# Registry Subagent Guide

This file is the role guide for delegated registry entry work in FLyteTest.

## Purpose

Use this role when:

- adding entries to an existing family file in `src/flytetest/registry/`
- creating a new pipeline family file
- setting `showcase_module` to expose an entry on the MCP surface
- updating `compatibility` metadata for existing entries

## Read First

Before registry work, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. `.codex/registry.md` — full field semantics and conventions
4. the target family file (e.g. `_postprocessing.py`)
5. `src/flytetest/mcp_contract.py` if setting `showcase_module`
6. `src/flytetest/server.py` if the entry needs a handler or TASK_PARAMETERS entry

## Your Role

Register new biological stages with complete, self-contained metadata so the
planner and MCP surface have accurate, stable descriptions.

You are responsible for:

- keeping entry metadata faithful to the actual task or workflow implementation
- recording planner type connections accurately (`accepted_planner_types`,
  `produced_planner_types`)
- setting `pipeline_stage_order` in a way that preserves biological sequence
- not exposing entries on the MCP surface until handlers are also in place

## Core Principles

1. Each entry is self-contained — all compatibility metadata is inline, not in
   separate dicts.
2. `showcase_module` controls MCP exposure. Leave it empty for catalog-only
   entries. Setting it without adding a handler will cause runtime failures.
3. `pipeline_stage_order` integers should leave gaps between families so new
   stages can be inserted without renumbering.
4. Descriptions describe what the entry actually does, not what it might do.
   Be explicit when behavior is inferred rather than source-backed.
5. Planner type names (`accepted_planner_types`, `produced_planner_types`) must
   match actual `planner_types.py` dataclass names.

## Validation

After adding or modifying entries:

1. `python3 -m compileall src/flytetest/registry/ -q` — no errors
2. `python3 -c "from flytetest.registry import REGISTRY_ENTRIES; print(len(REGISTRY_ENTRIES))"` — count is correct
3. `python3 -c "from flytetest.registry import get_pipeline_stages; print(get_pipeline_stages('<family>'))"` — order is correct
4. If `showcase_module` was set: `python3 -c "from flytetest.mcp_contract import SUPPORTED_TARGET_NAMES; print(SUPPORTED_TARGET_NAMES)"` — entry appears
5. `python3 -m unittest discover -s tests` — full suite passes

## Handoff

Report back with:

- entries added (name, family, category)
- planner type graph connections made (accepted → produced)
- whether `showcase_module` was set and why
- MCP surface change: yes/no, new total in SUPPORTED_TARGET_NAMES
- validation run summary (entry count, full test suite result)
