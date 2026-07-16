#!/usr/bin/env bash
# PreToolUse guard for mcp__supabase__execute_sql.
# The PM ledger protocol is read + idempotent upsert ONLY. Block DDL and
# destructive statements before they reach the database. Exit 2 = block
# (stderr is shown to the model), exit 0 = allow.

set -euo pipefail

input=$(cat)

# Extract the SQL string from tool_input (field name: query). Fall back to the
# whole payload if extraction fails — better to over-scan than under-scan.
if command -v jq >/dev/null 2>&1; then
  sql=$(printf '%s' "$input" | jq -r '.tool_input.query // .tool_input.sql // empty' 2>/dev/null || true)
  [ -n "$sql" ] || sql="$input"
else
  sql="$input"
fi

lower=$(printf '%s' "$sql" | tr '[:upper:]' '[:lower:]')

deny() {
  echo "BLOCKED by plugin guard: $1 — the PM ledger protocol allows only SELECT and idempotent INSERT ... ON CONFLICT upserts (plus UPDATE of existing ledger rows). Rephrase the operation." >&2
  exit 2
}

case "$lower" in
  *"drop table"*|*"drop schema"*|*"drop policy"*|*"drop function"*) deny "DROP statement" ;;
  *"truncate "*) deny "TRUNCATE statement" ;;
  *"alter table"*|*"alter schema"*|*"alter role"*) deny "ALTER statement" ;;
  *"create table"*|*"create schema"*|*"create policy"*|*"create extension"*) deny "DDL create statement (apply schema changes via supabase/migrations, not the PM)" ;;
  *"delete from"*) deny "DELETE statement" ;;
  *"grant "*|*"revoke "*) deny "permission change" ;;
esac

exit 0
