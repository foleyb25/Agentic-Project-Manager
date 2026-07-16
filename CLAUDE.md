# AgenticProjectManager — agent guide

This repo is a **Claude Code plugin**: the agentic PM pipeline for the project
that contains it as a submodule. No application code — skills, agents, hooks,
and MCP config only. The project's spec lives at `../SPEC.md`.

## First things first

- If `PROJECT.md` is missing, this instance is untailored — run **/tailor**
  (it reads `../SPEC.md` and generates `PROJECT.md` + `agents/*.md`).
- Sessions must load the plugin to see its skills/agents:
  `claude --plugin-dir AgenticProjectManager` from the project root.
- Never put project facts in `skills/pm-run/SKILL.md` — they belong in
  `PROJECT.md` and `agents/*.md`, so template updates merge cleanly.

## Layout & responsibilities

- `skills/pm-run/` — the PM charter + deterministic operating loop
  (`/pm-run <trigger> <run_id> [comment_id:N] [focus:...]`).
- `skills/tailor/`, `skills/bootstrap/` — setup procedures.
- `agents/*.md` — role consultants; **frontmatter `tools:` is the permission
  boundary** (read-only + explicit `mcp__server__tool` grants). Never widen a
  grant inside prose.
- `hooks/` — PreToolUse guards (e.g. `guard_sql.sh` blocks destructive SQL to
  the ledger). Test after editing: `bash hooks/guard_sql.sh <<< '{"tool_input":{"query":"drop table x"}}'`
  should exit 2.
- `.mcp.json` — github (hosted, `GITHUB_MCP_TOKEN` PAT), supabase
  (`SUPABASE_ACCESS_TOKEN` + `SUPABASE_PROJECT_REF`), plus tailored domain
  servers. `${VAR}` values expand from the environment.
- Secrets: env only, loaded locally from `.env` by `bin/pm-local.*`. Never in
  files, never in chat.

## Rules

- Ledger writes are idempotent upserts, always — a crashed run must resume
  from the cursor with no duplicates (protocol: `docs/PM_DATASTORE.md`).
- Role agents are advisory-only; write exceptions are explicit frontmatter
  grants justified by the project spec (and listed in PROJECT.md).
- Template-vs-tailoring discipline: generic changes go to the template repo
  (branch from the template remote's main, merge back); tailored changes stay
  in the fork.
