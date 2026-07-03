-- Run this in Supabase SQL Editor before deploying the app.

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

-- For the simplest pilot setup, leave Row Level Security disabled.
-- If you later enable RLS, you must add policies that allow the Streamlit app to read/write these tables.
