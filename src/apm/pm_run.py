"""One PM run: prefetch state, compose the run prompt, invoke the runner.

The prefetch is the cost saver — comments since the cursor are fetched,
hashed, and checked against the ledger in Python, so the PM spends its turns
on judgment (analysis, tickets, replies) instead of discovery. If prefetch
fails (no gh, no ledger creds), the PM is told to fall back to the manual
protocol in its charter.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import gh
from .config import Config
from .hashing import sha256_text
from .ledger import make_ledger
from .runner import make_runner

# The PM's entire tool surface. Ledger writes go through `apm ledger` and
# GitHub writes through `gh` — both auditable, both idempotent.
PM_BASE_TOOLS = [
    "Task",
    "Read",
    "Grep",
    "Glob",
    "Write",
    "WebFetch",
    "WebSearch",
    "Bash(gh issue:*)",
    "Bash(gh api:*)",
    "Bash(gh search:*)",
    "Bash(gh label:*)",
]


def _prefetch_comments(cfg: Config, ledger, repo: str, state_dir: Path) -> dict:
    cursor_rows = ledger.get("sync_cursor", {"scope": "repo"})
    since = cursor_rows[0]["last_seen_at"] if cursor_rows else None
    comments = gh.comments_since(repo, since)
    bodies_dir = state_dir / "comments"
    bodies_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for c in comments:
        body = c.get("body") or ""
        content_hash = sha256_text(body)
        body_file = bodies_dir / f"{c['id']}.md"
        body_file.write_text(body, encoding="utf-8")

        prior = ledger.get("comment_log", {"comment_id": c["id"]})
        if not prior:
            status = "new"
        elif prior[0].get("content_hash") == content_hash:
            status = "unchanged"
        else:
            status = "edited"

        entries.append(
            {
                "comment_id": c["id"],
                "issue_number": gh.issue_number_from_comment(c),
                "url": c.get("html_url"),
                "author": (c.get("user") or {}).get("login"),
                "author_type": (c.get("user") or {}).get("type"),
                "updated_at": c.get("updated_at"),
                "mentions_pm": "@pm" in (body or "").lower(),
                "content_hash": content_hash,
                "ledger_status": status,
                "body_file": str(body_file),
            }
        )
    return {"cursor": since, "comments": entries}


def build_run_context(
    cfg: Config,
    *,
    run_id: str,
    trigger: str,
    comment_id: str | None = None,
    issue_number: str | None = None,
    focus: str | None = None,
) -> Path:
    state_dir = cfg.repo_root / ".apm"
    state_dir.mkdir(parents=True, exist_ok=True)

    ctx: dict = {
        "run_id": run_id,
        "trigger": trigger,
        "triggering_comment_id": comment_id,
        "triggering_issue_number": issue_number,
        "focus": focus,
        "project": {
            "name": cfg.project_name,
            "spec": cfg.spec,
            "active_version_spec": cfg.active_version_spec,
            "workspace": cfg.workspace,
            "conventions": cfg.conventions,
        },
        "ledger_backend": cfg.ledger_backend,
        "prefetch": {},
    }
    try:
        repo = gh.current_repo()
        ctx["repo"] = repo
        ledger = make_ledger(cfg)
        ctx["prefetch"] = _prefetch_comments(cfg, ledger, repo, state_dir)
    except Exception as e:  # graceful: PM falls back to manual protocol
        ctx["repo"] = ctx.get("repo")
        ctx["prefetch"] = {"error": f"{type(e).__name__}: {e}"}

    path = state_dir / "run_context.json"
    path.write_text(json.dumps(ctx, indent=2), encoding="utf-8")
    return path


def compose_prompt(cfg: Config, context_path: Path, ctx: dict) -> str:
    roles_md = "\n".join(
        f"- `{r.name}` — {r.title or r.name}" for r in cfg.roles
    ) or "(no roles configured — everything routes to a decision escalation)"
    labels_md = " · ".join(
        f"`{dim}:{{{'|'.join(vals)}}}`" for dim, vals in cfg.labels.items()
    )
    trigger = ctx.get("trigger", "manual")
    trigger_note = {
        "issue_comment": (
            "Trigger is a comment event: process the triggering comment first "
            "(full protocol), then anything else past the cursor."
        ),
        "schedule": "Nightly run: full loop — spec seeds, comment sweep, consultations, tickets, ledger, replies.",
    }.get(trigger, "Manual run: full loop, honoring the focus note if present.")

    return f"""Execute one PM run per your charter (system prompt).

## Run context
- run_id: {ctx["run_id"]}
- trigger: {trigger} — {trigger_note}
- repo: {ctx.get("repo") or "(detect via gh)"}
- focus: {ctx.get("focus") or "none"}
- Full context (prefetched comments with hashes + ledger status, body files):
  Read {context_path}
  If `prefetch.error` is set there, fall back to manual fetch per your charter.

## Project
- name: {cfg.project_name}
- program spec (law): {cfg.spec}
- active version spec (build target): {cfg.active_version_spec or "see program spec"}
- workspace (the product source lives here): {cfg.workspace or "repo root"}
- shared conventions doc: {cfg.conventions or "none"}
- milestone: {cfg.milestone or "none configured"}
- labels: {labels_md}

## Consultation roster
{roles_md}

Consult with: `{cfg.apm_cmd} consult <role> "<feature.area>: <question>"`
(returns the role's JSON report on stdout).

Routing table (feature area -> consultants):
{cfg.routing_table_md()}

## Ledger (backend: {cfg.ledger_backend})
- read:   `{cfg.apm_cmd} ledger get <table> key=value ...`
- write:  `{cfg.apm_cmd} ledger upsert <table> '<json-row-or-array>'`
- patch:  `{cfg.apm_cmd} ledger patch <table> key=value --data '<json>'`
- hash:   `{cfg.apm_cmd} ledger hash --file <path>`
Tables: comment_log, action_fingerprints, sync_cursor, ticket_log.
"""


def run_pm(
    cfg: Config,
    *,
    run_id: str,
    trigger: str,
    comment_id: str | None = None,
    issue_number: str | None = None,
    focus: str | None = None,
    dry_run: bool = False,
) -> int:
    context_path = build_run_context(
        cfg,
        run_id=run_id,
        trigger=trigger,
        comment_id=comment_id,
        issue_number=issue_number,
        focus=focus,
    )
    ctx = json.loads(context_path.read_text(encoding="utf-8"))
    prompt = compose_prompt(cfg, context_path, ctx)

    apm_prefix = cfg.apm_cmd
    allowed = PM_BASE_TOOLS + [f"Bash({apm_prefix}:*)"]

    if dry_run:
        print("=== apm run --dry-run ===")
        print(f"engine: {cfg.engine} | cwd: {cfg.project_root}")
        print(f"allowedTools: {','.join(allowed)}")
        print(f"max_turns: {cfg.max_turns} | max_budget_usd: {cfg.max_budget_usd}")
        print("--- prompt ---")
        print(prompt)
        return 0

    runner = make_runner(cfg.engine)
    result = runner.run(
        prompt,
        system_prompt_file=cfg.repo_root / "agents" / "pm.md",
        allowed_tools=allowed,
        max_turns=cfg.max_turns,
        max_budget_usd=cfg.max_budget_usd,
        model=cfg.pm_model,
        cwd=cfg.project_root,
        capture=False,  # stream the PM's output into the console / CI log
    )
    return result.exit_code
