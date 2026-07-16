---
name: tailor
description: >-
  Tailor this AgenticProjectManager instance to the containing project: read
  ../SPEC.md, derive the domain and advisory roles, and generate
  config/apm.yaml + agents/roles/*.md. Run when config/apm.yaml has
  tailored: false, when SPEC.md changes materially, or on user request.
---

# /tailor — fit the PM pipeline to the project's SPEC.md

You are tailoring a generic PM pipeline to a specific project. The output is
**committed configuration** — a future CI run must work from these files with
no interactive session. Work from the spec; where the spec is silent, choose
sensible defaults and say so in your summary.

## 1. Read

- `../SPEC.md` (project root) — the project spec. If it doesn't exist or is
  the template placeholder, stop and tell the user to write it first.
- `config/apm.yaml` — current state (template ships `tailored: false`).
- `agents/pm.md` — the generic PM charter (context only — NEVER edit it).
- One existing role file under `agents/roles/` if any exist (style reference).

## 2. Derive from the spec

- **Domain** — what kind of project is this (game, ERP, SaaS, data platform…)?
- **Roles** — which 3–7 advisory domains would make PM tickets smart? Prefer
  roles the spec names. Games → designer, gameplay eng, AI eng, tech art, QA.
  ERP → finance, HR, QA, compliance, integrations. Every project gets some QA
  analog.
- **Feature-area taxonomy** — 6–12 lowercase dotted prefixes covering the
  spec's subject matter (e.g. `passing.*`, `payroll.*`, `invoicing.*`). One
  vocabulary serves routing, dedup fingerprints, and the ledger.
- **Routing table** — feature-area prefix → primary role + co-consults.
- **Labels & milestones** — version/phase labels from the spec's roadmap
  (e.g. `ver:v0`…) and the first active milestone.

## 3. Write `config/apm.yaml`

Set `tailored: true` and fill every section: `project` (name, spec paths,
workspace dir), `roles` (name, title, optional per-role `model` for cheaper
consults, optional `extra_tools` for scoped write exceptions — grant these
ONLY if the spec explicitly authorizes that role to write something), `routing`
rules, `labels`, `milestones`. Keep the existing `runner` and `ledger`
sections unless the spec dictates otherwise.

## 4. Write `agents/roles/<role>.md` for each role

House style (see any shipped example): NO frontmatter (files are injected via
`--append-system-prompt-file`; permissions come from config). Structure:

1. Title line: role name + project, one-line project description.
2. Pointers: `SPEC.md`, active version/phase spec, project conventions doc.
3. **Charter**: advisory-only (writes nothing — except config-granted
   exceptions, spelled out with exact commands and dedup-first discipline);
   domain ownership list; project-specific guardrails from the spec (budgets,
   compliance constraints, feel targets).
4. **Per consultation**: what to read, what to research, what "concrete"
   means for this role (numbers, ranges, citations).
5. **Report format**: final message = single JSON object conforming to
   `schemas/consultation.json` (`role`, `topic`, `findings[]`, `approach`,
   `files_touched[]`, `risks[]`, `sequencing`,
   `suggested_acceptance_criteria[]`, optional `out_of_domain`). No prose
   outside the JSON.

## 5. Verify & hand off

- `uv run apm run --dry-run` — config parses, prompt renders, routing table
  appears.
- `uv run pytest` — still green.
- Summarize for the user: roles created, routing table, label taxonomy, any
  defaults you chose, and the next steps (commit; `uv run apm bootstrap`;
  copy `workflows/pm.yml` into the project's `.github/workflows/`; set CI
  secrets).

Do not create GitHub labels/milestones yourself (that's `apm bootstrap`, run
by the user), and do not edit the project's SPEC.md.
