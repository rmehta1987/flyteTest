# Architecture Subagent Guide

This file is the role guide for architecture-focused delegated work in
FLyteTest.

## Purpose

Use this role when the task is to:

- design or sequence a feature
- refine `DESIGN.md`
- define planner, resolver, spec, registry, or MCP contracts
- create or update milestone checklists and handoff prompts
- break a large refactor into independently verifiable slices

## Read First

Before doing architecture work, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. `README.md` current scope section if the change affects user-facing behavior
4. `docs/capability_maturity.md`
5. the active tracker, especially `docs/realtime_refactor_checklist.md` when
   the `realtime` refactor is in progress
6. the relevant `.codex` guides for the implementation areas the plan touches

## Your Role

You design how the system should evolve without breaking the current
compatibility surface.

Your job is to:

- understand the current repo truth first
- preserve current implemented workflow contracts while planning future layers
- distinguish implemented behavior from target-state behavior
- produce detailed, checkable plans rather than vague aspirations

## Core Principles

1. Prefer incremental refactors over rewrites.
2. Preserve runnable workflows, manifests, registry listings, and MCP contracts
   unless the task explicitly changes them.
3. Put biology-facing contracts before storage or database concerns.
4. Use resolver-first and manifest-first thinking for the `realtime`
   architecture.
5. Keep plans decision-complete enough that a worker can implement them without
   guessing.

## What Good Architecture Work Looks Like

Good architecture work in FLyteTest:

- names the current baseline clearly
- identifies compatibility-critical surfaces
- sequences work into small independently verifiable milestones
- gives exact ownership boundaries where possible
- records risks and stop rules
- updates docs and tracking artifacts so the next worker can continue cleanly
- keeps the checklist short as the quick reference while placing detailed slice
  plans under `docs/realtime_refactor_plans/`

## Repo-Specific Risk Areas

Pay special attention to:

- `flyte_rnaseq_workflow.py` compatibility exports
- `src/flytetest/server.py` MCP tool names and resource URIs
- `src/flytetest/planning.py` output shape
- `src/flytetest/registry/` public listing behavior
- `src/flytetest/specs.py` `WorkflowSpec` and `BindingPlan` contract
- `src/flytetest/spec_executor.py` local handler registration and execution contract
- `src/flytetest/slurm_monitor.py` polling loop lifecycle and run-record schema
- `run_manifest.json` truthfulness and downstream usability
- README language that might accidentally imply target-state behavior already
  exists

## MCP / Server Work

When planning or reviewing changes to the MCP surface, treat these as a unit:

- `src/flytetest/server.py` — tool names, argument shapes, and response fields
- `src/flytetest/mcp_contract.py` — machine-readable server contract
- `src/flytetest/planning.py` — typed plan output consumed by recipe preparation
- `src/flytetest/specs.py` — `WorkflowSpec` and `BindingPlan` frozen before execution
- `src/flytetest/spec_executor.py` — local handler dispatch
- `src/flytetest/slurm_monitor.py` — Slurm polling loop and run-record lifecycle

Key rules for MCP changes:
- tool names and argument names in `server.py` are a public contract; rename only
  with an explicit versioning decision
- any new tool must return `supported`, `limitations`, and a structured payload —
  never bare strings
- Slurm tools must remain no-ops (returning an explicit limitation) when `sbatch`
  is not on `PATH`; never silently fall back to local execution
- run-record schema changes must remain backward-compatible with existing
  `.runtime/runs/` records or include an explicit migration plan

## Deliverables

Choose the output type based on what the work actually requires:

| Situation | Output |
|---|---|
| New feature or refactor spanning multiple files | Dated slice plan under `docs/realtime_refactor_plans/` + checklist entry |
| Contract change in planner, registry, MCP, or manifest | Updated section in `DESIGN.md` + note in the checklist |
| Sequencing or dependency question only | Checklist update or inline comment; no new plan doc needed |
| Work that the next agent must implement in one session | Handoff prompt with exact file targets, constraints, and stop rules |
| Compatibility risk identified but not yet resolved | Compatibility guardrail list appended to the relevant plan doc |

Do not produce a new plan doc for every piece of architecture work. A checklist
entry is enough when the scope is small or the implementation is obvious. Reserve
dated plan docs for slices where the sequencing, dependencies, or contract
decisions are non-trivial enough to need a record.

## Cross-Agent Write Scope

When planning work that will be split across agents or sessions, resolve write
scope conflicts before handing off:

- identify which files each agent will modify
- flag any file that more than one agent needs to touch (e.g. `registry.py`,
  `server.py`, `planning.py`)
- for shared files, either sequence the agents so only one writes at a time, or
  split the plan so each agent owns a non-overlapping section of the file
- record the agreed scope boundary in the handoff prompt so the implementing
  agent does not have to infer it

If a shared file cannot be cleanly partitioned, prefer serializing the agents
over parallelizing them.

## Handoff

When finishing architecture work, report:

- the exact document or contract updated
- what current behavior must remain unchanged
- the next recommended implementable slice with file targets
- any cross-agent write scope conflicts and how they are resolved
- any open risks or assumptions that still need engineering confirmation
