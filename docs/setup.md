# One-time setup checklist (per project)

Prerequisites on the machine that tailors/tests locally: `git`, `gh`
(authenticated), `uv`, Node 18+ with `@anthropic-ai/claude-code` installed.
CI installs its own copies (see `workflows/pm.yml`).

## 1. Wire APM into the project

- [ ] `git submodule add https://github.com/<you>/AgenticProjectManager.git AgenticProjectManager`
- [ ] Write `SPEC.md` at the project root (vision, roadmap, roles, process).
- [ ] Open Claude Code in the project, run `/tailor`, review the generated
      `config/apm.yaml` + `agents/roles/*.md`, commit them to your APM fork,
      and update the submodule pin in the project repo.
- [ ] Copy `workflows/pm.yml` → project repo `.github/workflows/pm.yml`.

## 2. Ledger backend

**Supabase (default):**
- [ ] Create a Supabase project; apply `supabase/migrations/*.sql` (SQL editor
      or `supabase db push`).
- [ ] Note the project URL and **service_role** key — the PM's sole-writer
      credential. It goes only into CI secrets / the PM's local env.

**jsonfile (zero services):**
- [ ] Set `ledger.backend: jsonfile` in `config/apm.yaml`.
- [ ] In CI, uncomment the `actions/cache` block in the workflow so
      `.apm/ledger.json` persists across runs.

## 3. GitHub

- [ ] Repo → Settings → Secrets → Actions: `ANTHROPIC_API_KEY`
      (+ `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` for supabase backend).
- [ ] `uv run apm bootstrap` — labels + active milestone (idempotent).

## 4. Acceptance test

- [ ] Actions → pm-agent → Run workflow. Verify: ≥1 correctly-labeled issue
      from spec seeds; matching `ticket_log` rows with the run's `run_id`.
- [ ] Comment `@pm <some feedback>` on an issue. Verify: workflow fires; the
      PM replies on-thread; 👀 reaction lands; `comment_log` row exists.
- [ ] Standalone consultant check:
      `uv run apm consult <role> "<area>: sanity-check question"` returns a
      JSON report conforming to `schemas/consultation.json`.

## Known limitations

- PR *review* (diff-line) comments aren't swept — only issue/PR conversation
  comments. Mention `@pm` in the PR conversation instead.
- GitHub cron can drift minutes and pauses after 60 days of repo inactivity.
- The PM needs no repo write access beyond `issues: write` — it never pushes.
