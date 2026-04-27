# Submission Prompt — RecipeId NewType through public signatures

## Source

`CRITIQUE_REPORT.md` finding **ENG-07** (secondary track of the
2026-04-25 critique follow-up; deferred from that milestone).

## Goal

Replace bare `str` recipe identifiers in the project's *public*
function signatures with a typed `RecipeId = NewType("RecipeId", str)`
alias. Today every consumer accepts `recipe_id: str`; that's
indistinguishable at the type-checker level from any other string.
A typed alias makes "this string is a frozen-recipe identifier" a
checked claim.

## Read first

1. `AGENTS.md`
2. `src/flytetest/spec_artifacts.py` — recipe-id format
   (`<YYYYMMDDThhmmss.mmm>Z-<target_name>`) and creation site.
3. `src/flytetest/server.py` — every `recipe_id: str` in MCP-facing
   tool signatures (`run_local_recipe`, `run_slurm_recipe`,
   `validate_run_recipe`, `monitor_slurm_job`, `retry_slurm_job`,
   `cancel_slurm_job`, etc.).
4. `src/flytetest/spec_executor.py` — internal callers.
5. `src/flytetest/mcp_replies.py` — reply dataclasses that carry a
   recipe_id.

## Architectural intent

- `RecipeId` is purely a `NewType("RecipeId", str)` alias — no
  runtime cost, no validation hook, no constructor function.
- Use it on *public* signatures: MCP tool functions, reply
  dataclasses, executor `submit()` / `monitor()` / `retry()` /
  `cancel()` parameter lists.
- Leave private helpers, comparisons, JSON dumps, and string
  concatenations on bare `str`.

## In scope

- Add the alias in a stable location
  (`src/flytetest/spec_artifacts.py` is the natural home — that's
  where recipe ids are produced).
- Annotate ~10–20 public signatures with `RecipeId`.
- Annotate the relevant fields on `RunReply`, `DryRunReply`,
  `ValidateRecipeReply` if present.
- Update one or two tests that explicitly type-annotate a recipe
  variable; otherwise leave tests alone.

## Out of scope

- Adding runtime validation that a `RecipeId` matches the format
  regex. (That belongs to the artifact loader, which already
  exists.)
- Replacing every `str` in the codebase that *might* be a recipe
  id. Stick to public surfaces and reply types.
- Adding a `class RecipeId(str)` subclass — `NewType` is the
  contract.

## Acceptance

- `from flytetest.spec_artifacts import RecipeId` (or wherever you
  place it) works.
- `mypy` / `pyright` (whichever the repo uses, if any) is no
  worse than before — no new errors introduced. If neither is
  configured, this acceptance reduces to "imports cleanly and
  tests still pass."
- Full test suite passes.

## Risk and stop conditions

- If the alias creates circular imports between `spec_artifacts.py`
  and `server.py` / `mcp_replies.py`, stop and either move the
  alias to a more neutral module (`types/__init__.py` or a new
  `ids.py`) or report.
- If you find more than ~25 public signatures, stop after the
  most-trafficked half and propose a follow-up milestone for the
  rest. Don't attempt all in one slice.

## Commit

`secondary-cleanup: introduce RecipeId NewType for public signatures`

## Documentation

- One dated entry in `CHANGELOG.md` under `## Unreleased`.
- No new user-facing doc (the alias is a developer-facing aid only).
