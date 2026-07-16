import pytest

from apm.ledger import LedgerError
from apm.ledger.jsonfile import JsonFileLedger


@pytest.fixture
def ledger(tmp_path):
    return JsonFileLedger(tmp_path / "ledger.json")


def test_upsert_then_get(ledger):
    ledger.upsert("sync_cursor", [{"scope": "repo", "last_seen_at": "2026-07-16T00:00:00Z"}])
    rows = ledger.get("sync_cursor", {"scope": "repo"})
    assert rows == [{"scope": "repo", "last_seen_at": "2026-07-16T00:00:00Z"}]


def test_upsert_is_pk_merge_idempotent(ledger):
    row = {"comment_id": 1, "issue_number": 5, "comment_url": "u", "author": "a",
           "content_hash": "h1", "analysis_note": "n", "forward_actions": "f",
           "status": "logged"}
    ledger.upsert("comment_log", [row])
    ledger.upsert("comment_log", [{**row, "content_hash": "h2"}])
    rows = ledger.get("comment_log", {"comment_id": 1})
    assert len(rows) == 1
    assert rows[0]["content_hash"] == "h2"
    assert rows[0]["author"] == "a"  # merge keeps untouched fields


def test_patch_updates_matching_rows(ledger):
    ledger.upsert("action_fingerprints", [{"fingerprint": "abc", "issue_ref": "#1"}])
    out = ledger.patch("action_fingerprints", {"fingerprint": "abc"}, {"issue_ref": "#2"})
    assert out[0]["issue_ref"] == "#2"
    assert ledger.get("action_fingerprints", {"fingerprint": "abc"})[0]["issue_ref"] == "#2"


def test_unknown_table_rejected(ledger):
    with pytest.raises(LedgerError):
        ledger.get("users", {})


def test_upsert_requires_pk(ledger):
    with pytest.raises(LedgerError):
        ledger.upsert("ticket_log", [{"title": "no pk"}])
