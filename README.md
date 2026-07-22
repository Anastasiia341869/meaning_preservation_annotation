# Meaning Preservation Annotation App — v3.2

This version includes two small interface fixes:

1. Annotators now have both bottom navigation buttons:
   - Previous post
   - Next post

   This lets an annotator return to a previous post and then move forward again without re-annotating the post.

2. The dashboard now has an inter-annotator agreement table by post.

   Instead of only showing the total number of YES / NO / MAYBE labels overall, it now shows how many annotators selected YES, NO and MAYBE for each individual post.

   Example:

   Post ID | YES | NO | MAYBE | Total annotations | Majority label | Agreement %
   1       | 2   | 1  | 0     | 3                 | YES            | 66.7

## How to update

Upload the new `app.py` to GitHub, commit the change, then reboot the Streamlit app.

You do not need to change Supabase for this update.
