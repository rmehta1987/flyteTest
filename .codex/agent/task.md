# Task Subagent Guide

This file is the role guide for delegated task-level implementation work in
FLyteTest.

## Purpose

Use this role when adding or modifying individual task functions in
`src/flytetest/tasks/`.

## Read First

Before task work, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. `.codex/tasks.md`
4. `.codex/comments.md`
5. the relevant `docs/tool_refs/...` file
6. the relevant workflow and registry entries if the task is already exposed
7. `docs/realtime_refactor_checklist.md` if the task is part of the architecture
   refactor

## Your Role

Implement one meaningful biological tool invocation or one deterministic
transformation at a time.

You are responsible for:

- keeping task boundaries narrow
- preserving deterministic output contracts
- documenting assumptions honestly
- keeping compatibility with existing workflows unless the task explicitly
  changes that contract

## Core Principles

1. One task, one biological action or deterministic transformation.
2. Keep current Flyte `File` and `Dir` signatures unless the task explicitly
   belongs to a later compatibility-safe migration slice.
3. Use the typed asset layer for manifests and provenance when useful, not as a
   forced runtime boundary.
4. Keep local/container parity through `run_tool(...)` and repo helpers.
5. Do not hide major stage changes in a task implementation.

## Repo Truths

- Prefer `flyte.TaskEnvironment`.
- Prefer `flyte.io.File` and `flyte.io.Dir` in runnable task interfaces.
- Use `Path` internally.
- Write manifests when the task is a collector or stage boundary.
- Be explicit when behavior is inferred rather than source-backed.

## Compatibility-Critical Surfaces

Be careful around tasks that affect:

- registry-exposed task signatures
- collector manifest keys
- files consumed by later stage workflows
- any compatibility export in `flyte_rnaseq_workflow.py`

If a task change affects one of those, update docs, registry metadata, and tests
in the same slice.

## Validation Expectations

At minimum, task work should include feasible validation such as:

- compile or import checks
- synthetic tests or path/result checks
- manifest-shaping checks
- registry consistency checks when task signatures changed

Follow `.codex/testing.md` and report exactly what was or was not verified.

## Handoff

When finishing task work, report:

- biological boundary implemented or changed
- files touched
- any manifest or registry updates required
- validation run
- compatibility risks for downstream workflows
