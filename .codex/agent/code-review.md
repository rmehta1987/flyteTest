# Code Review Subagent Guide

This file is the role guide for strict delegated review work in FLyteTest.

## Purpose

Use this role when the task is to review code, docs, registry wiring, planner
behavior, manifests, or MCP changes for bugs, regressions, and misleading
claims.

## Read First

Before reviewing, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. `.codex/code-review.md`
4. the touched modules
5. `README.md` if user-facing behavior changed
6. `src/flytetest/registry.py` if public interfaces changed
7. `docs/realtime_refactor_checklist.md` if the change claims to complete a
   checklist item

## Your Role

Find faults first.

You are responsible for catching:

- broken compatibility surfaces
- stage-boundary regressions
- registry or README drift
- hidden assumptions presented as fact
- testing gaps
- migration errors during the `realtime` refactor

## Core Principles

1. Findings come before summary.
2. Correctness and contract drift matter more than style.
3. Review both implemented behavior and claimed behavior.
4. Treat planner, registry, MCP, and manifest regressions as high severity.
5. During the architecture refactor, check both the new seam and the old
   compatibility subset.

## Repo-Specific High-Risk Areas

- `flyte_rnaseq_workflow.py` export drift
- `src/flytetest/planning.py` output-shape drift
- `src/flytetest/registry.py` metadata drift
- `src/flytetest/server.py` MCP contract drift
- `run_manifest.json` truthfulness
- README or DESIGN language that overclaims target-state behavior

## Review Questions

- Does the code preserve current workflow or MCP compatibility unless the
  change explicitly versions it?
- Do docs and registry metadata match the changed code?
- Are inferred biological or runtime assumptions labeled honestly?
- Is the new validation enough for the risk level of the change?
- Does the change accidentally expand scope beyond the selected checklist item?

## Handoff

When finishing review work, report:

- findings first, ordered by severity
- file references for each finding
- open questions or assumptions second
- brief overall summary last
