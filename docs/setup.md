# One-time setup checklist (per project)

Prerequisites: `git`, Claude Code (`claude`). That's it — no Python, no gh
CLI, no npm packages of your own (the Supabase MCP server runs via npx, which
ships with Node/Claude Code's runtime requirements).

## 1. Wire APM into the project

- [ ] Fork the template (`foleyb25/Agentic-Project-Manager`) for this project.
- [ ] `git submodule add git@github.com:<you>/Agentic-Project-Manager-<project>.git AgenticProjectManager`
- [ ] Write `SPEC.md` at the project root.
- [ ] `claude --plugin-dir AgenticProjectManager` → `/tailor` → review
      `PROJECT.md` + `agents/*.md` → commit + push to the fork → bump the
      submodule pin.
- [ ] Copy `workflows/pm.yml` → project repo `.github/workflows/pm.yml`.

## 2. Ledger (Supabase)

- [ ] Create a Supabase project; apply `supabase/migrations/*.sql` (SQL
      editor; idempotent).
- [ ] Create a management access token (Account → Access Tokens) — this is
      what the Supabase MCP uses. Note the project ref.
- [ ] Keep this Supabase project dedicated to the ledger — the management
      token can run arbitrary SQL, so don't co-locate production data.

## 3. Tokens & secrets

Local: `cp .env.example .env` inside the plugin dir and fill in
`GITHUB_MCP_TOKEN`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF`
(`bin/pm-local.*` loads it).

CI (project repo → Settings → Secrets → Actions):
- [ ] `ANTHROPIC_API_KEY`
- [ ] `GITHUB_MCP_TOKEN` — a PAT with issues read/write on the project repo
      (fine-grained recommended). The Actions-issued `GITHUB_TOKEN` cannot
      authenticate to the hosted GitHub MCP.
- [ ] `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF`

## 4. Bootstrap + acceptance test

- [ ] `/bootstrap` (labels + active milestone; idempotent).
- [ ] Actions → pm-agent → Run workflow. Verify: ≥1 correctly-labeled issue
      from spec seeds; matching `ticket_log` rows with the run's `run_id`
      (Supabase Table editor).
- [ ] Comment `@pm <feedback>` on an issue. Verify: workflow fires; on-thread
      PM reply; 👀 reaction; `comment_log` row.
- [ ] Standalone consultant check: in a plugin-loaded session, ask the PM to
      consult one role on a trivial topic and confirm the JSON report shape
      (`schemas/consultation.json`).

## Known limitations

- PR *review* (diff-line) comments aren't swept — only issue/PR conversation
  comments. Mention `@pm` in the PR conversation instead.
- GitHub cron can drift minutes and pauses after 60 days of repo inactivity.
- Domain MCP servers (e.g. an editor) are only reachable where they run;
  elsewhere they're marked failed and consults proceed from code+docs+web.
