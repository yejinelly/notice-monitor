-- Notice Monitor public-pilot schema. Apply in the Supabase SQL Editor.
alter default privileges for role postgres in schema public
revoke select, insert, update, delete on tables from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
revoke usage, select on sequences from anon, authenticated, service_role;

create table if not exists public.subscriptions (
  id bigint generated always as identity primary key,
  email text not null,
  site_name text not null,
  site_url text not null,
  site_type text not null default 'auto',
  keywords_json jsonb not null default '{"any": [], "all": []}'::jsonb,
  selectors_json jsonb not null default '{"item": "tr", "title": "a", "date": "time, .date"}'::jsonb,
  frequency text not null default 'schedule_10_14',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  last_checked_at timestamptz,
  unique (email, site_url)
);

create table if not exists public.seen_notices (
  subscription_id bigint not null references public.subscriptions(id) on delete cascade,
  fingerprint text not null,
  title text not null,
  link text not null,
  seen_at timestamptz not null default now(),
  primary key (subscription_id, fingerprint)
);

create index if not exists subscriptions_active_idx on public.subscriptions (active);

alter table public.subscriptions enable row level security;
alter table public.seen_notices enable row level security;

revoke all on table public.subscriptions from anon, authenticated;
revoke all on table public.seen_notices from anon, authenticated;

grant usage on schema public to service_role;
grant all privileges on table public.subscriptions to service_role;
grant all privileges on table public.seen_notices to service_role;
grant usage, select on all sequences in schema public to service_role;
