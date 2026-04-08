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
3. `README.md`
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
- `src/flytetest/registry.py` public listing behavior
- `run_manifest.json` truthfulness and downstream usability
- README language that might accidentally imply target-state behavior already
  exists

## Deliverables

Architecture work should usually produce one or more of:

- a detailed checklist or phased plan
- a refined contract in `DESIGN.md`
- a handoff prompt
- a dated slice plan under `docs/realtime_refactor_plans/`
- a verification matrix
- a compatibility guardrail list

## Handoff

When finishing architecture work, report:

- the exact document or contract updated
- what current behavior must remain unchanged
- the next recommended implementable slice
- any open risks or assumptions that still need engineering confirmation
