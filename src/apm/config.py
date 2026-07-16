"""Load and validate config/apm.yaml (the tailored, per-project configuration).

Env overrides (for CI without config edits): APM_ENGINE, APM_LEDGER_BACKEND.
Secrets are never read here — they stay in the env of the code that uses them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# src/apm/config.py -> repo root is two levels up from src/
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "apm.yaml"


@dataclass
class Role:
    name: str
    title: str = ""
    # Per-role model override for consultations (cost lever); None = runner default
    model: str | None = None
    # Scoped write exceptions granted by config, e.g. "Bash(gh issue create:*)".
    # Consult sessions get READONLY_TOOLS + these. Never widen inside prompts.
    extra_tools: list[str] = field(default_factory=list)


@dataclass
class RoutingRule:
    prefixes: list[str]
    primary: str
    co: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class Config:
    tailored: bool
    project_name: str
    spec: str
    active_version_spec: str | None
    workspace: str | None
    conventions: str | None
    project_root: Path
    engine: str
    pm_model: str | None
    consult_model: str | None
    max_turns: int
    consult_max_turns: int
    max_budget_usd: float | None
    ledger_backend: str
    jsonfile_path: str
    roles: list[Role]
    routing: list[RoutingRule]
    labels: dict[str, list[str]]
    milestone: str | None
    repo_root: Path = REPO_ROOT

    def role(self, name: str) -> Role | None:
        for r in self.roles:
            if r.name == name:
                return r
        return None

    @property
    def apm_cmd(self) -> str:
        """How the PM (cwd = project root) invokes this package's CLI."""
        try:
            rel = self.repo_root.relative_to(self.project_root)
        except ValueError:
            rel = self.repo_root
        return f"uv run --project {rel.as_posix()} apm"

    def routing_table_md(self) -> str:
        if not self.routing:
            return "(no routing table configured — run /tailor)"
        lines = [
            "| Feature area (prefix) | Primary | Co-consult |",
            "|---|---|---|",
        ]
        for rule in self.routing:
            prefixes = ", ".join(f"`{p}.*`" for p in rule.prefixes)
            note = f" ({rule.note})" if rule.note else ""
            lines.append(
                f"| {prefixes}{note} | {rule.primary} | {', '.join(rule.co) or '—'} |"
            )
        return "\n".join(lines)


class ConfigError(RuntimeError):
    pass


def load_config(path: str | Path | None = None) -> Config:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if not cfg_path.exists():
        raise ConfigError(f"config not found: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    project = raw.get("project") or {}
    runner = raw.get("runner") or {}
    ledger = raw.get("ledger") or {}
    repo_root = cfg_path.resolve().parent.parent

    roles = [
        Role(
            name=r["name"],
            title=r.get("title", ""),
            model=r.get("model"),
            extra_tools=list(r.get("extra_tools") or []),
        )
        for r in (raw.get("roles") or [])
    ]
    routing = [
        RoutingRule(
            prefixes=list(r.get("prefixes") or []),
            primary=r["primary"],
            co=list(r.get("co") or []),
            note=r.get("note", ""),
        )
        for r in (raw.get("routing") or [])
    ]

    return Config(
        tailored=bool(raw.get("tailored", False)),
        project_name=project.get("name", "(untailored project)"),
        spec=project.get("spec", "SPEC.md"),
        active_version_spec=project.get("active_version_spec"),
        workspace=project.get("workspace"),
        conventions=project.get("conventions"),
        project_root=(repo_root / project.get("root", "..")).resolve(),
        engine=os.environ.get("APM_ENGINE", runner.get("engine", "cli")),
        pm_model=runner.get("pm_model"),
        consult_model=runner.get("consult_model"),
        max_turns=int(runner.get("max_turns", 150)),
        consult_max_turns=int(runner.get("consult_max_turns", 40)),
        max_budget_usd=(
            float(runner["max_budget_usd"])
            if runner.get("max_budget_usd") is not None
            else None
        ),
        ledger_backend=os.environ.get(
            "APM_LEDGER_BACKEND", ledger.get("backend", "supabase")
        ),
        jsonfile_path=ledger.get("jsonfile_path", ".apm/ledger.json"),
        roles=roles,
        routing=routing,
        labels={k: list(v) for k, v in (raw.get("labels") or {}).items()},
        milestone=(raw.get("milestones") or {}).get("active"),
        repo_root=repo_root,
    )
