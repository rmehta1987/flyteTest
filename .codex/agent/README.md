# Subagent Guides

This directory contains role-specific delegation guides for FLyteTest.

Use these when splitting work across multiple sessions or sub-agents so each
worker gets a clear ownership boundary, repo-specific constraints, and an
expected handoff format.

These guides complement, but do not override:

- `AGENTS.md`
- `DESIGN.md`
- the area guides under `.codex/`
- active tracking docs such as `docs/realtime_refactor_checklist.md`

## Available Roles

- `architecture.md`
  Use for feature planning, refactor sequencing, architecture notes, and
  contract design.
- `task.md`
  Use for implementing or refactoring individual task modules and deterministic
  transformations.
- `workflow.md`
  Use for composing or refactoring workflow entrypoints and compatibility
  surfaces.
- `test.md`
  Use for adding or tightening tests, validation helpers, and verification
  plans.
- `code-review.md`
  Use for strict review passes focused on bugs, regressions, hidden assumptions,
  and testing gaps.

## Delegation Rules

- Give each sub-agent one clear ownership area.
- Prefer disjoint write scopes to avoid merge conflicts.
- Keep compatibility-critical surfaces explicit:
  `flyte_rnaseq_workflow.py`, `src/flytetest/server.py`,
  `src/flytetest/planning.py`, `src/flytetest/registry.py`,
  `src/flytetest/specs.py`, `src/flytetest/spec_executor.py`,
  `src/flytetest/slurm_monitor.py`, and current manifest contracts.
- When architecture refactor work is active, use
  `docs/realtime_refactor_checklist.md` as the shared tracker.
- Store active detailed per-slice plans under `docs/realtime_refactor_plans/`.
- Move completed or superseded plans to `docs/realtime_refactor_plans/archive/`;
  consult archived plans only when checking prior decisions or historical
  scope.
- For checklist-driven refactors, continue through multiple small sequential
  items in one session when it is safe, and stop only when blocked, when
  compatibility risk rises, or when the next step should be split into a fresh
  slice.
- Every handoff should report:
  files changed, validation run, current checklist status, assumptions, and any
  compatibility risk.
