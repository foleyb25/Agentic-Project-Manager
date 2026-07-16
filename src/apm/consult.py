"""Spawn one advisory consultation and print its JSON report to stdout.

Permissions are config law: consultants get READONLY_TOOLS plus whatever
`extra_tools` their config entry grants (e.g. QA's scoped issue-create) —
never what a prompt asks for. Model resolves role.model -> consult_model ->
session default, so consultations can run on a cheaper model than the PM.
"""

from __future__ import annotations

import json
import sys

from .config import Config
from .runner import make_runner

READONLY_TOOLS = ["Read", "Grep", "Glob", "WebFetch", "WebSearch"]


def run_consult(cfg: Config, role_name: str, topic: str) -> int:
    role = cfg.role(role_name)
    if role is None:
        names = ", ".join(r.name for r in cfg.roles) or "(none — run /tailor)"
        print(f"unknown role '{role_name}' — configured roles: {names}", file=sys.stderr)
        return 2
    role_file = cfg.repo_root / "agents" / "roles" / f"{role_name}.md"
    if not role_file.exists():
        print(f"missing charter: {role_file} — run /tailor", file=sys.stderr)
        return 2

    prompt = f"""Consultation request from the PM.

Topic: {topic}

Project: {cfg.project_name}
Program spec: {cfg.spec}
Active version spec: {cfg.active_version_spec or "see program spec"}
Workspace: {cfg.workspace or "repo root"}
Conventions doc: {cfg.conventions or "none"}

Investigate per your charter (read code/config, research as needed) and return
ONLY the JSON consultation report."""

    # Domain MCP servers (e.g. an editor-embedded inspection server) load from
    # consult.mcp_config; which tools a role may call still comes from its
    # config extra_tools grants (mcp__<server>__<tool> entries).
    mcp_config = (
        cfg.repo_root / cfg.consult_mcp_config if cfg.consult_mcp_config else None
    )
    runner = make_runner(cfg.engine)
    result = runner.run(
        prompt,
        system_prompt_file=role_file,
        allowed_tools=READONLY_TOOLS + role.extra_tools,
        max_turns=cfg.consult_max_turns,
        model=role.model or cfg.consult_model,
        json_schema_file=cfg.repo_root / "schemas" / "consultation.json",
        mcp_config=mcp_config,
        cwd=cfg.project_root,
        capture=True,
    )
    if result.structured is not None:
        print(json.dumps(result.structured, indent=2))
    else:
        # Schema enforcement failed or engine returned raw text — surface it
        print(result.output)
    return result.exit_code
