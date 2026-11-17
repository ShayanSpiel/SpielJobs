-- Additive persistence foundation. Apply only to the confirmed SpielJobs project.
-- The runtime currently uses device-local history; these tables do not imply
-- accounts, cross-device sync, or feed ingestion have already been implemented.
begin;
create table if not exists public.job_sources (
  id text primary key,
  name text not null,
  homepage_url text not null,
  adapter text not null,
  enabled boolean not null default true,
  config jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
create table if not exists public.job_companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  canonical_domain text unique,
  logo_url text,
  created_at timestamptz not null default now()
);
create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.job_companies(id),
  title text not null,
  normalized_title text not null,
  location text,
  workplace_type text check (workplace_type in ('onsite','hybrid','remote')),
  first_seen_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  search_document tsvector generated always as (to_tsvector('simple', normalized_title)) stored
);
create index if not exists jobs_search_idx on public.jobs using gin(search_document);
create index if not exists jobs_feed_idx on public.jobs(first_seen_at desc,id);
create table if not exists public.job_offers (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.jobs(id) on delete cascade,
  source_id text not null references public.job_sources(id),
  external_id text not null,
  canonical_url text not null check (canonical_url ~ '^https?://'),
  description text,
  compensation jsonb,
  employment_type text,
  status text not null default 'unknown' check (status in ('open','closed','unknown')),
  status_evidence text,
  posted_at timestamptz,
  checked_at timestamptz not null default now(),
  content_hash text,
  unique(source_id,external_id),
  unique(source_id,canonical_url)
);
create index if not exists job_offers_job_idx on public.job_offers(job_id);
create index if not exists job_offers_freshness_idx on public.job_offers(checked_at desc);
create table if not exists public.job_search_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  query text not null check (length(query) <= 2000),
  plan jsonb not null default '{}'::jsonb,
  source_report jsonb not null default '[]'::jsonb,
  result_ids uuid[] not null default '{}',
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '30 days')
);
create index if not exists job_search_runs_owner_idx on public.job_search_runs(user_id,created_at desc);
create table if not exists public.saved_jobs (
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid not null references public.jobs(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key(user_id,job_id)
);
alter table public.job_sources enable row level security;
alter table public.job_companies enable row level security;
alter table public.jobs enable row level security;
alter table public.job_offers enable row level security;
alter table public.job_search_runs enable row level security;
alter table public.saved_jobs enable row level security;
-- Public listing reads. Adapter configuration and private search history remain
-- server-only until an authenticated API and consent flow are implemented.
create policy jobs_public_read on public.jobs for select to anon, authenticated using (true);
create policy offers_public_read on public.job_offers for select to anon, authenticated using (true);
create policy companies_public_read on public.job_companies for select to anon, authenticated using (true);
create policy searches_owner_read on public.job_search_runs for select to authenticated using ((select auth.uid())=user_id);
create policy searches_owner_delete on public.job_search_runs for delete to authenticated using ((select auth.uid())=user_id);
create policy saved_owner_all on public.saved_jobs for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
revoke all on public.job_sources,public.job_companies,public.jobs,public.job_offers,public.job_search_runs,public.saved_jobs from anon,authenticated;
grant select on public.job_companies,public.jobs,public.job_offers to anon,authenticated;
grant select,delete on public.job_search_runs to authenticated;
grant select,insert,delete on public.saved_jobs to authenticated;
commit;
