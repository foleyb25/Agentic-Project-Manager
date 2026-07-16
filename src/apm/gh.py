"""Thin wrapper over the `gh` CLI (auth comes from gh login or GH_TOKEN)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any


class GhError(RuntimeError):
    pass


def _gh_exe() -> str:
    exe = shutil.which("gh")
    if not exe:
        raise GhError("`gh` CLI not found on PATH")
    return exe


def gh(*args: str) -> str:
    proc = subprocess.run(
        [_gh_exe(), *args], capture_output=True, text=True, encoding="utf-8"
    )
    if proc.returncode != 0:
        raise GhError(f"gh {' '.join(args[:3])}… failed: {proc.stderr.strip()[:500]}")
    return proc.stdout


def gh_json(*args: str) -> Any:
    out = gh(*args)
    return json.loads(out) if out.strip() else None


def current_repo() -> str:
    """owner/repo from env (CI) or the local checkout."""
    for var in ("GH_REPO", "GITHUB_REPOSITORY"):
        if os.environ.get(var):
            return os.environ[var]
    return gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner").strip()


def comments_since(repo: str, since: str | None) -> list[dict]:
    """All issue/PR conversation comments, oldest-first by updated_at.

    Uses `updated` (not created) so edited comments resurface for re-analysis.
    Note: PR *review* (diff-line) comments are a different endpoint and are not
    swept — documented limitation.
    """
    endpoint = f"repos/{repo}/issues/comments?sort=updated&direction=asc&per_page=100"
    if since:
        endpoint += f"&since={since}"
    out = gh("api", endpoint, "--paginate")
    if not out.strip():
        return []
    # --paginate concatenates JSON arrays; gh joins them as ...][... in some
    # versions. Normalize by splitting safely.
    text = out.strip()
    if "][" in text:
        text = "[" + text.replace("][", ",").strip("[]") + "]"
    return json.loads(text)


def issue_number_from_comment(comment: dict) -> int | None:
    url = comment.get("issue_url") or ""
    try:
        return int(url.rstrip("/").rsplit("/", 1)[-1])
    except (ValueError, IndexError):
        return None
