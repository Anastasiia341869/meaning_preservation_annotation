from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Meaning Preservation Annotation", page_icon="📝", layout="wide")

LABELS = ["YES", "NO", "MAYBE"]

STEP_DEFINITIONS: list[dict[str, Any]] = [
    {
        "number": 1,
        "title": "Can the original post be understood well enough to judge its meaning?",
        "quick": "Consider whether the text provides enough information to identify the general topic and/or what happened or is being discussed.",
        "guidance": """
Decision:

- No: the original meaning cannot be judged confidently → MAYBE: Context unclear
- Yes: the original is understandable enough to evaluate → Go to Step 2
""",
        "options": [
            {"label": "No — the original meaning cannot be judged confidently", "outcome": "MAYBE", "reason": "Context unclear"},
            {"label": "Yes — the original is understandable enough to evaluate", "outcome": "CONTINUE", "reason": "Original understandable"},
        ],
    },
    {
        "number": 2,
        "title": "Is the main event, situation or proposition preserved?",
        "quick": "Check whether the simplified version keeps the same action/event, state/situation, topic, outcome, central claim, and factual relationships such as cause, condition, time or negation.",
        "guidance": """
Example:

Original: “The council rejected our application.”  
Simplified: “The council is considering our application.”

The outcome has changed from rejection to consideration.

Decision:

- The main event, situation, outcome or claim has changed → NO: Core meaning changed
- An important factual relationship is uncertain or only partly retained → MAYBE: Core meaning unclear
- The main event and central claim are preserved → Go to Step 3
""",
        "options": [
            {"label": "The main event, situation, outcome or claim has changed", "outcome": "NO", "reason": "Core meaning changed"},
            {"label": "An important factual relationship is uncertain or only partly retained", "outcome": "MAYBE", "reason": "Core meaning unclear"},
            {"label": "The main event and central claim are preserved", "outcome": "CONTINUE", "reason": "Core meaning preserved"},
        ],
    },
    {
        "number": 3,
        "title": "Are the participants, targets and relationships preserved?",
        "quick": "Check who performs the action, who is affected, who is praised/criticised/blamed/insulted/addressed, named people/groups, @mentions, pronouns, and relationships.",
        "guidance": """
Example:

Original: “They blamed me for the mistake.”  
Simplified: “I made the mistake.”

The original reports an accusation. The simplified version changes this into an admission.

Decision:

- The actor, recipient, target, group or relationship has changed → NO: Participant or target changed
- A participant has been removed or made unclear, and the effect is uncertain → MAYBE: Participant reference unclear
- The participants, targets and relationships remain the same → Go to Step 4
""",
        "options": [
            {"label": "The actor, recipient, target, group or relationship has changed", "outcome": "NO", "reason": "Participant or target changed"},
            {"label": "A participant has been removed or made unclear, and the effect is uncertain", "outcome": "MAYBE", "reason": "Participant reference unclear"},
            {"label": "The participants, targets and relationships remain the same", "outcome": "CONTINUE", "reason": "Participants preserved"},
        ],
    },
    {
        "number": 4,
        "title": "Is the writer’s communicative purpose preserved?",
        "quick": "Identify what the writer is doing: giving information, asking, requesting, commanding, advising, warning, complaining, praising, criticising, insulting, threatening, joking, or expressing surprise/doubt/disbelief.",
        "guidance": """
Example:

Original: “Could you possibly stop doing that?”  
Simplified: “You must stop doing that.”

This changes the communicative purpose or force.

Decision:

- The type of communicative act changes → NO: Communicative purpose changed
- The same broad purpose remains, but politeness, directness or force may have changed → MAYBE: Communicative force changed
- The communicative purpose is preserved → Go to Step 5
""",
        "options": [
            {"label": "The type of communicative act changes", "outcome": "NO", "reason": "Communicative purpose changed"},
            {"label": "The same broad purpose remains, but politeness, directness or force may have changed", "outcome": "MAYBE", "reason": "Communicative force changed"},
            {"label": "The communicative purpose is preserved", "outcome": "CONTINUE", "reason": "Communicative purpose preserved"},
        ],
    },
    {
        "number": 5,
        "title": "Has polarity, emotion or emotional intensity changed?",
        "quick": "Look for anger softened into neutrality, criticism changed into praise, sadness changed into anger, uncertainty changed into confidence, mild emotion made stronger, or strong emotion removed.",
        "guidance": """
Example:

Original: “I am absolutely furious about this.”  
Simplified: “I do not like this.”

This substantially softens the anger.

Decision:

- Polarity, emotion or intensity has clearly changed in a meaning-relevant way → NO: Emotion or polarity changed
- A small emotional shift may have occurred, but its importance is uncertain → MAYBE: Emotional shift unclear
- Polarity, emotion and relevant intensity are preserved → Go to Step 6
""",
        "options": [
            {"label": "Polarity, emotion or intensity has clearly changed in a meaning-relevant way", "outcome": "NO", "reason": "Emotion or polarity changed"},
            {"label": "A small emotional shift may have occurred, but its importance is uncertain", "outcome": "MAYBE", "reason": "Emotional shift unclear"},
            {"label": "Polarity, emotion and relevant intensity are preserved", "outcome": "CONTINUE", "reason": "Emotion preserved"},
        ],
    },
    {
        "number": 6,
        "title": "Is non-literal meaning preserved?",
        "quick": "Check sarcasm, irony, humour, idioms, metaphors, rhetorical questions, exaggeration, understatement, wordplay, mock praise, and contrast between literal wording and intended meaning.",
        "guidance": """
The simplified version may explain non-literal meaning directly, but the explanation must accurately represent the intended message.

Example:

Original: “Fantastic. Another cancelled train.”  
Incorrect simplification: “The writer is happy that another train was cancelled.”

This interprets sarcasm literally.

Decision:

- Sarcasm, irony or humour is interpreted literally or incorrectly → NO: Non-literal meaning lost
- An idiom, metaphor or exaggeration is given the wrong interpretation → NO: Figurative meaning changed
- Wordplay or humour is removed, but the main message remains and its importance is uncertain → MAYBE: Humour or wordplay lost
- The intended non-literal meaning is preserved or accurately explained → Go to Step 7
""",
        "options": [
            {"label": "Sarcasm, irony or humour is interpreted literally or incorrectly", "outcome": "NO", "reason": "Non-literal meaning lost"},
            {"label": "An idiom, metaphor or exaggeration is given the wrong interpretation", "outcome": "NO", "reason": "Figurative meaning changed"},
            {"label": "Wordplay or humour is removed, but the main message remains and its importance is uncertain", "outcome": "MAYBE", "reason": "Humour or wordplay lost"},
            {"label": "The intended non-literal meaning is preserved or accurately explained", "outcome": "CONTINUE", "reason": "Non-literal meaning preserved"},
        ],
    },
    {
        "number": 7,
        "title": "Are emojis handled accurately?",
        "quick": "Check whether emojis repeat emotion, intensify emotion, mark sarcasm/irony, replace a word, represent an action/object, soften criticism, add playfulness, uncertainty, embarrassment or disbelief.",
        "guidance": """
Examples:

Original: “Great 🙄”  
Simplified: “That is great.”  
The eye-roll emoji marks sarcasm. Removing it makes the statement appear genuinely positive.

Original: “I passed! 🎉”  
Simplified: “I passed! I am celebrating.”  
The celebratory meaning is expressed in words.

Original: “I disagree.”  
Simplified: “I disagree 😡”  
The new emoji introduces anger that was not explicit in the original. This may be MAYBE if anger is plausible but not clearly supported.

Decision:

- An emoji’s important emotional, ironic or semantic function is lost → NO: Emoji meaning lost
- A new emoji clearly introduces or changes emotion, stance or intensity → NO: Unsupported emoji meaning
- The effect of removing, changing or adding the emoji is uncertain → MAYBE: Emoji effect unclear
- The emoji is retained, removed or explained without changing its function → Go to Step 8
""",
        "options": [
            {"label": "An emoji’s important emotional, ironic or semantic function is lost", "outcome": "NO", "reason": "Emoji meaning lost"},
            {"label": "A new emoji clearly introduces or changes emotion, stance or intensity", "outcome": "NO", "reason": "Unsupported emoji meaning"},
            {"label": "The effect of removing, changing or adding the emoji is uncertain", "outcome": "MAYBE", "reason": "Emoji effect unclear"},
            {"label": "The emoji is retained, removed or explained without changing its function", "outcome": "CONTINUE", "reason": "Emoji handled accurately"},
        ],
    },
    {
        "number": 8,
        "title": "Are hashtags, mentions, links and named references preserved appropriately?",
        "quick": "Check whether an important hashtag, mention, link, campaign name or reference is removed, changed, reformatted, expanded or explained.",
        "guidance": """
Decision:

- An important hashtag, mention, link, campaign name or reference is removed or changed, altering the message → NO: Important social media reference lost
- The element is removed, but its importance cannot be judged confidently → MAYBE: Social media reference unclear
- The element is reformatted, expanded or explained without changing its function → Go to Step 9
""",
        "options": [
            {"label": "An important hashtag, mention, link, campaign name or reference is removed or changed, altering the message", "outcome": "NO", "reason": "Important social media reference lost"},
            {"label": "The element is removed, but its importance cannot be judged confidently", "outcome": "MAYBE", "reason": "Social media reference unclear"},
            {"label": "The element is reformatted, expanded or explained without changing its function", "outcome": "CONTINUE", "reason": "Social media references preserved"},
        ],
    },
    {
        "number": 9,
        "title": "Are abbreviations, slang, profanity and informal language handled accurately?",
        "quick": "Check abbreviations, slang, profanity and informal language. Preserve both basic meaning and important social or emotional function.",
        "guidance": """
Safe abbreviation expansions may include:

- idk → “I do not know”
- tbh → “to be honest”
- imo → “in my opinion”

Only expand an abbreviation when its meaning is clear in context.

Slang may express approval, criticism, group identity, humour, emotional intensity, informality, or familiarity between speakers.

Profanity may function as an insult, intensifier, expression of anger/shock, humour, informal emphasis, frustration or despair. It should not automatically be deleted or weakened.

Example:

Original: “Fuck my life.”  
Simplified: “I am a little upset.”

The simplified version substantially weakens the frustration or despair.

Decision:

- An abbreviation, slang expression or informal phrase is interpreted incorrectly → NO: Informal expression mistranslated
- Profanity or slang is removed and important intensity, hostility, humour or identity is lost → NO: Register or intensity changed
- The core meaning is retained, but some informal tone or social meaning may have been lost → MAYBE: Register partially changed
- The expression is accurately expanded or explained → Go to Step 10
""",
        "options": [
            {"label": "An abbreviation, slang expression or informal phrase is interpreted incorrectly", "outcome": "NO", "reason": "Informal expression mistranslated"},
            {"label": "Profanity or slang is removed and important intensity, hostility, humour or identity is lost", "outcome": "NO", "reason": "Register or intensity changed"},
            {"label": "The core meaning is retained, but some informal tone or social meaning may have been lost", "outcome": "MAYBE", "reason": "Register partially changed"},
            {"label": "The expression is accurately expanded or explained", "outcome": "CONTINUE", "reason": "Informal language preserved"},
        ],
    },
    {
        "number": 10,
        "title": "Has important information been omitted or unsupported information added?",
        "quick": "Check whether important information was removed or unsupported facts, causes, motives, emotions, opinions, intentions, advice, warnings, moral judgements, assumptions or explanations were added.",
        "guidance": """
A simplification may remove repetition, filler or non-essential details. It may also add a brief explanation when the meaning is already clear.

Check whether it removes important information, such as:

- an event, participant or target
- a reason, consequence or condition
- negation, time, place or quantity
- emotion, warning, request or sarcastic cue

Also check whether it adds unsupported:

- facts, causes or motives
- emotions, opinions or intentions
- advice, warnings or moral judgements
- assumptions or explanations

Example of omission:

Original: “I did not agree to attend tomorrow.”  
Simplified: “I agreed to attend.”  
→ NO: Important information omitted

Example of unsupported addition:

Original: “She did not reply.”  
Simplified: “She ignored me because she does not care.”  
→ NO: Unsupported interpretation added

Safe changes include expanding idk to “I do not know,” explaining an idiom accurately, or removing repetition.

Decision:

- Important information is removed or unsupported meaning is added → NO: Material omission or unsupported addition
- The effect of the change is uncertain → MAYBE: Information change unclear
- Only non-essential details are removed, and additions are clearly supported → YES: Meaning preserved
""",
        "options": [
            {"label": "Important information is removed or unsupported meaning is added", "outcome": "NO", "reason": "Material omission or unsupported addition"},
            {"label": "The effect of the change is uncertain", "outcome": "MAYBE", "reason": "Information change unclear"},
            {"label": "Only non-essential details are removed, and additions are clearly supported", "outcome": "YES", "reason": "Meaning preserved"},
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
        st.error("Supabase secrets are missing. Add SUPABASE_URL and SUPABASE_KEY in Streamlit → App settings → Secrets.")
        st.stop()
    return create_client(url, key)

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@st.cache_data(ttl=30)
def load_posts() -> list[dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("posts").select("*").order("display_order").execute()
    return response.data or []

def load_progress(annotator_id: str) -> list[dict[str, Any]]:
    client = get_supabase_client()
    return client.table("annotation_progress").select("*").eq("annotator_id", annotator_id).execute().data or []

def load_step_answers(annotator_id: str, post_id: str) -> list[dict[str, Any]]:
    client = get_supabase_client()
    return client.table("step_answers").select("*").eq("annotator_id", annotator_id).eq("post_id", post_id).order("step_number").execute().data or []

def save_step_answer(annotator_id: str, post_id: str, step_number: int, decision: str, reason: str, comment: str) -> None:
    client = get_supabase_client()
    client.table("step_answers").upsert(
        {
            "annotator_id": annotator_id,
            "post_id": post_id,
            "step_number": step_number,
            "decision": decision,
            "reason": reason,
            "comment": comment,
            "updated_at": utc_now(),
        },
        on_conflict="annotator_id,post_id,step_number",
    ).execute()

def save_progress(annotator_id: str, post_id: str, current_step: int, completed: bool, final_label: str | None = None, terminal_reason: str | None = None, terminal_step: int | None = None, comment: str | None = None) -> None:
    client = get_supabase_client()
    client.table("annotation_progress").upsert(
        {
            "annotator_id": annotator_id,
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
    ).execute()

def reset_annotation(annotator_id: str, post_id: str) -> None:
    client = get_supabase_client()
    client.table("step_answers").delete().eq("annotator_id", annotator_id).eq("post_id", post_id).execute()
    client.table("annotation_progress").delete().eq("annotator_id", annotator_id).eq("post_id", post_id).execute()

def read_uploaded_dataset(uploaded_file) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)

def normalise_columns(df: pd.DataFrame) -> dict[str, str]:
    return {str(col).strip().lower().replace(" ", "_"): col for col in df.columns}

def guess_column(df: pd.DataFrame, candidates: list[str]) -> str:
    normalised = normalise_columns(df)
    for candidate in candidates:
        key = candidate.strip().lower().replace(" ", "_")
        if key in normalised:
            return normalised[key]
    return df.columns[0]

def import_posts_to_supabase(df: pd.DataFrame, id_col: str, original_col: str, simplified_col: str) -> int:
    client = get_supabase_client()
    records = []
    for index, row in df.iterrows():
        raw_id = row[id_col] if id_col else index + 1
        post_id = str(raw_id).strip()
        if not post_id or post_id.lower() == "nan":
            post_id = str(index + 1)
        original = "" if pd.isna(row[original_col]) else str(row[original_col])
        simplified = "" if pd.isna(row[simplified_col]) else str(row[simplified_col])
        if original.strip() and simplified.strip():
            records.append({"post_id": post_id, "display_order": int(index + 1), "original_post": original, "simplified_post": simplified, "updated_at": utc_now()})
    if not records:
        return 0
    for start in range(0, len(records), 500):
        client.table("posts").upsert(records[start:start + 500], on_conflict="post_id").execute()
    load_posts.clear()
    return len(records)

def build_export() -> bytes:
    client = get_supabase_client()
    posts = pd.DataFrame(client.table("posts").select("*").order("display_order").execute().data or [])
    progress = pd.DataFrame(client.table("annotation_progress").select("*").execute().data or [])
    steps = pd.DataFrame(client.table("step_answers").select("*").execute().data or [])

    if posts.empty:
        posts = pd.DataFrame(columns=["post_id", "display_order", "original_post", "simplified_post"])
    if progress.empty:
        progress = pd.DataFrame(columns=["annotator_id", "post_id", "current_step", "completed", "final_label", "terminal_reason", "terminal_step", "comment", "updated_at"])
    if steps.empty:
        steps = pd.DataFrame(columns=["annotator_id", "post_id", "step_number", "decision", "reason", "comment", "updated_at"])

    rows = progress.merge(posts, how="left", on="post_id", suffixes=("", "_post"))
    if not steps.empty:
        pivot_decisions = steps.pivot_table(index=["annotator_id", "post_id"], columns="step_number", values="decision", aggfunc="last")
        pivot_decisions.columns = [f"step_{int(c)}_decision" for c in pivot_decisions.columns]
        pivot_decisions = pivot_decisions.reset_index()
        pivot_reasons = steps.pivot_table(index=["annotator_id", "post_id"], columns="step_number", values="reason", aggfunc="last")
        pivot_reasons.columns = [f"step_{int(c)}_reason" for c in pivot_reasons.columns]
        pivot_reasons = pivot_reasons.reset_index()
        rows = rows.merge(pivot_decisions, how="left", on=["annotator_id", "post_id"]).merge(pivot_reasons, how="left", on=["annotator_id", "post_id"])

    completed = progress[progress.get("completed", pd.Series(dtype=bool)).eq(True)] if not progress.empty else progress
    counts = completed["final_label"].value_counts().reindex(LABELS, fill_value=0) if not completed.empty else pd.Series([0,0,0], index=LABELS)
    total = int(counts.sum())
    summary = pd.DataFrame({"final_label": LABELS, "number_of_annotations": [int(counts[label]) for label in LABELS], "percentage_of_completed_annotations": [round(float(counts[label]) / total * 100, 2) if total else 0 for label in LABELS]})
    by_annotator = progress.groupby("annotator_id", dropna=False).agg(total_started=("post_id", "count"), completed=("completed", "sum")).reset_index() if not progress.empty else pd.DataFrame(columns=["annotator_id", "total_started", "completed"])

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        rows.to_excel(writer, sheet_name="Annotations", index=False)
        steps.to_excel(writer, sheet_name="Step answers", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False, startrow=1)
        by_annotator.to_excel(writer, sheet_name="Summary", index=False, startrow=8)
        workbook = writer.book
        header = workbook.add_format({"bold": True, "bg_color": "#2F5597", "font_color": "white", "border": 1})
        wrap = workbook.add_format({"text_wrap": True, "valign": "top"})
        title = workbook.add_format({"bold": True, "font_size": 16})
        for sheet_name, data in [("Annotations", rows), ("Step answers", steps)]:
            ws = writer.sheets[sheet_name]
            for col_num, value in enumerate(data.columns):
                ws.write(0, col_num, value, header)
            ws.freeze_panes(1, 0)
            if len(data.columns):
                ws.autofilter(0, 0, max(len(data), 1), len(data.columns)-1)
                ws.set_column(0, len(data.columns)-1, 24, wrap)
        ws = writer.sheets["Summary"]
        ws.write("A1", "Annotation summary", title)
        for col_num, value in enumerate(summary.columns):
            ws.write(1, col_num, value, header)
        for col_num, value in enumerate(by_annotator.columns):
            ws.write(8, col_num, value, header)
        ws.set_column("A:D", 28)
        chart = workbook.add_chart({"type": "column"})
        chart.add_series({"name": "Final labels", "categories": "=Summary!$A$3:$A$5", "values": "=Summary!$B$3:$B$5", "data_labels": {"value": True}})
        chart.set_title({"name": "YES / NO / MAYBE"})
        chart.set_legend({"none": True})
        ws.insert_chart("F2", chart)
    return output.getvalue()

# -----------------------------
# Interface
# -----------------------------

def render_post_box(title: str, text: str):
    st.subheader(title)
    safe_text = str(text).replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(f"""
<div style="border:1px solid #B8C4D8;border-radius:10px;padding:18px;min-height:160px;background:#F7F9FC;font-size:1.08rem;white-space:pre-wrap;">{safe_text}</div>
""", unsafe_allow_html=True)

def choose_current_post(posts: list[dict[str, Any]], progress: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not posts:
        return None
    progress_by_post = {p["post_id"]: p for p in progress}
    incomplete = [p for p in progress if not p.get("completed")]
    if incomplete:
        incomplete_post_id = incomplete[0]["post_id"]
        found = next((post for post in posts if post["post_id"] == incomplete_post_id), None)
        if found:
            return found
    for post in posts:
        p = progress_by_post.get(post["post_id"])
        if not p or not p.get("completed"):
            return post
    return None

def annotator_page():
    st.title("Meaning Preservation Annotation")
    st.write("Enter your assigned annotator ID. Your progress is saved automatically after each decision.")
    posts = load_posts()
    if not posts:
        st.warning("No posts have been uploaded yet. Ask the researcher to add posts in the Admin page.")
        return
    annotator_id = st.text_input("Annotator ID", placeholder="For example: A01").strip()
    if not annotator_id:
        st.info("Enter your annotator ID to begin or resume.")
        return
    progress = load_progress(annotator_id)
    completed_count = sum(1 for p in progress if p.get("completed"))
    total_posts = len(posts)
    st.progress(completed_count / total_posts if total_posts else 0)
    st.caption(f"{completed_count} of {total_posts} posts completed for annotator {annotator_id}.")
    current_post = choose_current_post(posts, progress)
    if current_post is None:
        st.success("All posts are completed. Thank you.")
        return
    progress_by_post = {p["post_id"]: p for p in progress}
    current_progress = progress_by_post.get(current_post["post_id"], {})
    current_step = int(current_progress.get("current_step") or 1)
    current_step = max(1, min(current_step, len(STEP_DEFINITIONS)))
    st.divider()
    st.markdown(f"### Current post: `{current_post['post_id']}`")
    left, right = st.columns(2)
    with left:
        render_post_box("Original post", current_post["original_post"])
    with right:
        render_post_box("Simplified post", current_post["simplified_post"])
    step_answers = load_step_answers(annotator_id, current_post["post_id"])
    if step_answers:
        with st.expander("Saved previous step answers"):
            for answer in step_answers:
                st.write(f"**Step {answer['step_number']}:** {answer['decision']}")
    st.divider()
    step = STEP_DEFINITIONS[current_step - 1]
    st.markdown(f"## Step {step['number']}: {step['title']}")
    st.write(step["quick"])
    with st.expander("Show detailed guidance and examples"):
        st.markdown(step["guidance"])
    option_labels = [option["label"] for option in step["options"]]
    with st.form(key=f"form_{annotator_id}_{current_post['post_id']}_{current_step}"):
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
        save_step_answer(annotator_id, current_post["post_id"], current_step, selected, reason, comment)
        if outcome == "CONTINUE":
            save_progress(annotator_id, current_post["post_id"], current_step + 1, False, comment=comment)
            st.success("Saved. Moving to the next step.")
        else:
            save_progress(annotator_id, current_post["post_id"], current_step, True, final_label=outcome, terminal_reason=reason, terminal_step=current_step, comment=comment)
            if outcome == "YES":
                st.success(f"Final label saved: YES — {reason}")
            elif outcome == "NO":
                st.error(f"Final label saved: NO — {reason}")
            else:
                st.warning(f"Final label saved: MAYBE — {reason}")
        st.rerun()
    with st.expander("Need to restart this post?"):
        st.write("Use this only if you made a mistake on the current post.")
        if st.button("Reset this post for my annotator ID"):
            reset_annotation(annotator_id, current_post["post_id"])
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
    tab_upload, tab_dashboard, tab_export = st.tabs(["Upload posts", "Dashboard", "Export"])
    with tab_upload:
        st.subheader("Upload posts")
        st.write("Upload a CSV or XLSX file. Required information: original post and simplified post. A post ID column is strongly recommended.")
        uploaded_file = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"])
        if uploaded_file:
            df = read_uploaded_dataset(uploaded_file)
            st.write("Preview")
            st.dataframe(df.head(), use_container_width=True)
            columns = list(df.columns)
            id_guess = guess_column(df, ["post_id", "id", "item_id", "row_id"])
            original_guess = guess_column(df, ["original_post", "original", "source", "source_text", "post"])
            simplified_guess = guess_column(df, ["simplified_post", "simplified", "target", "target_text", "simplification"])
            id_col = st.selectbox("Post ID column", columns, index=columns.index(id_guess) if id_guess in columns else 0)
            original_col = st.selectbox("Original post column", columns, index=columns.index(original_guess) if original_guess in columns else 0)
            simplified_col = st.selectbox("Simplified post column", columns, index=columns.index(simplified_guess) if simplified_guess in columns else min(1, len(columns)-1))
            if original_col == simplified_col:
                st.error("Original and simplified post columns must be different.")
            elif st.button("Import / update posts in Supabase"):
                count = import_posts_to_supabase(df, id_col, original_col, simplified_col)
                st.success(f"Imported or updated {count} posts.")
                st.cache_data.clear()
        posts = load_posts()
        st.subheader("Current posts in database")
        st.write(f"{len(posts)} posts available.")
        if posts:
            st.dataframe(pd.DataFrame(posts).head(20), use_container_width=True)
    with tab_dashboard:
        st.subheader("Summary")
        client = get_supabase_client()
        progress = pd.DataFrame(client.table("annotation_progress").select("*").execute().data or [])
        posts = pd.DataFrame(load_posts())
        if progress.empty:
            st.info("No annotations yet.")
        else:
            completed = progress[progress["completed"].eq(True)]
            counts = completed["final_label"].value_counts().reindex(LABELS, fill_value=0)
            total_completed = int(counts.sum())
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("YES", int(counts["YES"]), f"{(counts['YES']/total_completed*100):.1f}%" if total_completed else "0%")
            c2.metric("NO", int(counts["NO"]), f"{(counts['NO']/total_completed*100):.1f}%" if total_completed else "0%")
            c3.metric("MAYBE", int(counts["MAYBE"]), f"{(counts['MAYBE']/total_completed*100):.1f}%" if total_completed else "0%")
            c4.metric("Completed annotations", total_completed)
            st.bar_chart(pd.DataFrame({"count": [int(counts[label]) for label in LABELS]}, index=LABELS))
            by_annotator = progress.groupby("annotator_id").agg(started=("post_id", "count"), completed=("completed", "sum")).reset_index()
            st.subheader("Progress by annotator")
            st.dataframe(by_annotator, use_container_width=True)
            if not posts.empty:
                st.caption(f"Posts in database: {len(posts)}")
    with tab_export:
        st.subheader("Export results")
        st.write("Download all annotations, step answers and a summary table as an Excel workbook.")
        st.download_button("Download XLSX results", data=build_export(), file_name="meaning_preservation_annotation_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

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
