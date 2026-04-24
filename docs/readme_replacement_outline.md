# Proposed README Replacement Outline

## Goal

Keep `README.md` as a stable landing page that answers:

- What is FLyteTest?
- Who is it for?
- What is implemented now?
- How do I get started?
- Where do I go for details?

Do **not** keep it as the full source of truth for:

- every task and workflow
- every MCP tool behavior
- every RCC wrapper script
- fixture provenance and smoke helper details
- detailed architecture notes

That material should live in dedicated docs owned by audience or domain.

## Design Rules

- Keep the README short enough to scan in one sitting, ideally 200 to 300 lines.
- Summarize by pipeline family and surface area, not by enumerating every entry.
- Put volatile inventories in generated or dedicated catalog docs.
- Organize deeper docs by audience first, then by domain.
- Link out aggressively instead of duplicating operational detail.
- Treat the README as the repo front door, not the entire building.

## Proposed README Structure

### 1. Title And One-Paragraph Summary

Purpose:

- state what FLyteTest is
- state the current interaction model
- state the current biological scope at a high level

Keep:

- short product summary from the current intro
- one sentence on reproducibility / frozen recipes / Slurm support

Avoid:

- milestone history
- long lists of implemented slices

### 2. What FLyteTest Is

Purpose:

- preserve the current orientation table because it is useful for new readers

Keep:

- what it does
- how you interact
- biology focus
- job tracking
- reliability
- what it is not

Trim:

- anything that starts to sound like roadmap, architecture, or operations

### 3. Current Scope Snapshot

Purpose:

- replace the current long "Implemented Now" section with a compact snapshot

Recommended format:

- a small table by pipeline family
- each row includes status, what is implemented, and the primary detailed doc

Suggested rows:

- annotation
- variant calling
- postprocessing
- MCP scientist surface
- Slurm lifecycle support

Example fields:

- `Family`
- `Current coverage`
- `Primary entrypoint`
- `Detailed doc`

### 4. Quick Start

Purpose:

- keep only the two or three most important entry paths

Recommended subsections:

- `Scientist: MCP experiment loop`
- `Developer: local environment setup`
- `Cluster operator: RCC wrappers and Slurm runbooks`

Keep in README:

- virtualenv setup
- MCP server launch command
- one very short experiment-loop summary

Move out of README:

- long command galleries for every workflow
- tool-by-tool MCP behavior
- Slurm lifecycle details

### 5. Documentation Map

Purpose:

- make the README the directory of trusted docs

Organize by audience:

- `Scientists`
- `Developers`
- `HPC / operations`
- `Architecture / contributors`

Good existing targets to link:

- `SCIENTIST_GUIDE.md`
- `DESIGN.md`
- `AGENTS.md`
- `docs/gatk_pipeline_overview.md`
- `scripts/rcc/README.md`
- `docs/tool_refs/README.md`

Suggested future targets:

- `docs/pipeline_families/annotation_overview.md`
- `docs/catalogs/registry_catalog.md`
- `docs/operations/fixtures_and_smoke_tests.md`

### 6. Current Limits

Purpose:

- keep one honest section on current boundaries

This should replace most of the current `Deferred`, `Roadmap`, and `Assumptions`
content with a tighter list such as:

- generated workflow execution is still bounded
- artifact handling is still local-path oriented
- some pipeline families are deeper than others
- scheduler tools require an authenticated Slurm-capable environment

Keep this short and current.

### 7. Repository Layout

Purpose:

- help new contributors find the main surfaces quickly

Recommended format:

- short bullets for `src/`, `docs/`, `scripts/rcc/`, `data/`, `results/`, `tests/`

Do not turn this into a full file inventory.

## Recommended Content Migration

### Keep In README

- short repo introduction
- orientation table
- compact scope snapshot
- minimal quick start
- documentation map
- current limits
- repo layout

### Move To Existing Docs

- `Architecture Status` -> `DESIGN.md`
- `MCP Recipe Surface` -> `SCIENTIST_GUIDE.md` plus `src/flytetest/mcp_contract.py`
- `MCP Server And Client Setup` -> `SCIENTIST_GUIDE.md` and `docs/mcp_client_config.example.json`
- `HPC And Containers` -> `scripts/rcc/README.md`
- variant-calling inventory -> `docs/gatk_pipeline_overview.md`

### Move To New Or Generated Docs

- full workflow/task inventory -> generated registry catalog
- fixture provenance and smoke helpers -> dedicated fixtures/testing doc
- per-family overviews -> one doc per pipeline family

## Recommended Companion Docs

These do not all need to be created immediately, but this is the structure I
would grow toward.

### Stable Audience Docs

- `SCIENTIST_GUIDE.md`
- `DESIGN.md`
- `AGENTS.md`
- `scripts/rcc/README.md`

### Pipeline Family Docs

- `docs/pipeline_families/annotation_overview.md`
- `docs/pipeline_families/variant_calling_overview.md`
- `docs/pipeline_families/postprocessing_overview.md`

Note:

- `docs/gatk_pipeline_overview.md` can either stay where it is or be renamed
  into the `pipeline_families/` layout later.

### Catalog Docs

- `docs/catalogs/registry_catalog.md`
- `docs/catalogs/bundle_catalog.md`

These are good candidates for generated docs sourced from the registry and
bundle definitions, so the README stops carrying lists that will go stale.

### Operations Docs

- `docs/operations/fixtures_and_smoke_tests.md`
- `docs/operations/mcp_server_setup.md`
- `docs/operations/slurm_lifecycle.md`

## Draft Replacement README Skeleton

```md
# FLyteTest

FLyteTest is a prompt-driven Flyte v2 bioinformatics platform for turning
registered biological stages into reproducible tasks, workflows, and frozen run
recipes that can execute locally or on Slurm-backed HPC environments.

## What FLyteTest Is

| | FLyteTest |
|---|---|
| What it does | ... |
| How you interact | ... |
| Biology focus | ... |
| Job tracking | ... |
| Reliability | ... |
| What it is not | ... |

## Current Scope

| Family / surface | Current coverage | Primary doc |
|---|---|---|
| Annotation | ... | ... |
| Variant calling | ... | ... |
| Postprocessing | ... | ... |
| Scientist MCP surface | ... | ... |
| Slurm lifecycle tools | ... | ... |

## Quick Start

### Scientist: MCP experiment loop

1. Browse entries and bundles.
2. Load a starter bundle or provide explicit bindings.
3. Run via `run_task` or `run_workflow`.
4. Validate or submit frozen Slurm recipes when needed.

See: `SCIENTIST_GUIDE.md`

### Developer: local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-cluster.txt
```

### HPC / RCC operations

See: `scripts/rcc/README.md`

## Documentation Map

### Scientists

- `SCIENTIST_GUIDE.md`
- `docs/gatk_pipeline_overview.md`

### Developers

- `README.md`
- `docs/tool_refs/README.md`

### HPC / operations

- `scripts/rcc/README.md`

### Architecture / contributors

- `DESIGN.md`
- `AGENTS.md`

## Current Limits

- ...
- ...
- ...

## Repository Layout

- `src/` — implementation
- `docs/` — detailed docs and runbooks
- `scripts/rcc/` — RCC and Slurm wrappers
- `tests/` — automated validation
```

## Notes For The Actual Rewrite

- Remove hand-maintained full task and workflow lists from `README.md`.
- Replace inventory sections with summary tables and links.
- Prefer one canonical link per topic instead of mentioning the same topic in
  multiple sections.
- Keep examples short in the README and move extended examples to audience docs.
- If the registry continues to grow, generate catalogs instead of expanding the
  landing page.