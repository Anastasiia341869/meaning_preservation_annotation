# Meaning Preservation Annotation App — Updated Version

This version includes:

1. Updated six-step decision tree.
2. Annotator email instead of annotator ID.
3. A YES / NO / MAYBE table for each annotator and an overall common table.
4. Researcher option to delete one annotator's results.
5. Annotator navigation to go back to previous posts.
6. Admin option to replace the dataset and delete existing annotations before importing a new dataset.

## Files to upload to GitHub

Replace or upload these files in your GitHub repository:

- `app.py`
- `requirements.txt`
- `runtime.txt`
- `supabase_schema.sql`
- `.gitignore`
- `README.md`

The file `new_tweet_selection.csv` is your ready-to-upload dataset. Do not put real or sensitive research data in GitHub if the repository is public. You can upload the dataset through the app's Researcher admin page instead.

## Streamlit secrets

In Streamlit Community Cloud → Manage app → Settings → Secrets, keep this format:

```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "your_supabase_secret_or_publishable_key"
ADMIN_PASSWORD = "your_private_admin_password"
```

For the most reliable app behaviour, use a Supabase secret key stored only in Streamlit Secrets. Do not upload it to GitHub.

## Supabase setup

Open Supabase → SQL Editor and run the contents of `supabase_schema.sql`.

If you already created the tables earlier, it is still safe to run this SQL again.

## Updating the app

1. Go to GitHub.
2. Open your repository.
3. Upload or replace `app.py`, `requirements.txt`, `runtime.txt`, `supabase_schema.sql`, `.gitignore`, and `README.md`.
4. Commit changes.
5. Go to Streamlit Community Cloud.
6. Open the app.
7. Reboot the app.

## Updating the dataset

1. Open the Streamlit app.
2. Go to Researcher admin.
3. Enter your admin password.
4. Open Upload / update posts.
5. Upload `new_tweet_selection.csv` or your XLSX file.
6. Select the original text column and the simplified text column.
7. Tick "Replace existing posts and delete all existing annotations" if you want a clean new dataset.
8. Click Import / update posts.

## Annotator workflow

Annotators now enter their email address. They can go to previous and next posts. Their progress is saved after every decision.

## Researcher dashboard

The dashboard includes:

- common YES / NO / MAYBE table;
- YES / NO / MAYBE by annotator email;
- individual annotator tables;
- export to XLSX.

## Deleting one annotator's results

Use Researcher admin → Delete annotator results. Select the email, type the email to confirm, then delete.
