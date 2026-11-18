create table public.spieljobs_search_quota (
  minute_start timestamptz not null,
  identity text not null,
  hits integer not null check (hits between 1 and 120),
  primary key (minute_start, identity)
);
alter table public.spieljobs_search_quota enable row level security;
revoke all on public.spieljobs_search_quota from public, anon, authenticated;
grant select, insert, update, delete on public.spieljobs_search_quota to service_role;

create function public.spieljobs_take_search_slot(client_hash text) returns boolean
language plpgsql security invoker set search_path = '' as $$
declare
  bucket timestamptz := date_trunc('minute', now());
  admitted boolean;
begin
  if client_hash is null or client_hash !~ '^[a-f0-9]{32}$' then
    return false;
  end if;
  delete from public.spieljobs_search_quota where minute_start < bucket - interval '10 minutes';
  insert into public.spieljobs_search_quota as quota (minute_start, identity, hits)
    values (bucket, client_hash, 1)
    on conflict (minute_start, identity) do update set hits = quota.hits + 1 where quota.hits < 10
    returning true into admitted;
  if admitted is not true then
    return false;
  end if;
  insert into public.spieljobs_search_quota as quota (minute_start, identity, hits)
    values (bucket, 'global', 1)
    on conflict (minute_start, identity) do update set hits = quota.hits + 1 where quota.hits < 120;
  return found;
end;
$$;
revoke all on function public.spieljobs_take_search_slot(text) from public, anon, authenticated;
grant execute on function public.spieljobs_take_search_slot(text) to service_role;
