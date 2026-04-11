# Milestone 18b Shared GFF3 Utilities

Date: 2026-04-10
Status: Complete

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 18b

Implementation note:
- This slice centralizes GFF3 mechanics, not biological policy.
- It should preserve attribute order, escaping, and current output fidelity.

## Current State

- EggNOG and repeat-filtering each implement their own GFF3 parsing and
  formatting helpers.
- The current implementations differ slightly in representation but aim for the
  same output behavior.

## Target State

- A shared `gff3` utility module handles ordered attribute parsing,
  formatting, escaping, and common ID / Parent filtering helpers.
- EggNOG and repeat-filtering use the shared helpers while producing the same
  current outputs.

## Scope

In scope:

- Ordered GFF3 attribute parsing and formatting helpers.
- Shared escaping helper for attribute values.
- Common ID / Parent filtering helpers used by EggNOG and repeat-filtering.
- Focused migration of the current callers.

Out of scope:

- Changing the meaning of EggNOG annotation propagation.
- Changing repeat-filter cleanup policy.
- Introducing tool-specific biological rules into the shared utility layer.

## Implementation Steps

1. Create `src/flytetest/gff3.py`.
2. Add ordered parse / format helpers and shared escaping.
3. Migrate EggNOG and repeat-filtering call sites.
4. Add tests for ordering, escaping, and current-output preservation.
5. Update documentation if the helper module changes how the code is explained.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused EggNOG and repeat-filter tests.
- Run `git diff --check`.

## Blockers Or Assumptions

- This slice assumes a single ordered attribute representation is sufficient for
  the current callers.
- It assumes the shared helpers can preserve existing output byte-for-byte or
  near enough for the current tests.
