#!/usr/bin/env bash
# Local PM run: sources the plugin's .env (gitignored secrets), loads the
# plugin, and executes one /pm-run on your interactive claude login.
# Usage: bin/pm-local.sh [trigger] [focus...]   (from the project root)

set -euo pipefail

plugin_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project_root="$(dirname "$plugin_dir")"

if [ -f "$plugin_dir/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$plugin_dir/.env"
  set +a
fi

trigger="${1:-manual}"
shift || true
run_id="pm-local-$(date +%Y%m%d-%H%M%S)"

cd "$project_root"
exec claude --plugin-dir "$plugin_dir" \
  "/pm-run $trigger $run_id ${*:+focus:$*}"
