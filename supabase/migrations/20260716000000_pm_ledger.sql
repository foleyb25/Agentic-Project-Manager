-- PM ledger — comment log, dedup fingerprints, sync cursor, ticket log.
-- Source of truth for schema + protocol: PM_DATASTORE.md (repo root).
-- Access policy: PM agent writes via service-role key (bypasses RLS);
-- every other agent/human reads via anon key under SELECT-only RLS.

-- 3.1 comment_log — idempotency ledger + PM working memory per comment
create table if not exists comment_log (
  comment_id         bigint primary key,      -- GitHub comment ID → idempotency key
  issue_number       integer not null,        -- issue/PR the comment lives on
  comment_url        text    not null,        -- deep link for humans reading the ledger
  author             text    not null,
  content_hash       text    not null,        -- sha256(comment body) → detects EDITS
  analysis_note      text    not null,        -- PM's statement about the comment
  forward_actions    text    not null,        -- what the PM did / will do
  created_refs       jsonb,                   -- issues/PRs opened because of this, e.g. ["#42"]
  status             text    not null
                       check (status in ('logged','actioned','escalated','no_action')),
  processed_at       timestamptz not null default now(),
  superseded_by_edit boolean not null default false
);
create index if not exists idx_comment_issue on comment_log(issue_number);

-- 3.2 action_fingerprints — duplicate-issue prevention
create table if not exists action_fingerprints (
  fingerprint text primary key,  -- sha256(type|role|feature_area|normalized_summary)
  issue_ref   text not null,     -- the canonical open issue for this problem
  created_at  timestamptz not null default now()
);

-- 3.3 sync_cursor — incremental comment polling (updated_at, not created_at)
create table if not exists sync_cursor (
  scope        text primary key,       -- 'repo' (or per-issue if volume demands)
  last_seen_at timestamptz not null
);

-- 3.4 ticket_log — receipt of every ticket the PM writes, per run
create table if not exists ticket_log (
  issue_number  integer primary key,   -- the GitHub issue created
  title         text    not null,
  labels        jsonb   not null,      -- ["role:ge","ver:v0","type:feature"]
  source        text    not null
                  check (source in ('spec_seed','comment','consultation','qa_bug_sweep')),
  source_ref    text,                  -- seed #, comment_id, or consultation topic
  fingerprint   text references action_fingerprints(fingerprint),
  run_id        text    not null,      -- run identifier (timestamp-based)
  created_at    timestamptz not null default now()
);
create index if not exists idx_ticket_run on ticket_log(run_id);

-- RLS: anon/authenticated get SELECT only; writes require the service-role key
-- (service role bypasses RLS entirely, so no write policies are defined).
alter table comment_log         enable row level security;
alter table action_fingerprints enable row level security;
alter table sync_cursor         enable row level security;
alter table ticket_log          enable row level security;

drop policy if exists "read-only for all agents" on comment_log;
create policy "read-only for all agents" on comment_log
  for select to anon, authenticated using (true);

drop policy if exists "read-only for all agents" on action_fingerprints;
create policy "read-only for all agents" on action_fingerprints
  for select to anon, authenticated using (true);

drop policy if exists "read-only for all agents" on sync_cursor;
create policy "read-only for all agents" on sync_cursor
  for select to anon, authenticated using (true);

drop policy if exists "read-only for all agents" on ticket_log;
create policy "read-only for all agents" on ticket_log
  for select to anon, authenticated using (true);
