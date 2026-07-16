---
name: tailor
description: >-
  Tailor this AgenticProjectManager plugin to the containing project: read the
  project root's SPEC.md, derive the domain and advisory roles, and generate
  PROJECT.md + agents/*.md (+ domain MCP servers in .mcp.json). Run when
  PROJECT.md is missing, when SPEC.md changes materially, or on request.
user-invocable: true
---

# /tailor — fit the PM plugin to the project's SPEC.md

You are tailoring a generic PM plugin to a specific project. The output is
**committed configuration** — a future headless CI run must work from these
files with no interactive session. Work from the spec; where it is silent,
choose sensible defaults and say so in your summary.

## 1. Read

- `SPEC.md` at the project root (the repo containing this plugin as a
  submodule). Missing or placeholder → stop; tell the user to write it first.
- `${CLAUDE_PLUGIN_ROOT}/skills/pm-run/SKILL.md` — the generic PM procedure
  (context only — NEVER edit it; project facts belong in PROJECT.md).
- One existing `agents/*.md` if any exist (style reference).

## 2. Derive from the spec

- **Domain** — what kind of project (game, ERP, SaaS, data platform…)?
- **Roles** — 3–7 advisory domains that make PM tickets smart. Prefer roles
  the spec names. Games → designer, gameplay eng, AI eng, tech art, QA. ERP →
  finance, HR, QA, compliance, integrations. Every project gets a QA analog.
- **Feature-area taxonomy** — 6–12 lowercase dotted prefixes covering the
  spec's subject matter. One vocabulary serves routing, dedup fingerprints,
  and the ledger.
- **Routing table** — prefix → primary role + co-consults.
- **Labels & milestones** — version/phase labels from the spec's roadmap and
  the first active milestone.
- **Domain MCP servers** — if consultants need a domain surface (editor
  inspection, ERP sandbox), add the server to
  `${CLAUDE_PLUGIN_ROOT}/.mcp.json` with `${VAR:-default}` env expansion, and
  grant specific `mcp__<server>__<tool>` names per agent.

## 3. Write `${CLAUDE_PLUGIN_ROOT}/PROJECT.md`

The single tailored-facts file pm-run reads. Sections: project name +
one-line description; product owner (GitHub handle); spec paths (program
spec, active version spec), workspace dir, conventions doc; consultation
roster (role name → agent name, one-line charter, write exceptions if the
spec grants any); routing table; label taxonomy; active milestone; ledger
notes (Supabase project ref).

## 4. Write one `${CLAUDE_PLUGIN_ROOT}/agents/<role>.md` per role

Frontmatter (this is a real Claude Code subagent definition):

```yaml
---
name: <role>
description: <when the PM should consult this role — routing-aware>
tools:
  - Read
  - Grep
  - Glob
  - WebFetch
  - WebSearch
  # + specific mcp__<server>__<tool> grants (read-only inspection by default;
  #   write exceptions ONLY if the spec explicitly authorizes them)
maxTurns: 40
# model: <cheaper model>   # optional per-role cost lever
---
```

Body, in this order: role + project one-liner; pointers (spec, active version
spec, conventions doc); **charter** (advisory-only — writes nothing except
spec-granted exceptions, spelled out with exact tools and dedup-first
discipline; domain ownership; project guardrails from the spec); **per
consultation** (what to read, what to research, what "concrete" means —
numbers, ranges, citations); **report format**: final message = single JSON
object per `${CLAUDE_PLUGIN_ROOT}/schemas/consultation.json` (`role`, `topic`,
`findings[]`, `approach`, `files_touched[]`, `risks[]`, `sequencing`,
`suggested_acceptance_criteria[]`, optional `out_of_domain`). No prose outside
the JSON.

## 5. Verify & hand off

- Frontmatter parses (valid YAML), every routing-table role has an agent
  file, every agent file's name appears in PROJECT.md's roster.
- Summarize: roles created, routing table, labels, defaults chosen, next
  steps (commit to the plugin fork; push; bump the submodule pin; `/bootstrap`
  the repo; set CI secrets; copy `workflows/pm.yml`).

Do not create GitHub labels/milestones yourself (that's /bootstrap), and do
not edit the project's SPEC.md.
