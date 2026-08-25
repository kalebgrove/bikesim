-- Run this in the Supabase SQL editor to create the simulations table.
-- Idempotent: safe to run multiple times.

create table if not exists public.simulations (
  id         uuid primary key default gen_random_uuid(),
  sim_id     text unique not null,
  route_id   bigint,
  route_name text,
  rider_ref  text,
  status     text not null,
  stop_reason text,
  config     jsonb not null,
  summary    jsonb,
  file_path  text,
  created_at  timestamptz not null default now(),
  completed_at timestamptz
);

-- Enable RLS so only the service role (server-side) can read/write.
alter table public.simulations enable row level security;
