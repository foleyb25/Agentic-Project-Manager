# AgenticProjectManager — agent guide

This repo is the **agentic PM pipeline** for the project that contains it (as a
submodule). It is a Python/uv package plus prompt assets. The project's spec
lives at `../SPEC.md` (the project root).

## First things first

- If `config/apm.yaml` has `tailored: false` (or is missing roles), this
  instance has not been tailored yet — run the **/tailor** skill before
  anything else. It reads `../SPEC.md` and generates the role agents + config.
- Never hand-edit `agents/pm.md` to add project specifics — project knowledge
  belongs in `config/apm.yaml`, `agents/roles/*.md`, and the project's own
  `SPEC.md`/docs. The PM prompt stays generic so template updates merge
  cleanly.

## Commands

```bash
uv sync                                   # install (dev deps included)
uv run pytest                             # tests
uv run apm run --trigger manual           # one full PM run
uv run apm run --dry-run                  # print the composed prompt, don't call claude
uv run apm consult <role> "<area.topic>: question"
uv run apm ledger get|upsert|patch|hash   # ledger I/O (backend from config)
uv run apm bootstrap                      # GitHub labels + milestone
```

## Architecture (protocol in Python, judgment in prompts)

- `src/apm/pm_run.py` — composes the run prompt, prefetches comments + ledger
  state into `.apm/run_context.json`, invokes the runner.
- `src/apm/runner.py` — `CliRunner` wraps `claude -p` (default); `SdkRunner`
  uses claude-agent-sdk (`--extra sdk`). Both take the same arguments.
- `src/apm/ledger/` — `LedgerStore` protocol; `supabase.py` (PostgREST),
  `jsonfile.py` (local file). Add backends here, never in prompts.
- `src/apm/hashing.py` — content hashes + action fingerprints (dedup law).
- `agents/pm.md` — the PM charter. `agents/roles/*.md` — advisory role
  charters, consulted via `apm consult` (allowlists come from config, not
  the role file).

## Rules

- Role agents are **advisory-only**; write exceptions (e.g. QA filing bugs)
  are explicit `extra_tools` grants in `config/apm.yaml` — never widen an
  allowlist inside a prompt.
- Secrets come from env only (`ANTHROPIC_API_KEY`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_KEY`, `GH_TOKEN`) — never in config or code.
- Keep `apm run` idempotent: every ledger write is an upsert; a crashed run
  must resume from the cursor with no duplicates.
- After changing `src/`, run `uv run pytest` and a `--dry-run` before
  committing.
