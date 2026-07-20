-- Supabase setup for the Streamlit annotation app.
-- Run this in Supabase SQL Editor.
-- It is safe to run more than once.

create table if not exists posts (
  post_id text primary key,
  display_order integer,
  original_post text not null,
  simplified_post text not null,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

create table if not exists annotation_progress (
  id bigint generated always as identity primary key,
  annotator_id text not null,
  post_id text not null references posts(post_id) on delete cascade,
  current_step integer not null default 1,
  completed boolean default false,
  final_label text,
  terminal_reason text,
  terminal_step integer,
  comment text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  unique (annotator_id, post_id)
);

create table if not exists step_answers (
  id bigint generated always as identity primary key,
  annotator_id text not null,
  post_id text not null references posts(post_id) on delete cascade,
  step_number integer not null,
  decision text not null,
  reason text,
  comment text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  unique (annotator_id, post_id, step_number)
);

-- Simple pilot permissions.
-- If you use the Supabase secret key in Streamlit Secrets, these grants are usually enough.
-- Do not put any Supabase key in GitHub.
alter table posts disable row level security;
alter table annotation_progress disable row level security;
alter table step_answers disable row level security;

grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on table posts to anon, authenticated;
grant select, insert, update, delete on table annotation_progress to anon, authenticated;
grant select, insert, update, delete on table step_answers to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;
