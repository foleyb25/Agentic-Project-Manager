# PM_DATASTORE — Comment Ledger & Action Log

**Owner:** PM agent (sole writer) · **Readers:** all agents, humans
**Status:** v2 — implemented by `src/apm/ledger/` (backend-pluggable: the
Supabase design below is the default; `jsonfile` offers a zero-service local
backend with the same tables/PKs). The PM reads/writes via `apm ledger
get|upsert|patch|hash`; the processing protocol in §4 is transcribed into
`agents/pm.md` and partially pre-computed by `apm run`'s prefetch.

---

## 1. Purpose

An idempotency ledger and working memory for the PM agent:
1. Never analyze the same comment twice; never miss an edited one
2. Never open a duplicate issue for an already-tracked problem
3. Preserve the PM's analysis ("what did this comment mean, what did I do about
   it") as a queryable record that feeds weekly digests and gate reviews
4. Log every ticket written per cron run — an audit trail of why each issue
   exists and what each PM run produced

## 2. Storage choice

**Supabase cloud (Postgres)** — decided.

Fits the stack you already run, survives any single machine, and gives free
extras that matter here: a queryable dashboard over the ledger (Supabase Studio,
no build needed), row-level security to enforce write discipline, and REST/JS
client access so any agent or future tool can read it.

**Access policy (enforced with RLS, not convention):**
- **PM agent is the sole writer** — writes via the service-role key, held only
  in the PM's environment. No other agent gets that key.
- **Everything else reads** — humans via Studio; agents via anon/read-only key
  with RLS `SELECT`-only policies on all three tables.
- Keys live in agent env config, never in the repo.

## 3. Schema

### 3.1 `comment_log` — the core table (your four columns, hardened)

```sql
create table comment_log (
  comment_id         bigint primary key,      -- GitHub comment ID (globally unique) → idempotency key
  issue_number       integer not null,        -- issue/PR the comment lives on
  comment_url        text    not null,        -- deep link for humans reading the ledger
  author             text    not null,
  content_hash       text    not null,        -- sha256(comment body) → detects EDITS
  analysis_note      text    not null,        -- PM's statement about the comment
  forward_actions    text    not null,        -- what the PM did / will do (prose or JSON list)
  created_refs       jsonb,                   -- issues/PRs opened because of this, e.g. ["#42"]
  status             text    not null
                       check (status in ('logged','actioned','escalated','no_action')),
  processed_at       timestamptz not null default now(),
  superseded_by_edit boolean not null default false
);
create index idx_comment_issue on comment_log(issue_number);
```

Example row for the lob-pass comment:

| field | value |
|---|---|
| comment_id | 2214377105 |
| issue_number | 37 (PR: passing mechanics) |
| analysis_note | "Positive on throw mechanics overall and bullet passes specifically. Defect report on lob lead: arc apex too high, flight speed too slow. Merge proceeding; review requested." |
| forward_actions | "Opened tuning issue for lob arc params (GD feel targets + GE impl); linked PR #37; replied on-thread confirming." |
| created_refs | ["#41"] |
| status | actioned |

### 3.2 `action_fingerprints` — duplicate-ISSUE prevention

```sql
create table action_fingerprints (
  fingerprint text primary key,  -- sha256(type|role|feature_area|normalized_summary)
  issue_ref   text not null,     -- the canonical open issue for this problem
  created_at  timestamptz not null default now()
);
```

Before opening any comment-driven issue, the PM computes the fingerprint
(e.g. `tuning|gd,ge|passing.lob|arc-too-high-speed-too-slow`). On a hit, it
**appends the new report as a comment on the existing issue** instead of
creating a twin — so three playtesters reporting the lob problem produce one
issue with three linked reports, which is also better signal ("3 independent
reports" > 3 orphan tickets).

### 3.3 `sync_cursor` — incremental polling

```sql
create table sync_cursor (
  scope        text primary key,       -- 'repo' (or per-issue if volume demands)
  last_seen_at timestamptz not null    -- updated_at of newest processed comment
);
```

The PM polls GitHub for comments `updated > last_seen_at` only — cheap, and
using *updated* (not created) is what surfaces edited comments for re-check.
All writes use Postgres upserts (`insert … on conflict`), which preserves the
crash-safe idempotency guarantee (§4) in a cloud database exactly as it worked
locally.

### 3.4 `ticket_log` — record of every ticket the PM writes (per cron run)

```sql
create table ticket_log (
  issue_number  integer primary key,   -- the GitHub issue created
  title         text    not null,
  labels        jsonb   not null,      -- ["role:ge","ver:v0","type:feature"]
  source        text    not null
                  check (source in ('spec_seed','comment','consultation','qa_bug_sweep')),
  source_ref    text,                  -- seed #, comment_id, or consultation topic
  fingerprint   text references action_fingerprints(fingerprint),
  run_id        text    not null,      -- cron run identifier (timestamp-based)
  created_at    timestamptz not null default now()
);
create index idx_ticket_run on ticket_log(run_id);
```

Every cron run closes with one batch of `ticket_log` inserts — the run's
receipt. This gives you: an audit trail of *why* every ticket exists (which
seed, comment, or consultation produced it), per-run reviews ("what did the PM
do last night?" is one query on `run_id`), and the `qa_bug_sweep` source that
records QA-created bugs when the PM's dedup scan reconciles them.

## 4. Processing protocol (per comment)

1. Fetch comments since cursor.
2. `comment_id` in ledger?
   - **No** → new comment → analyze.
   - **Yes, hash matches** → skip (already handled).
   - **Yes, hash differs** → comment was **edited** → re-analyze; write a new
     analysis (mark old row `superseded_by_edit`); reconcile actions (edit may
     add a new defect or retract one).
3. Analyze → draft `analysis_note` + intended actions.
4. For each intended new issue: compute fingerprint → hit ⇒ comment on the
   canonical issue; miss ⇒ create issue, record fingerprint + `created_refs`.
5. Write the ledger row, reply on the original thread, **react 👀 to the
   comment** — a human-visible "processed" marker on GitHub itself, so you can
   spot a stalled PM at a glance without opening the database.
6. Advance cursor.

Idempotency guarantee: every step is safe to re-run — PK on `comment_id`,
fingerprint PK on actions, and the 👀 reaction is idempotent too. A crashed PM
resumes from the cursor with no duplicates.

## 5. Additional dedup layers (defense in depth)

- **GitHub-side belt-and-suspenders:** before creating from a fingerprint miss,
  run one GitHub search over open issues (`label:type:tuning "lob"`) — catches
  human-created issues the fingerprint table has never seen.
- **One-canonical-issue policy:** per feature-area parameter, at most one open
  `tuning` issue; new reports append. Enforced by fingerprint + PM charter.
- **PM replies are self-marking:** the PM's own on-thread reply quotes the
  ledger row ID, making processing visible and auditable in the thread itself.

## 6. What the ledger feeds

- **Weekly digest:** notable `analysis_note`s grouped by feature area; open
  `forward_actions` not yet closed.
- **Gate reviews:** the v4 kill/pivot review queries the ledger for the full
  analysis history per feature area — a longitudinal, quotable record of how
  the game has been feeling, not a vibe.
