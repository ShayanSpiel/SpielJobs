begin;

create table public.spieljobs_edge_quota (
  minute_start timestamptz primary key,
  hits integer not null check (hits between 1 and 40)
);
alter table public.spieljobs_edge_quota enable row level security;
revoke all on public.spieljobs_edge_quota from public, anon, authenticated;
grant select, insert, update, delete on public.spieljobs_edge_quota to service_role;

create function public.spieljobs_edge_take_slot() returns boolean
language plpgsql security invoker set search_path = '' as $$
declare
  bucket timestamptz := date_trunc('minute', now());
begin
  delete from public.spieljobs_edge_quota where minute_start < bucket - interval '1 hour';
  insert into public.spieljobs_edge_quota as quota (minute_start, hits)
    values (bucket, 1)
    on conflict (minute_start) do update set hits = quota.hits + 1 where quota.hits < 40;
  return found;
end;
$$;
revoke all on function public.spieljobs_edge_take_slot() from public, anon, authenticated;
grant execute on function public.spieljobs_edge_take_slot() to service_role;

commit;
