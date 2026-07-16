"""Supabase (PostgREST) ledger backend.

Credentials from env only: SUPABASE_URL + SUPABASE_SERVICE_KEY (the PM is the
sole writer; the service key lives only in the PM's environment / CI secret).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from . import LedgerError, check_table


class SupabaseLedger:
    def __init__(self) -> None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise LedgerError(
                "SUPABASE_URL / SUPABASE_SERVICE_KEY not set "
                "(or set ledger backend to 'jsonfile')"
            )
        self._base = url.rstrip("/") + "/rest/v1"
        self._client = httpx.Client(
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
            timeout=30.0,
        )

    def _params(self, filters: dict[str, Any]) -> dict[str, str]:
        return {k: f"eq.{v}" for k, v in filters.items()}

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.is_error:
            raise LedgerError(f"supabase {resp.status_code}: {resp.text[:500]}")

    def get(self, table: str, filters: dict[str, Any]) -> list[dict]:
        check_table(table)
        resp = self._client.get(f"{self._base}/{table}", params=self._params(filters))
        self._raise_for_status(resp)
        return resp.json()

    def upsert(self, table: str, rows: list[dict]) -> list[dict]:
        check_table(table)
        resp = self._client.post(
            f"{self._base}/{table}",
            json=rows,
            headers={
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
        )
        self._raise_for_status(resp)
        return resp.json()

    def patch(
        self, table: str, filters: dict[str, Any], fields: dict[str, Any]
    ) -> list[dict]:
        check_table(table)
        if not filters:
            raise LedgerError("patch requires at least one filter")
        resp = self._client.patch(
            f"{self._base}/{table}",
            json=fields,
            params=self._params(filters),
            headers={"Prefer": "return=representation"},
        )
        self._raise_for_status(resp)
        return resp.json()
