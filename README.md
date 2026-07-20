# Meaning Preservation Annotation App — Clean Start v3

This is the clean-start version of the Streamlit + Supabase annotation app.

## Main features

- Annotators enter their email address.
- Annotators can go to previous and next posts.
- Researcher can upload or replace posts.
- Researcher can delete old uploaded posts.
- Researcher can delete one annotator's results.
- Dashboard shows:
  - YES / NO / MAYBE counts by annotator email;
  - overall common YES / NO / MAYBE counts;
  - exportable annotation results.

## Files for GitHub

Upload these files to the GitHub repository:

- app.py
- requirements.txt
- runtime.txt
- README.md

You may also upload:

- supabase_clean_reset.sql
- supabase_safe_setup.sql

Do not upload passwords or Supabase keys to GitHub.

## Supabase

If you want to start over completely, run:

supabase_clean_reset.sql

This deletes the old posts, old annotators and old annotations from the app tables, then recreates clean tables.

## Streamlit secrets

Keep secrets only in Streamlit:

SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-supabase-key"
ADMIN_PASSWORD = "your-admin-password"

## Dataset

Upload the dataset through the Researcher admin page in the Streamlit app.
If your GitHub repo is public, do not upload real research data to GitHub.


## v3.1 interface cleanup

- Removed the annotator YES / NO / MAYBE summary from the annotator page.
- Removed the top navigation area.
- Kept only a Previous post button at the bottom.
- Decision choices now use Yes:, No: and Maybe: instead of Uncertain.
