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

# Core tools every PM run gets; the GitHub/ledger surface is config-chosen.
PM_CORE_TOOLS = [
    "Task",
    "Read",
    "Grep",
    "Glob",
    "Write",
    "WebFetch",
    "WebSearch",
]
# cli surface: gh + apm ledger via Bash (hosts with gh installed, e.g. Actions)
PM_CLI_TOOLS = [
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

{_tool_surface_md(cfg)}
"""


def _tool_surface_md(cfg: Config) -> str:
    if cfg.pm_tool_surface != "mcp":
        return f"""## Tool surfaces (cli)
GitHub: `gh` commands as shown in your charter.

Ledger (backend: {cfg.ledger_backend}):
- read:   `{cfg.apm_cmd} ledger get <table> key=value ...`
- write:  `{cfg.apm_cmd} ledger upsert <table> '<json-row-or-array>'`
- patch:  `{cfg.apm_cmd} ledger patch <table> key=value --data '<json>'`
- hash:   `{cfg.apm_cmd} ledger hash --file <path>`
Tables: comment_log, action_fingerprints, sync_cursor, ticket_log."""

    return f"""## Tool surfaces (mcp) — overrides the concrete command examples in your charter
GitHub: use the `github` MCP tools — `issue_write` (create/update issues,
labels, milestone), `issue_read` (details/comments/labels), `add_issue_comment`
(on-thread replies; its `reaction` parameter posts the 👀 processed-marker),
plus list/search tools for dedup sweeps. Your charter's gh-command examples map
1:1 onto these.

Ledger: use the `supabase` MCP `execute_sql` tool. EVERY write must be an
idempotent upsert. Primary keys: comment_log=comment_id,
action_fingerprints=fingerprint, sync_cursor=scope, ticket_log=issue_number.
- read:   select * from sync_cursor where scope = 'repo';
- upsert (same pattern for every table — list all columns, update all
  non-PK columns from excluded):
    insert into sync_cursor (scope, last_seen_at)
    values ('repo', '2026-01-01T00:00:00Z')
    on conflict (scope) do update set last_seen_at = excluded.last_seen_at;
- escape single quotes in text values by doubling them; pass jsonb columns as
  '["#41"]'::jsonb.

Content hashes (the one CLI helper you keep):
`{cfg.apm_cmd} ledger hash --file <path>` or `--text "<fingerprint-key>"`."""


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
    mcp_config = None
    if cfg.pm_tool_surface == "mcp":
        # MCP surface: GitHub + ledger via servers from pm_mcp_config; the only
        # Bash grant left is the hash helper (part of this package, portable).
        allowed = PM_CORE_TOOLS + cfg.pm_mcp_tools + [f"Bash({apm_prefix} ledger hash:*)"]
        if cfg.pm_mcp_config:
            mcp_config = cfg.repo_root / cfg.pm_mcp_config
    else:
        allowed = PM_CORE_TOOLS + PM_CLI_TOOLS + [f"Bash({apm_prefix}:*)"]

    if dry_run:
        print("=== apm run --dry-run ===")
        print(f"engine: {cfg.engine} | surface: {cfg.pm_tool_surface} | cwd: {cfg.project_root}")
        print(f"mcp_config: {mcp_config}")
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
        mcp_config=mcp_config,
        cwd=cfg.project_root,
        capture=False,  # stream the PM's output into the console / CI log
    )
    return result.exit_code
