from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any
import re

import pandas as pd
import streamlit as st
from supabase import create_client
from postgrest.exceptions import APIError


st.set_page_config(
    page_title="Meaning Preservation Annotation",
    page_icon="📝",
    layout="wide",
)

LABELS = ["YES", "NO", "MAYBE"]

STEP_DEFINITIONS: list[dict[str, Any]] = [
    {
        "number": 1,
        "title": "Can the original post be understood?",
        "quick": "Decide whether the original post gives enough information to understand the general topic and what is being discussed.",
        "guidance": """
The meaning may be unclear if the post depends on missing context, such as a previous comment, an unclear reference, or something outside the text.
""",
        "options": [
            {
                "label": "No — the original meaning cannot be judged confidently",
                "outcome": "MAYBE",
                "reason": "Context unclear",
            },
            {
                "label": "Yes — the original is understandable enough",
                "outcome": "CONTINUE",
                "reason": "Original understandable",
            },
        ],
    },
    {
        "number": 2,
        "title": "Is the core meaning preserved?",
        "quick": "Check whether the simplified version keeps the same main message, event, topic, outcome, claim, people involved and relationships.",
        "guidance": """
Also check that important details such as negation, time, cause or condition have not changed.

Example 1:

Original: “The council rejected our application.”  
Simplified: “The council is considering our application.”

The outcome has changed. This is **NO: Core meaning changed**.

Example 2:

Original: “They blamed me for the mistake.”  
Simplified: “I made the mistake.”

The meaning changes from an accusation to an admission. This is **NO: Core meaning changed**.
""",
        "options": [
            {
                "label": "No — the main message, event, participant or outcome has changed",
                "outcome": "NO",
                "reason": "Core meaning changed",
            },
            {
                "label": "Uncertain — the core meaning may have changed, but I am not sure",
                "outcome": "MAYBE",
                "reason": "Core meaning unclear",
            },
            {
                "label": "Yes — the core meaning is preserved",
                "outcome": "CONTINUE",
                "reason": "Core meaning preserved",
            },
        ],
    },
    {
        "number": 3,
        "title": "Are emotion, polarity and intensity preserved?",
        "quick": "Check whether the simplified version keeps the same emotional meaning and strength.",
        "guidance": """
For example, anger should not become neutral, criticism should not become praise, and strong emotion should not become much weaker or stronger.

Example:

Original: “I am absolutely furious about this.”  
Simplified: “I’m okay with this.”

The emotion and intensity have changed. This is **NO: Emotion or polarity changed**.
""",
        "options": [
            {
                "label": "No — emotion, polarity or intensity clearly changes the meaning",
                "outcome": "NO",
                "reason": "Emotion or polarity changed",
            },
            {
                "label": "Uncertain — there may be a small emotional change",
                "outcome": "MAYBE",
                "reason": "Emotional shift unclear",
            },
            {
                "label": "Yes — the emotional meaning is preserved",
                "outcome": "CONTINUE",
                "reason": "Emotion preserved",
            },
        ],
    },
    {
        "number": 4,
        "title": "Is non-literal or informal meaning preserved?",
        "quick": "Check whether sarcasm, irony, humour, idioms, metaphors, exaggeration, slang, abbreviations, profanity or informal language are handled correctly.",
        "guidance": """
The simplified version may explain these meanings directly, but the explanation must match the original meaning.

Example 1:

Original: “Fantastic. Another cancelled train.”  
Simplified: “The writer is happy that another train was cancelled.”

The sarcasm has been misunderstood. This is **NO: Non-literal meaning lost**.

Example 2:

Original: “Fuck my life.”  
Simplified: “I am a little upset.”

The strong frustration has been weakened too much. This is **MAYBE: Informal meaning or intensity changed** if the main message is still partly preserved, or **NO** if the intensity is central to the meaning.
""",
        "options": [
            {
                "label": "No — sarcasm, humour, slang, profanity or figurative meaning is misunderstood or omitted",
                "outcome": "NO",
                "reason": "Non-literal or informal meaning lost",
            },
            {
                "label": "Uncertain — some tone or humour may be lost, but the main message may still be preserved",
                "outcome": "MAYBE",
                "reason": "Tone or humour partly lost",
            },
            {
                "label": "Yes — the intended meaning is preserved or accurately explained",
                "outcome": "CONTINUE",
                "reason": "Non-literal or informal meaning preserved",
            },
        ],
    },
    {
        "number": 5,
        "title": "Are emojis, hashtags and social media cues handled accurately?",
        "quick": "Check whether emojis, hashtags, @mentions or links affect emotion, sarcasm, emphasis, topic, identity, humour or attitude.",
        "guidance": """
Example 1:

Original: “Great 🙄”  
Simplified: “That is great.”

The eye-roll emoji showed sarcasm, so the meaning has changed. This is **NO: Social media meaning changed**.

Example 2:

Original: “I passed! 🎉”  
Simplified: “I passed! I am celebrating.”

The emoji meaning is explained clearly. This is acceptable.
""",
        "options": [
            {
                "label": "No — an emoji, hashtag or social media cue changes the meaning",
                "outcome": "NO",
                "reason": "Social media meaning changed",
            },
            {
                "label": "Uncertain — the effect of the cue is unclear",
                "outcome": "MAYBE",
                "reason": "Social media cue unclear",
            },
            {
                "label": "Yes — the cue is preserved, safely removed or clearly explained",
                "outcome": "CONTINUE",
                "reason": "Social media cues preserved",
            },
        ],
    },
    {
        "number": 6,
        "title": "Has important information been removed or unsupported information added?",
        "quick": "Check whether important meaning was removed, or whether the simplified version adds new meaning not present in the original.",
        "guidance": """
A simplification may remove repetition or filler. It may also add a short explanation if the meaning is already clear. However, it should not remove important information or add unsupported meaning.

Example 1:

Original: “I did not agree to attend tomorrow.”  
Simplified: “I agreed to attend.”

Important meaning has been lost. This is **NO: Material omission or unsupported addition**.

Example 2:

Original: “She did not reply.”  
Simplified: “She ignored me because she does not care.”

The simplified version adds an unsupported motive. This is **NO: Material omission or unsupported addition**.
""",
        "options": [
            {
                "label": "Yes — important information is removed or unsupported meaning is added",
                "outcome": "NO",
                "reason": "Material omission or unsupported addition",
            },
            {
                "label": "Uncertain — the effect of the change is unclear",
                "outcome": "MAYBE",
                "reason": "Information change unclear",
            },
            {
                "label": "No — only non-essential details are removed and additions are clearly supported",
                "outcome": "YES",
                "reason": "Meaning preserved",
            },
        ],
    },
]


# -----------------------------
# Supabase helpers
# -----------------------------

@st.cache_resource
def get_supabase_client():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        st.error(
            "Supabase secrets are missing. Add SUPABASE_URL and SUPABASE_KEY "
            "in Streamlit Community Cloud → Manage app → Settings → Secrets."
        )
        st.stop()
    return create_client(url, key)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_execute(query_builder, friendly_error: str):
    try:
        return query_builder.execute()
    except APIError as exc:
        st.error(friendly_error)
        with st.expander("Technical details"):
            st.code(str(exc))
        st.stop()
    except Exception as exc:
        st.error(friendly_error)
        with st.expander("Technical details"):
            st.code(str(exc))
        st.stop()


@st.cache_data(ttl=20)
def load_posts() -> list[dict[str, Any]]:
    client = get_supabase_client()
    response = safe_execute(
        client.table("posts").select("*").order("display_order"),
        "The app could not read the posts table in Supabase. Check that the tables exist and that Streamlit secrets use the correct Supabase project.",
    )
    return response.data or []


def load_all_progress() -> list[dict[str, Any]]:
    client = get_supabase_client()
    response = safe_execute(
        client.table("annotation_progress").select("*"),
        "The app could not read annotation progress from Supabase.",
    )
    return response.data or []


def load_progress(email: str) -> list[dict[str, Any]]:
    client = get_supabase_client()
    response = safe_execute(
        client.table("annotation_progress").select("*").eq("annotator_id", email),
        "The app could not read your saved progress from Supabase.",
    )
    return response.data or []


def load_step_answers(email: str, post_id: str) -> list[dict[str, Any]]:
    client = get_supabase_client()
    response = safe_execute(
        client.table("step_answers")
        .select("*")
        .eq("annotator_id", email)
        .eq("post_id", post_id)
        .order("step_number"),
        "The app could not read saved step answers from Supabase.",
    )
    return response.data or []


def save_step_answer(email: str, post_id: str, step_number: int, decision: str, reason: str, comment: str) -> None:
    client = get_supabase_client()
    safe_execute(
        client.table("step_answers").upsert(
            {
                "annotator_id": email,
                "post_id": post_id,
                "step_number": step_number,
                "decision": decision,
                "reason": reason,
                "comment": comment,
                "updated_at": utc_now(),
            },
            on_conflict="annotator_id,post_id,step_number",
        ),
        "The app could not save this step answer. Check Supabase permissions.",
    )


def save_progress(
    email: str,
    post_id: str,
    current_step: int,
    completed: bool,
    final_label: str | None = None,
    terminal_reason: str | None = None,
    terminal_step: int | None = None,
    comment: str | None = None,
) -> None:
    client = get_supabase_client()
    safe_execute(
        client.table("annotation_progress").upsert(
            {
                "annotator_id": email,
                "post_id": post_id,
                "current_step": current_step,
                "completed": completed,
                "final_label": final_label,
                "terminal_reason": terminal_reason,
                "terminal_step": terminal_step,
                "comment": comment or "",
                "updated_at": utc_now(),
            },
            on_conflict="annotator_id,post_id",
        ),
        "The app could not save progress. Check Supabase permissions.",
    )


def reset_one_annotation(email: str, post_id: str) -> None:
    client = get_supabase_client()
    safe_execute(
        client.table("step_answers").delete().eq("annotator_id", email).eq("post_id", post_id),
        "The app could not delete step answers for this post.",
    )
    safe_execute(
        client.table("annotation_progress").delete().eq("annotator_id", email).eq("post_id", post_id),
        "The app could not delete progress for this post.",
    )
    st.cache_data.clear()


def delete_annotator_results(email: str) -> None:
    client = get_supabase_client()
    safe_execute(
        client.table("step_answers").delete().eq("annotator_id", email),
        "The app could not delete this annotator's step answers.",
    )
    safe_execute(
        client.table("annotation_progress").delete().eq("annotator_id", email),
        "The app could not delete this annotator's progress.",
    )
    st.cache_data.clear()


def clear_all_posts_and_annotations() -> None:
    client = get_supabase_client()
    safe_execute(client.table("step_answers").delete().neq("id", -1), "Could not clear step answers.")
    safe_execute(client.table("annotation_progress").delete().neq("id", -1), "Could not clear annotation progress.")
    safe_execute(client.table("posts").delete().neq("post_id", "__never__"), "Could not clear posts.")
    st.cache_data.clear()


# -----------------------------
# Data import and export
# -----------------------------


def read_uploaded_dataset(uploaded_file) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


def guess_column(df: pd.DataFrame, candidates: list[str]) -> str:
    normalised = {str(col).strip().lower().replace(" ", "_"): col for col in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower().replace(" ", "_")
        if key in normalised:
            return normalised[key]
    return df.columns[0]


def import_posts_to_supabase(df: pd.DataFrame, id_col: str | None, original_col: str, simplified_col: str, replace_existing: bool) -> int:
    if replace_existing:
        clear_all_posts_and_annotations()

    client = get_supabase_client()
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, row in df.iterrows():
        if id_col:
            raw_id = row[id_col]
            post_id = str(raw_id).strip()
        else:
            post_id = str(index + 1)

        if not post_id or post_id.lower() == "nan":
            post_id = str(index + 1)

        if post_id in seen:
            post_id = f"{post_id}_{index + 1}"
        seen.add(post_id)

        original = "" if pd.isna(row[original_col]) else str(row[original_col])
        simplified = "" if pd.isna(row[simplified_col]) else str(row[simplified_col])
        if original.strip() and simplified.strip():
            records.append(
                {
                    "post_id": post_id,
                    "display_order": int(index + 1),
                    "original_post": original,
                    "simplified_post": simplified,
                    "updated_at": utc_now(),
                }
            )

    if not records:
        return 0

    for start in range(0, len(records), 500):
        safe_execute(
            client.table("posts").upsert(records[start : start + 500], on_conflict="post_id"),
            "The app could not import posts into Supabase. Check table permissions.",
        )

    load_posts.clear()
    return len(records)


def make_label_summary(progress_df: pd.DataFrame) -> pd.DataFrame:
    completed = progress_df[progress_df["completed"].eq(True)] if not progress_df.empty else pd.DataFrame()
    counts = completed["final_label"].value_counts().reindex(LABELS, fill_value=0) if not completed.empty else pd.Series([0, 0, 0], index=LABELS)
    total = int(counts.sum())
    return pd.DataFrame(
        {
            "Final label": LABELS,
            "Number": [int(counts[label]) for label in LABELS],
            "Percentage": [round((int(counts[label]) / total * 100), 1) if total else 0 for label in LABELS],
        }
    )


def make_by_annotator_summary(progress_df: pd.DataFrame) -> pd.DataFrame:
    if progress_df.empty:
        return pd.DataFrame(columns=["Email", "YES", "NO", "MAYBE", "Total completed", "Total started"])

    completed = progress_df[progress_df["completed"].eq(True)]
    if completed.empty:
        started = progress_df.groupby("annotator_id")["post_id"].count().reset_index(name="Total started")
        started = started.rename(columns={"annotator_id": "Email"})
        for label in LABELS:
            started[label] = 0
        started["Total completed"] = 0
        return started[["Email", "YES", "NO", "MAYBE", "Total completed", "Total started"]]

    pivot = completed.pivot_table(
        index="annotator_id",
        columns="final_label",
        values="post_id",
        aggfunc="count",
        fill_value=0,
    ).reset_index()
    for label in LABELS:
        if label not in pivot.columns:
            pivot[label] = 0
    started = progress_df.groupby("annotator_id")["post_id"].count().reset_index(name="Total started")
    out = pivot.merge(started, on="annotator_id", how="left")
    out["Total completed"] = out[LABELS].sum(axis=1)
    out = out.rename(columns={"annotator_id": "Email"})
    return out[["Email", "YES", "NO", "MAYBE", "Total completed", "Total started"]].sort_values("Email")


def build_export() -> bytes:
    client = get_supabase_client()
    posts = pd.DataFrame(safe_execute(client.table("posts").select("*").order("display_order"), "Could not export posts.").data or [])
    progress = pd.DataFrame(safe_execute(client.table("annotation_progress").select("*"), "Could not export progress.").data or [])
    steps = pd.DataFrame(safe_execute(client.table("step_answers").select("*"), "Could not export step answers.").data or [])

    if posts.empty:
        posts = pd.DataFrame(columns=["post_id", "display_order", "original_post", "simplified_post"])
    if progress.empty:
        progress = pd.DataFrame(columns=["annotator_id", "post_id", "current_step", "completed", "final_label", "terminal_reason", "terminal_step", "comment", "updated_at"])
    if steps.empty:
        steps = pd.DataFrame(columns=["annotator_id", "post_id", "step_number", "decision", "reason", "comment", "updated_at"])

    rows = progress.merge(posts, how="left", on="post_id", suffixes=("", "_post"))
    rows = rows.rename(columns={"annotator_id": "annotator_email"})

    if not steps.empty:
        pivot_decisions = steps.pivot_table(index=["annotator_id", "post_id"], columns="step_number", values="decision", aggfunc="last")
        pivot_decisions.columns = [f"step_{int(c)}_decision" for c in pivot_decisions.columns]
        pivot_decisions = pivot_decisions.reset_index().rename(columns={"annotator_id": "annotator_email"})

        pivot_reasons = steps.pivot_table(index=["annotator_id", "post_id"], columns="step_number", values="reason", aggfunc="last")
        pivot_reasons.columns = [f"step_{int(c)}_reason" for c in pivot_reasons.columns]
        pivot_reasons = pivot_reasons.reset_index().rename(columns={"annotator_id": "annotator_email"})

        rows = rows.merge(pivot_decisions, how="left", on=["annotator_email", "post_id"])
        rows = rows.merge(pivot_reasons, how="left", on=["annotator_email", "post_id"])

    overall = make_label_summary(progress)
    by_annotator = make_by_annotator_summary(progress)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        rows.to_excel(writer, sheet_name="Annotations", index=False)
        steps.rename(columns={"annotator_id": "annotator_email"}).to_excel(writer, sheet_name="Step answers", index=False)
        overall.to_excel(writer, sheet_name="Overall summary", index=False)
        by_annotator.to_excel(writer, sheet_name="By annotator", index=False)

        workbook = writer.book
        header = workbook.add_format({"bold": True, "bg_color": "#2F5597", "font_color": "white", "border": 1, "text_wrap": True})
        wrap = workbook.add_format({"text_wrap": True, "valign": "top"})
        pct = workbook.add_format({"num_format": '0.0"%"'})

        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            if sheet_name == "Annotations":
                data = rows
            elif sheet_name == "Step answers":
                data = steps
            elif sheet_name == "Overall summary":
                data = overall
            else:
                data = by_annotator
            for col_num, value in enumerate(data.columns):
                ws.write(0, col_num, value, header)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(data), 1), max(len(data.columns) - 1, 0))
            ws.set_column(0, max(len(data.columns) - 1, 0), 24, wrap)

        if not overall.empty:
            ws = writer.sheets["Overall summary"]
            chart = workbook.add_chart({"type": "column"})
            chart.add_series({"name": "Overall", "categories": "='Overall summary'!$A$2:$A$4", "values": "='Overall summary'!$B$2:$B$4", "data_labels": {"value": True}})
            chart.set_title({"name": "Overall YES / NO / MAYBE"})
            chart.set_legend({"none": True})
            ws.insert_chart("E2", chart)

    return output.getvalue()


# -----------------------------
# UI helpers
# -----------------------------


def normalise_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def render_post_box(title: str, text: str):
    st.subheader(title)
    safe_text = str(text).replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"""
<div style="
    border: 1px solid #B8C4D8;
    border-radius: 10px;
    padding: 18px;
    min-height: 160px;
    background: #F7F9FC;
    font-size: 1.08rem;
    white-space: pre-wrap;
">{safe_text}</div>
""",
        unsafe_allow_html=True,
    )


def post_status(post_id: str, progress_by_post: dict[str, dict[str, Any]]) -> str:
    p = progress_by_post.get(post_id)
    if not p:
        return "Not started"
    if p.get("completed"):
        return str(p.get("final_label") or "Completed")
    return f"In progress — Step {p.get('current_step', 1)}"


def get_progress_by_post(progress: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p["post_id"]: p for p in progress}


def find_next_unfinished_index(posts: list[dict[str, Any]], progress_by_post: dict[str, dict[str, Any]], start: int = 0) -> int:
    if not posts:
        return 0
    n = len(posts)
    for offset in range(n):
        idx = (start + offset) % n
        p = progress_by_post.get(posts[idx]["post_id"])
        if not p or not p.get("completed"):
            return idx
    return min(start, n - 1)


def annotator_page():
    st.title("Meaning Preservation Annotation")
    st.write("Enter your email address. Your progress is saved automatically after every decision.")

    posts = load_posts()
    if not posts:
        st.warning("No posts have been uploaded yet. Ask the researcher to add posts in the Researcher admin page.")
        return

    email_input = st.text_input("Email address", placeholder="name@example.com")
    email = normalise_email(email_input)
    if not email:
        st.info("Enter your email address to begin or resume.")
        return
    if not is_valid_email(email):
        st.warning("Please enter a valid email address.")
        return

    session_email_key = "active_annotator_email"
    if st.session_state.get(session_email_key) != email:
        st.session_state[session_email_key] = email
        st.session_state["current_post_index"] = 0

    progress = load_progress(email)
    progress_by_post = get_progress_by_post(progress)
    completed_count = sum(1 for p in progress if p.get("completed"))
    total_posts = len(posts)

    st.progress(completed_count / total_posts if total_posts else 0)
    st.caption(f"{completed_count} of {total_posts} posts completed for {email}.")

    with st.expander("Your YES / NO / MAYBE summary", expanded=False):
        own_progress_df = pd.DataFrame(progress)
        st.dataframe(make_label_summary(own_progress_df), hide_index=True, use_container_width=True)

    if "current_post_index" not in st.session_state:
        st.session_state["current_post_index"] = find_next_unfinished_index(posts, progress_by_post, 0)
    st.session_state["current_post_index"] = max(0, min(int(st.session_state["current_post_index"]), total_posts - 1))

    idx = st.session_state["current_post_index"]
    current_post = posts[idx]
    current_progress = progress_by_post.get(current_post["post_id"], {})

    st.divider()
    nav_left, nav_mid, nav_right, nav_unfinished = st.columns([1, 1.5, 1, 1.4])
    with nav_left:
        if st.button("← Previous post", disabled=idx == 0, use_container_width=True):
            st.session_state["current_post_index"] = max(0, idx - 1)
            st.rerun()
    with nav_mid:
        st.markdown(f"<div style='text-align:center'><strong>Post {idx + 1} of {total_posts}</strong><br>Status: {post_status(current_post['post_id'], progress_by_post)}</div>", unsafe_allow_html=True)
    with nav_right:
        if st.button("Next post →", disabled=idx >= total_posts - 1, use_container_width=True):
            st.session_state["current_post_index"] = min(total_posts - 1, idx + 1)
            st.rerun()
    with nav_unfinished:
        if st.button("Next unfinished", use_container_width=True):
            st.session_state["current_post_index"] = find_next_unfinished_index(posts, progress_by_post, idx + 1)
            st.rerun()

    post_labels = [f"{i + 1}. {p['post_id']} — {post_status(p['post_id'], progress_by_post)}" for i, p in enumerate(posts)]
    selected_label = st.selectbox("Jump to a post", post_labels, index=idx)
    selected_idx = post_labels.index(selected_label)
    if selected_idx != idx:
        st.session_state["current_post_index"] = selected_idx
        st.rerun()

    st.markdown(f"### Current post ID: `{current_post['post_id']}`")
    left, right = st.columns(2)
    with left:
        render_post_box("Original post", current_post["original_post"])
    with right:
        render_post_box("Simplified post", current_post["simplified_post"])

    step_answers = load_step_answers(email, current_post["post_id"])
    if step_answers:
        with st.expander("Saved step answers"):
            for answer in step_answers:
                st.write(f"**Step {answer['step_number']}:** {answer['decision']}")

    if current_progress.get("completed"):
        label = current_progress.get("final_label", "")
        reason = current_progress.get("terminal_reason", "")
        if label == "YES":
            st.success(f"Final label already saved: YES — {reason}")
        elif label == "NO":
            st.error(f"Final label already saved: NO — {reason}")
        else:
            st.warning(f"Final label already saved: MAYBE — {reason}")
        with st.expander("Change this annotation"):
            st.write("This will delete your saved answers for this post only and let you annotate it again.")
            if st.button("Restart this post", type="secondary"):
                reset_one_annotation(email, current_post["post_id"])
                st.rerun()
        return

    current_step = int(current_progress.get("current_step") or 1)
    current_step = max(1, min(current_step, len(STEP_DEFINITIONS)))

    st.divider()
    step = STEP_DEFINITIONS[current_step - 1]
    st.markdown(f"## Step {step['number']}: {step['title']}")
    st.write(step["quick"])

    with st.expander("Show guidance and examples"):
        st.markdown(step["guidance"])

    option_labels = [option["label"] for option in step["options"]]

    with st.form(key=f"form_{email}_{current_post['post_id']}_{current_step}"):
        selected = st.radio("Select one decision", option_labels, index=None)
        comment = st.text_area("Optional comment", placeholder="Add a short explanation if useful.")
        submitted = st.form_submit_button("Save decision and continue", use_container_width=True)

    if submitted:
        if selected is None:
            st.warning("Please select a decision first.")
            return

        option = next(o for o in step["options"] if o["label"] == selected)
        outcome = option["outcome"]
        reason = option["reason"]

        save_step_answer(email, current_post["post_id"], current_step, selected, reason, comment)

        if outcome == "CONTINUE":
            save_progress(email, current_post["post_id"], current_step + 1, False, comment=comment)
            st.success("Saved. Moving to the next step.")
        else:
            save_progress(email, current_post["post_id"], current_step, True, outcome, reason, current_step, comment)
            st.session_state["current_post_index"] = find_next_unfinished_index(posts, get_progress_by_post(load_progress(email)), idx + 1)
        st.rerun()

    if step_answers:
        with st.expander("Undo/restart this post"):
            if st.button("Restart this post from Step 1"):
                reset_one_annotation(email, current_post["post_id"])
                st.rerun()


def admin_page():
    st.title("Researcher Admin")

    expected_password = st.secrets.get("ADMIN_PASSWORD", "")
    password = st.text_input("Admin password", type="password")
    if not expected_password:
        st.error("ADMIN_PASSWORD is missing from Streamlit secrets.")
        return
    if password != expected_password:
        st.info("Enter the admin password to continue.")
        return

    st.success("Admin access granted.")

    tab_upload, tab_dashboard, tab_delete, tab_export = st.tabs(["Upload / update posts", "Dashboard", "Delete annotator results", "Export"])

    with tab_upload:
        st.subheader("Upload or update posts")
        st.write("Upload a CSV or XLSX file. Recommended columns: post_id, original_post, simplified_post. You can also map different column names.")
        uploaded_file = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"])

        if uploaded_file:
            df = read_uploaded_dataset(uploaded_file)
            st.write("Preview")
            st.dataframe(df.head(10), use_container_width=True)

            columns = list(df.columns)
            original_guess = guess_column(df, ["original_post", "original", "source", "source_text", "post", "text", "tweet"])
            simplified_guess = guess_column(df, ["simplified_post", "simplified", "target", "target_text", "simplification"])
            id_guess = guess_column(df, ["post_id", "id", "item_id", "row_id"])

            id_options = ["Use row number"] + columns
            default_id_index = id_options.index(id_guess) if id_guess in id_options else 0
            id_choice = st.selectbox("Post ID column", id_options, index=default_id_index)
            id_col = None if id_choice == "Use row number" else id_choice
            original_col = st.selectbox("Original post column", columns, index=columns.index(original_guess) if original_guess in columns else 0)
            simplified_col = st.selectbox("Simplified post column", columns, index=columns.index(simplified_guess) if simplified_guess in columns else min(1, len(columns) - 1))

            replace_existing = st.checkbox("Replace existing posts and delete all existing annotations", value=False)
            if replace_existing:
                st.warning("This will remove all current posts and all saved annotations before importing the new dataset.")

            if original_col == simplified_col:
                st.error("Original and simplified post columns must be different.")
            else:
                if st.button("Import / update posts", type="primary"):
                    count = import_posts_to_supabase(df, id_col, original_col, simplified_col, replace_existing)
                    st.success(f"Imported or updated {count} posts.")
                    st.cache_data.clear()

        posts = load_posts()
        st.subheader("Current posts in database")
        st.write(f"{len(posts)} posts available.")
        if posts:
            st.dataframe(pd.DataFrame(posts).head(20), use_container_width=True)

    with tab_dashboard:
        st.subheader("Common YES / NO / MAYBE table")
        progress = pd.DataFrame(load_all_progress())
        overall = make_label_summary(progress)
        st.dataframe(overall, hide_index=True, use_container_width=True)

        if not progress.empty:
            completed = progress[progress["completed"].eq(True)]
            counts = completed["final_label"].value_counts().reindex(LABELS, fill_value=0) if not completed.empty else pd.Series([0, 0, 0], index=LABELS)
            total_completed = int(counts.sum())
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("YES", int(counts["YES"]))
            c2.metric("NO", int(counts["NO"]))
            c3.metric("MAYBE", int(counts["MAYBE"]))
            c4.metric("Completed annotations", total_completed)
            st.bar_chart(pd.DataFrame({"Number": [int(counts[label]) for label in LABELS]}, index=LABELS))

        st.subheader("YES / NO / MAYBE by annotator email")
        by_annotator = make_by_annotator_summary(progress)
        st.dataframe(by_annotator, hide_index=True, use_container_width=True)

        if not by_annotator.empty:
            st.subheader("Individual annotator tables")
            for _, row in by_annotator.iterrows():
                email = row["Email"]
                with st.expander(str(email)):
                    individual = pd.DataFrame(
                        {
                            "Final label": LABELS,
                            "Number": [int(row.get(label, 0)) for label in LABELS],
                        }
                    )
                    total = int(individual["Number"].sum())
                    individual["Percentage"] = individual["Number"].apply(lambda x: round(x / total * 100, 1) if total else 0)
                    st.dataframe(individual, hide_index=True, use_container_width=True)

    with tab_delete:
        st.subheader("Delete one annotator's results")
        progress = pd.DataFrame(load_all_progress())
        if progress.empty:
            st.info("There are no annotator results to delete yet.")
        else:
            emails = sorted(progress["annotator_id"].dropna().unique().tolist())
            selected_email = st.selectbox("Select annotator email", emails)
            selected_count = int(progress[progress["annotator_id"].eq(selected_email)].shape[0])
            st.warning(f"This will delete all saved progress and step answers for {selected_email}. It will not delete the posts.")
            st.write(f"Saved post-level records for this annotator: {selected_count}")
            confirm = st.text_input("Type the annotator email to confirm deletion")
            if st.button("Delete this annotator's results", type="primary", disabled=confirm.strip().lower() != selected_email.lower()):
                delete_annotator_results(selected_email)
                st.success(f"Deleted results for {selected_email}.")
                st.rerun()

    with tab_export:
        st.subheader("Export results")
        st.write("Download all annotations, step answers, the common summary and by-annotator summaries as an Excel workbook.")
        export_bytes = build_export()
        st.download_button(
            "Download XLSX results",
            data=export_bytes,
            file_name="meaning_preservation_annotation_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def main():
    with st.sidebar:
        st.header("Navigation")
        page = st.radio("Choose page", ["Annotator", "Researcher admin"])
        st.caption("Annotators should use the Annotator page only.")

    if page == "Annotator":
        annotator_page()
    else:
        admin_page()


if __name__ == "__main__":
    main()
