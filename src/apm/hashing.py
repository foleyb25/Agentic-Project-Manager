"""Content hashes and action fingerprints — the dedup law (docs/PM_DATASTORE.md).

comment content_hash: sha256 of the verbatim comment body (edit detection).
action fingerprint:   sha256("type|roles|feature_area|normalized_summary")
                      (duplicate-issue prevention; roles sorted, summary
                      normalized so independent reports of the same problem
                      collide).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize_summary(summary: str) -> str:
    """Lowercase, alnum runs only, hyphen-joined: 'Arc too high!' -> 'arc-too-high'."""
    tokens = re.findall(r"[a-z0-9]+", summary.lower())
    return "-".join(tokens)


def fingerprint(
    action_type: str, roles: list[str], feature_area: str, summary: str
) -> tuple[str, str]:
    """Return (sha256_fingerprint, human_readable_key)."""
    key = "|".join(
        [
            action_type.strip().lower(),
            ",".join(sorted(r.strip().lower() for r in roles)),
            feature_area.strip().lower(),
            normalize_summary(summary),
        ]
    )
    return sha256_text(key), key
