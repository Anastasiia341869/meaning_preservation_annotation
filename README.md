# Meaning Preservation Annotation App

This is the updated Streamlit + Supabase annotation interface using the revised 10-step decision tree.

## Files for GitHub

Upload these files to the root of your GitHub repository:

- `app.py`
- `requirements.txt`
- `supabase_schema.sql`
- `.gitignore`
- `README.md`
- `sample_posts.csv` optional

Do not upload any real `.streamlit/secrets.toml` file to GitHub.

## Streamlit secrets

Add these in Streamlit Community Cloud under App settings → Secrets:

```toml
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_KEY = "your_supabase_anon_public_key"
ADMIN_PASSWORD = "choose_a_private_admin_password"
```

## Supabase setup

1. Create a Supabase project.
2. Open SQL Editor.
3. Copy and run the contents of `supabase_schema.sql`.
4. Deploy the Streamlit app.
5. Use the Researcher admin page to upload posts.

## Dataset format

Recommended columns:

- `post_id`
- `original_post`
- `simplified_post`

The admin upload page lets you map different column names.

## Saved progress

The app writes each decision to Supabase immediately. Refreshing the browser or closing the page should not delete completed progress, provided the annotator returns with the same annotator ID.
