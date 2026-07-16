import textwrap

import pytest

from apm.config import ConfigError, load_config

SAMPLE = textwrap.dedent("""
    tailored: true
    project:
      name: Test Project
      root: ".."
      spec: SPEC.md
      active_version_spec: SPECS/SPEC_V0.md
      workspace: App/
    runner:
      engine: cli
      consult_model: claude-haiku-4-5-20251001
      max_turns: 99
      max_budget_usd: 5
    ledger:
      backend: jsonfile
    roles:
      - name: qa
        title: QA
        extra_tools: ["Bash(gh issue create:*)"]
      - name: ge
        title: Engineer
        model: claude-sonnet-5
    routing:
      - prefixes: [tests, perf]
        primary: qa
        co: [ge]
    labels:
      ver: [v0, v1]
      type: [feature, bug]
    milestones:
      active: "v0 — Start"
""")


@pytest.fixture
def cfg(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "apm.yaml").write_text(SAMPLE, encoding="utf-8")
    return load_config(tmp_path / "config" / "apm.yaml")


def test_project_and_runner(cfg):
    assert cfg.tailored
    assert cfg.project_name == "Test Project"
    assert cfg.engine == "cli"
    assert cfg.max_turns == 99
    assert cfg.max_budget_usd == 5.0
    assert cfg.ledger_backend == "jsonfile"


def test_roles_and_lookup(cfg):
    qa = cfg.role("qa")
    assert qa is not None and qa.extra_tools == ["Bash(gh issue create:*)"]
    assert cfg.role("ge").model == "claude-sonnet-5"
    assert cfg.role("nope") is None


def test_routing_table_renders(cfg):
    md = cfg.routing_table_md()
    assert "`tests.*`" in md and "qa" in md and "ge" in md


def test_env_override_backend(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "apm.yaml").write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("APM_LEDGER_BACKEND", "supabase")
    cfg = load_config(tmp_path / "config" / "apm.yaml")
    assert cfg.ledger_backend == "supabase"


def test_missing_config_raises():
    with pytest.raises(ConfigError):
        load_config("does/not/exist.yaml")
