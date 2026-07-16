"""Idempotent GitHub provisioning from config: label taxonomy + active milestone."""

from __future__ import annotations

from .config import Config
from .gh import current_repo, gh, gh_json

# stable palette per label dimension; values cycle if a dimension has more entries
DIMENSION_COLORS = {
    "role": ["5319e7", "e99695", "1d76db", "0e8a16", "fbca04", "d93f0b", "bfd4f2"],
    "ver": ["c5def5"],
    "type": ["a2eeef", "d73a4a", "bfdadc", "7057ff", "ededed"],
}
DEFAULT_COLORS = ["c2e0c6", "f9d0c4", "d4c5f9"]


def bootstrap(cfg: Config, repo: str | None = None) -> None:
    repo = repo or current_repo()

    def make_label(name: str, color: str, description: str) -> None:
        gh(
            "label", "create", name,
            "--repo", repo, "--force",
            "--color", color, "--description", description[:100],
        )
        print(f"label: {name}")

    # role:* from configured roles (+ pm itself)
    role_colors = DIMENSION_COLORS["role"]
    make_label("role:pm", role_colors[0], "Project manager / orchestration")
    for i, role in enumerate(cfg.roles, start=1):
        make_label(
            f"role:{role.name}",
            role_colors[i % len(role_colors)],
            role.title or role.name,
        )

    # every other dimension straight from config.labels
    for dim, values in cfg.labels.items():
        colors = DIMENSION_COLORS.get(dim, DEFAULT_COLORS)
        for i, value in enumerate(values):
            make_label(f"{dim}:{value}", colors[i % len(colors)], f"{dim} {value}")

    # active milestone
    if cfg.milestone:
        existing = gh_json("api", f"repos/{repo}/milestones?state=all") or []
        if any(m.get("title") == cfg.milestone for m in existing):
            print(f"milestone exists: {cfg.milestone}")
        else:
            gh(
                "api", f"repos/{repo}/milestones", "-X", "POST",
                "-f", f"title={cfg.milestone}",
                "-f",
                "description="
                f"Active milestone for {cfg.project_name}. "
                f"Spec: {cfg.active_version_spec or cfg.spec}",
            )
            print(f"milestone created: {cfg.milestone}")

    print("bootstrap complete.")
