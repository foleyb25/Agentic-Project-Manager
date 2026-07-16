---
name: bootstrap
description: >-
  One-time (idempotent) GitHub repo provisioning from PROJECT.md: create the
  label taxonomy and the active milestone. Run after /tailor, before the
  first PM run.
user-invocable: true
---

# /bootstrap — labels + milestone from PROJECT.md

1. Read `${CLAUDE_PLUGIN_ROOT}/PROJECT.md`: the roster (role names), label
   taxonomy, and active milestone.
2. Create labels — one per `role:*` (including `role:pm`), one per value of
   every other taxonomy dimension (`ver:*`, `type:*`, …). Use the `github`
   MCP label tools if the surface exposes them; otherwise `gh label create
   <name> --force --color <hex> --description <text>` via Bash if `gh` is
   available. Pick stable colors per dimension. `--force`/update-if-exists
   semantics — re-running must be harmless.
3. Create the active milestone if it doesn't exist (check first — never
   duplicate). Description: one line + the active spec path.
4. If neither surface can create labels (no label tool, no gh), output the
   complete label list as a table so the user can create them in the GitHub
   UI, and say exactly that — never claim success without evidence.
5. Report what was created vs already present.
