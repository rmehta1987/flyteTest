# Workflow Subagent Guide

This file is the role guide for delegated workflow-level work in FLyteTest.

## Purpose

Use this role when adding or modifying workflow entrypoints in
`src/flytetest/workflows/` or compatibility exports in
`flyte_rnaseq_workflow.py`.

## Read First

Before workflow work, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. `.codex/workflows.md`
4. the relevant task modules
5. `src/flytetest/registry/`
6. `README.md` Quick Start and workflow table if touching examples or docs
7. `docs/realtime_refactor_checklist.md` if the work is part of the architecture
   refactor

## Your Role

Compose narrow tasks into biologically meaningful stage entrypoints without
breaking existing workflow behavior unintentionally.

You are responsible for:

- keeping the biological order explicit
- preserving stage boundaries and collector outputs
- maintaining compatibility exports where required
- keeping workflow docs, registry entries, and README language aligned

## Core Principles

1. Workflows express biological intent, not tool internals.
2. Reuse existing narrow tasks whenever possible.
3. Keep current workflow entrypoints runnable through `flyte run`.
4. Preserve collector-stage and manifest semantics.
5. If the work is part of the `realtime` refactor, keep current workflows as the
   stable baseline while adding new metadata or composition layers around them.

## Compatibility-Critical Surfaces

Treat these as high risk:

- `flyte_rnaseq_workflow.py`
- registry workflow names, inputs, and outputs
- README examples and workflow descriptions
- workflow result bundle structure and manifest keys
- current MCP showcase targets when they point at a workflow entrypoint

## Validation Expectations

Workflow work should usually verify:

- imports and compilation
- registry wiring
- compatibility exports
- synthetic path/result handling
- any touched README examples or docs claims

Use `.codex/testing.md` and report what remains unverified if real tools are not
available.

## Handoff

When finishing workflow work, report:

- workflow graph or stage sequence
- existing workflows intentionally left unchanged
- compatibility surfaces updated
- validation run
- the next downstream stage impacted by the change
