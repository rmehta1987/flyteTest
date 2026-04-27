# Submission Prompt — `PlannerResolutionError` 5-vs-4 decision

## Source

`CRITIQUE_REPORT.md` finding **ENG-06** (secondary track of the
2026-04-25 critique follow-up; deferred from that milestone).

## Goal

`src/flytetest/errors.py` defines a `PlannerResolutionError` hierarchy
of five exception classes. The translator that consumes them in
`src/flytetest/server.py` (`_execute_run_tool`) handles four cases
explicitly and folds two of the five into the same handler. The
critique flagged this as a smell — either the five classes should
collapse to four, or the four handlers should grow to five.

This is a **decision-first** milestone. Stage 1 is the decision; stage
2 is the implementation only after the user signs off.

## Read first

1. `AGENTS.md`
2. `src/flytetest/errors.py` — the five exception classes
   (`UnknownRunIdError`, `UnknownOutputNameError`,
   `ManifestNotFoundError`, `BindingPathMissingError`,
   `BindingTypeMismatchError`).
3. `src/flytetest/server.py` — locate `_execute_run_tool` and the
   exception-to-decline translator. Note exactly which classes share
   a handler.
4. `tests/test_planning.py` and `tests/test_server.py` — every test
   that asserts a specific decline category code or error message.
   The decline category surface is part of the public MCP contract.

## Decision

**Option A — Collapse five classes to four.** Merge whichever two
classes share a handler into one class, with a `kind` enum field
distinguishing the sub-cases when callers need to inspect.

**Option B — Grow handlers to five.** Give each of the five exception
classes its own decline category and message. Update tests for the
new category.

## Decision evidence to gather

- Are the two collapsed classes ever caught separately *anywhere*
  (not just by the translator)? If yes, Option B is forced.
- Do their decline category codes show up in `mcp_replies.py` or
  in any user-facing doc? If yes, collapsing them is a public-surface
  break.
- Is the distinction between them semantically meaningful for a
  scientist trying to understand why their run was declined? If
  yes, Option B is more honest.

## In scope

- The decision document (one paragraph, in this prompt's reply or
  appended to a `decision.md` next to this prompt).
- After the decision is signed off: the implementation, which is
  one of:
  - Option A: delete one class, update the few catching sites,
    update tests.
  - Option B: split the shared handler into two, define a new
    decline category, update tests.

## Out of scope

- Rewriting the broader exception hierarchy.
- Adding new exception types.
- Changing the translator's overall structure.

## Acceptance

- Stage 1: decision recorded with one paragraph of evidence.
- Stage 2 (after sign-off):
  - exception count and handler count agree (`5/5` or `4/4`)
  - all existing tests pass
  - any new decline category is documented in the relevant
    user-facing doc

## Risk and stop conditions

- If you find that the decline categories are referenced by an
  external client (search docs/archive and any sample MCP
  configs), stop after stage 1 and ask before changing the public
  contract.

## Commit (stage 2 only)

`secondary-cleanup: align PlannerResolutionError classes with handlers (5/5)`

or

`secondary-cleanup: align PlannerResolutionError classes with handlers (4/4)`
