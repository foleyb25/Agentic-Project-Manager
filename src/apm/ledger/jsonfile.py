"""Zero-service ledger backend: one JSON file, tables keyed by primary key.

Good for local runs and small projects. In CI, persist the file across runs
with actions/cache (see workflows/pm.yml). Not safe for concurrent writers —
the PM workflow's concurrency group already guarantees a single writer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import TABLE_PKS, LedgerError, check_table


class JsonFileLedger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, dict[str, dict]]:
        if not self._path.exists():
            return {t: {} for t in TABLE_PKS}
        data = json.loads(self._path.read_text(encoding="utf-8"))
        for t in TABLE_PKS:
            data.setdefault(t, {})
        return data

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)

    @staticmethod
    def _matches(row: dict, filters: dict[str, Any]) -> bool:
        # PK values arrive as strings from the CLI; compare loosely.
        return all(str(row.get(k)) == str(v) for k, v in filters.items())

    def get(self, table: str, filters: dict[str, Any]) -> list[dict]:
        check_table(table)
        rows = self._load()[table].values()
        return [r for r in rows if self._matches(r, filters)]

    def upsert(self, table: str, rows: list[dict]) -> list[dict]:
        check_table(table)
        pk = TABLE_PKS[table]
        data = self._load()
        out = []
        for row in rows:
            if pk not in row:
                raise LedgerError(f"upsert into {table} requires '{pk}'")
            key = str(row[pk])
            merged = {**data[table].get(key, {}), **row}
            data[table][key] = merged
            out.append(merged)
        self._save(data)
        return out

    def patch(
        self, table: str, filters: dict[str, Any], fields: dict[str, Any]
    ) -> list[dict]:
        check_table(table)
        if not filters:
            raise LedgerError("patch requires at least one filter")
        data = self._load()
        out = []
        for key, row in data[table].items():
            if self._matches(row, filters):
                row.update(fields)
                data[table][key] = row
                out.append(row)
        self._save(data)
        return out
