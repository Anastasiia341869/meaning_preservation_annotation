-- CLEAN RESET for the meaning preservation annotation app.
-- WARNING: this deletes ALL uploaded posts, annotations and annotator progress
-- in these three app tables.
-- Run this in Supabase SQL Editor when you want to start over.

drop table if exists step_answers cascade;
drop table if exists annotation_progress cascade;
drop table if exists posts cascade;

create table posts (
  post_id text primary key,
  display_order integer,
  original_post text not null,
  simplified_post text not null,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

create table annotation_progress (
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

create table step_answers (
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
-- Keep keys only in Streamlit Secrets, never in GitHub.
alter table posts disable row level security;
alter table annotation_progress disable row level security;
alter table step_answers disable row level security;

grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on table posts to anon, authenticated;
grant select, insert, update, delete on table annotation_progress to anon, authenticated;
grant select, insert, update, delete on table step_answers to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;
