"""Pluggable ledger storage. Schema + protocol: docs/PM_DATASTORE.md.

All backends implement LedgerStore with exact-match filters and PK-merge
upserts, so every write is idempotent and a crashed run resumes from the
cursor with no duplicates.
"""

from __future__ import annotations

from typing import Any, Protocol

# table -> primary key column
TABLE_PKS: dict[str, str] = {
    "comment_log": "comment_id",
    "action_fingerprints": "fingerprint",
    "sync_cursor": "scope",
    "ticket_log": "issue_number",
}


class LedgerError(RuntimeError):
    pass


class LedgerStore(Protocol):
    def get(self, table: str, filters: dict[str, Any]) -> list[dict]: ...

    def upsert(self, table: str, rows: list[dict]) -> list[dict]: ...

    def patch(
        self, table: str, filters: dict[str, Any], fields: dict[str, Any]
    ) -> list[dict]: ...


def check_table(table: str) -> None:
    if table not in TABLE_PKS:
        raise LedgerError(
            f"'{table}' is not a ledger table ({', '.join(TABLE_PKS)})"
        )


def make_ledger(cfg) -> LedgerStore:
    if cfg.ledger_backend == "supabase":
        from .supabase import SupabaseLedger

        return SupabaseLedger()
    if cfg.ledger_backend == "jsonfile":
        from .jsonfile import JsonFileLedger

        return JsonFileLedger(cfg.repo_root / cfg.jsonfile_path)
    raise LedgerError(f"unknown ledger backend: {cfg.ledger_backend}")
