"""Runners: how prompts reach Claude.

CliRunner (default) wraps `claude -p` — locally this uses your interactive
claude login (a subscription seat costs no API tokens); in CI it uses
ANTHROPIC_API_KEY. SdkRunner drives the Python Claude Agent SDK instead
(`uv sync --extra sdk`, runner.engine: sdk). Both accept identical arguments
so config can switch engines without touching call sites.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RunnerError(RuntimeError):
    pass


@dataclass
class RunnerResult:
    exit_code: int
    output: str
    structured: Any | None = None  # parsed structured_output when a schema was given


class CliRunner:
    def run(
        self,
        prompt: str,
        *,
        system_prompt_file: str | Path | None = None,
        allowed_tools: list[str] | None = None,
        max_turns: int | None = None,
        max_budget_usd: float | None = None,
        model: str | None = None,
        json_schema_file: str | Path | None = None,
        mcp_config: str | Path | None = None,
        cwd: str | Path | None = None,
        capture: bool = True,
    ) -> RunnerResult:
        exe = shutil.which("claude")
        if not exe:
            raise RunnerError(
                "`claude` CLI not found — npm install -g @anthropic-ai/claude-code"
            )
        # --strict-mcp-config: ONLY the servers we pass load; the project's own
        # .mcp.json (e.g. an editor server meant for humans) never leaks in.
        cmd = [exe, "-p", prompt, "--strict-mcp-config"]
        if mcp_config:
            cmd += ["--mcp-config", str(mcp_config)]
        if system_prompt_file:
            cmd += ["--append-system-prompt-file", str(system_prompt_file)]
        if allowed_tools:
            cmd += ["--allowedTools", ",".join(allowed_tools)]
        if max_turns:
            cmd += ["--max-turns", str(max_turns)]
        if max_budget_usd:
            cmd += ["--max-budget-usd", str(max_budget_usd)]
        if model:
            cmd += ["--model", model]
        if json_schema_file:
            schema = Path(json_schema_file).read_text(encoding="utf-8")
            cmd += ["--output-format", "json", "--json-schema", schema]

        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=capture,
            text=True,
            encoding="utf-8",
        )
        output = (proc.stdout or "") if capture else ""
        structured = None
        if json_schema_file and capture and proc.returncode == 0:
            try:
                structured = json.loads(output).get("structured_output")
            except (json.JSONDecodeError, AttributeError):
                structured = None
        if proc.returncode != 0 and capture:
            output = output or (proc.stderr or "")
        return RunnerResult(proc.returncode, output, structured)


class SdkRunner:
    """Claude Agent SDK engine (experimental — CliRunner is the default)."""

    def run(
        self,
        prompt: str,
        *,
        system_prompt_file: str | Path | None = None,
        allowed_tools: list[str] | None = None,
        max_turns: int | None = None,
        max_budget_usd: float | None = None,  # not enforced by SDK; documented
        model: str | None = None,
        json_schema_file: str | Path | None = None,
        mcp_config: str | Path | None = None,
        cwd: str | Path | None = None,
        capture: bool = True,
    ) -> RunnerResult:
        try:
            import anyio
            from claude_agent_sdk import ClaudeAgentOptions, query
        except ImportError as e:  # pragma: no cover
            raise RunnerError(
                "claude-agent-sdk not installed — run `uv sync --extra sdk` "
                "or set runner.engine: cli"
            ) from e

        system_prompt = None
        if system_prompt_file:
            system_prompt = {
                "type": "preset",
                "preset": "claude_code",
                "append": Path(system_prompt_file).read_text(encoding="utf-8"),
            }

        mcp_servers = None
        if mcp_config:
            # NOTE: unlike the CLI, the SDK does not expand ${VAR} placeholders
            # in server configs — use literal values or pre-expanded files here.
            mcp_servers = json.loads(
                Path(mcp_config).read_text(encoding="utf-8")
            ).get("mcpServers", {})

        async def _run() -> tuple[int, str]:
            options = ClaudeAgentOptions(
                system_prompt=system_prompt,
                allowed_tools=allowed_tools or [],
                max_turns=max_turns,
                model=model,
                cwd=str(cwd) if cwd else None,
                mcp_servers=mcp_servers or {},
            )
            chunks: list[str] = []
            exit_code = 0
            async for message in query(prompt=prompt, options=options):
                kind = type(message).__name__
                if kind == "ResultMessage":
                    result = getattr(message, "result", None)
                    if result:
                        chunks.append(result)
                    if getattr(message, "is_error", False):
                        exit_code = 1
                elif not capture and kind == "AssistantMessage":
                    for block in getattr(message, "content", []) or []:
                        text = getattr(block, "text", None)
                        if text:
                            print(text, flush=True)
            return exit_code, "\n".join(chunks)

        exit_code, output = anyio.run(_run)
        structured = None
        if json_schema_file and output:
            try:
                structured = json.loads(output)
            except json.JSONDecodeError:
                structured = None
        return RunnerResult(exit_code, output, structured)


def make_runner(engine: str):
    if engine == "cli":
        return CliRunner()
    if engine == "sdk":
        return SdkRunner()
    raise RunnerError(f"unknown runner engine: {engine}")
