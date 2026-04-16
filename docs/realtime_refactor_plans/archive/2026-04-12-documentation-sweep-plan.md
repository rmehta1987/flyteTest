# Documentation Sweep Plan

## Context

The `.codex/documentation.md` and `.codex/comments.md` style guides were
updated to require:

1. Args/Returns entries must explain the biological/engineering *why* — not
   restate the type name
2. Inline comments must answer *why*, not narrate *what* the code does
3. Module docstrings must be flush at column 0 (not 4-space indented)
4. Dataclass docstrings must use `Attributes:` sections for non-obvious fields
5. Test closures use one-liner docstrings only — no Args/Returns

**Depth target:** `slurm_poll_loop` in `src/flytetest/slurm_monitor.py`.
That docstring is the standard — it explains deployment context, lifecycle
contract, error handling strategy, and Args that say *why each parameter
exists*. The sweep replaces boilerplate with docstrings at that level of
substance. One-liners are correct only when they capture everything a
maintainer needs without reading the body.

This plan inventories files that need updating and breaks the sweep into small,
reviewable passes. The intent is to improve reader-facing knowledge without
changing runtime behavior.

## Execution Safety Rules

- Treat this as a documentation-only refactor unless a broken docstring exposes
  a real behavior bug; if behavior changes, stop and split that work into its
  own implementation change.
- Work one batch at a time, and keep each batch small enough to review by
  diff. Do not mix task, workflow, server, test, and shell-script cleanup in
  the same commit-sized unit.
- Refresh counts and line references with `rg` before editing a batch. The
  inventory below is a starting point, not a frozen source of truth.
- Preserve biological pipeline order and existing task/workflow boundaries.
  A docstring may clarify an existing assumption, but it must not invent
  support or describe future behavior as implemented.
- Prefer deleting unhelpful Args/Returns sections over replacing them with
  longer boilerplate. Add detail only when it explains a real contract,
  biological role, failure mode, or execution boundary.
- Update `CHANGELOG.md` with dated bullets as batches land. Note anything
  tried, deferred, or intentionally left alone so later agents do not repeat
  the same audit work.

## Per-Batch Validation

After each Python batch:

1. Run `python -m compileall` on the touched Python files.
2. Run the smallest relevant pytest target for the touched files when one
   exists.
3. Run `rg "A value used by the helper|The returned .* value used by the caller"`
   against the touched files to confirm the batch did not leave obvious
   boilerplate behind.
4. Review `git diff --check` to catch whitespace and Markdown/code-block
   formatting issues.

After each documentation-only or shell-script batch:

1. Run `git diff --check`.
2. Read the rendered Markdown or script comments in diff form for stale claims.
3. Confirm no executable shell behavior changed unless that was an explicit
   part of the batch.

## Suggested Batch Order

Use these as commit-sized or review-sized units. A batch can be split further
when the diff starts to feel noisy.

| Batch | Scope | Why This Order | Validation |
|---|---|---|---|
| 0 | Refresh this inventory and add a `CHANGELOG.md` note | Prevent stale counts and line numbers from steering later work | `rg` inventory commands + `git diff --check` |
| 1 | `src/flytetest/spec_executor.py` class/dataclass copy-paste fixes only | Removes misleading class documentation from shared execution records before broader cleanup | `python -m compileall src/flytetest/spec_executor.py`; targeted `tests/test_spec_executor.py` if feasible |
| 2 | `src/flytetest/spec_executor.py` helper/class method boilerplate | Keeps saved-spec and Slurm execution documentation in one focused pass after the dataclass intent is correct | Same as Batch 1 |
| 3 | Shared infrastructure: `src/flytetest/server.py`, `planner_adapters.py`, `spec_artifacts.py`, `manifest_io.py`, `mcp_contract.py`, `config.py`, `gff3.py`, `resolver.py`, `specs.py`, `manifest_envelope.py`, `types/assets.py` | Documents planner, MCP, manifest, and asset boundaries before task-level wording depends on them | Compile touched files; run matching planner/server/spec tests where practical |
| 4 | PASA-only task/workflow files: `src/flytetest/tasks/pasa.py`, `src/flytetest/workflows/pasa.py` | PASA is the largest task surface and should not be mixed with other biological stages | Compile touched files; run PASA-focused tests |
| 5 | Consensus/filtering/protein evidence task/workflow files | These stages sit around evidence integration and filtering, so their pipeline-boundary language should be reviewed together | Compile touched files; run matching tests |
| 6 | Transcript evidence, TransDecoder, AGAT, EggNOG, annotation, functional, QC/quant task/workflow files | Cleans the remaining biological task families in smaller topical chunks if needed | Compile touched files; run matching tests |
| 7 | Test cleanup: boilerplate Args/Returns and nested closure docstrings | Test closure style is easier to review after production docs establish the vocabulary | Run the touched test files |
| 8 | `scripts/rcc/` comment audit | Shell comments have different constraints and should stay separate from Python docstring work | `git diff --check`; inspect script diffs for behavior changes |
| 9 | Final sweep | Catch missed boilerplate, stale line references, and documents that need status updates | Repo-wide `rg`; targeted test reruns as needed |

## Progress

| Batch | Status | Notes |
|---|---|---|
| 0 | Done | 2026-04-13 inventory refreshed from the live tree. Exact helper-boilerplate search now finds 853 matches total: 674 in `src/` and 179 in `tests/`. `spec_executor.py` has zero matches for the exact helper boilerplate pattern, but still has the LocalNodeExecutionRequest-style copy-paste body in 7 class/dataclass docstrings (6 wrong copies plus the source request class). A first-non-comment-line scan found no remaining module docstring indentation issues in `src/` or `tests/`. |
| 1 | Done | 2026-04-13 replaced the wrong LocalNodeExecutionRequest-style class/dataclass docstring copies in `src/flytetest/spec_executor.py`; the request class itself remains as the one appropriate occurrence. |
| 2 | Done | 2026-04-13 swept remaining generic helper/class method wording in `src/flytetest/spec_executor.py`; exact boilerplate `rg` checks are clean for the file, `python3 -m compileall src/flytetest/spec_executor.py` passed, `.venv/bin/python -m pytest tests/test_spec_executor.py` passed, and `git diff --check -- src/flytetest/spec_executor.py` passed. The bare `python` command is unavailable in this shell. |
| 3 | Done | 2026-04-13 cleaned shared infrastructure docstrings in `planner_adapters.py`, `spec_artifacts.py`, `specs.py`, `types/assets.py`, `manifest_io.py`, `manifest_envelope.py`, `mcp_contract.py`, `config.py`, `gff3.py`, and `server.py`. `server.py` was included because a broader generic-wording scan found cleanup beyond the exact helper-boilerplate query. Worker validation passed compileall, targeted tests, targeted `rg` scans, and path-scoped `git diff --check`; the bare `python3 -m pytest` path remains unavailable because system pytest is not installed, so venv pytest was used for runnable tests. |
| 4 | Done | 2026-04-13 cleaned PASA task/workflow docstrings in `src/flytetest/tasks/pasa.py` and `src/flytetest/workflows/pasa.py`; validation passed compileall, `tests/test_pasa_update.py`, targeted `rg`, and path-scoped `git diff --check`. |
| 5 | Done | 2026-04-13 cleaned consensus, repeat-filtering, and protein-evidence task/workflow docstrings; validation passed compileall, `tests/test_consensus.py`, `tests/test_repeat_filtering.py`, `tests/test_protein_evidence.py`, targeted `rg`, and path-scoped `git diff --check`. |
| 6 | Done | 2026-04-13 cleaned transcript-evidence, TransDecoder, AGAT, EggNOG, annotation, functional, QC, and quant task/workflow docstrings; validation passed compileall, `tests/test_transcript_contract.py`, `tests/test_transdecoder.py`, `tests/test_agat.py`, `tests/test_eggnog.py`, `tests/test_functional.py`, `tests/test_annotation.py`, targeted `rg`, and path-scoped `git diff --check`. |
| 7 | Done | 2026-04-13 cleaned boilerplate test helper docstrings and nested closure docstrings across the Batch 7 test files. Validation passed compileall, touched test-file pytest targets (`tests/test_server.py`, `tests/test_spec_executor.py`, `tests/test_consensus.py`, `tests/test_pasa_update.py`, `tests/test_transcript_contract.py`, `tests/test_transdecoder.py`, `tests/test_specs.py`, `tests/test_planning.py`, `tests/test_annotation.py`, `tests/test_functional.py`, `tests/test_eggnog.py`, `tests/test_agat.py`, `tests/test_repeat_filtering.py`, `tests/test_protein_evidence.py`), targeted `rg`, and path-scoped `git diff --check`. Remaining `Args:`/`Returns:` hits are descriptive helper/test-fixture docs, not the old boilerplate or nested closure blocks. |
| 8 | Done | 2026-04-13 audited `scripts/rcc/` comments and added missing file-level purpose headers to 34 RCC shell/Slurm helper scripts. Validation passed `bash -n` on changed `.sh` and `.sbatch` files, `git diff --check -- scripts/rcc`, and a diff inspection showing comment-only additions. |
| 9 | Done | 2026-04-13 final sweep complete. Repo-wide boilerplate `rg` checks are clean; the only remaining `spec_executor.py` LocalNodeExecutionRequest-style phrase is the source request class occurrence allowed by Batch 1; the first-module-docstring indentation scan found no remaining issues in `src/` or `tests/`; `python3 -m compileall src tests` passed; `git diff --check` passed; the consolidated touched-file pytest target passed with 179 tests. A full `.venv/bin/python -m pytest` run still fails in untouched `tests/test_slurm_async_monitor.py::TestSlurmPollLoop::test_loop_survives_reconcile_error` because the async retry test observed one reconcile call instead of the expected retry within its timeout. |

---

## Files Needing Changes

The counts below were refreshed on 2026-04-13 with:

```
rg -c "A value used by the helper|The returned .* value used by the caller" src tests --glob '*.py'
```

They remain approximate enough to re-check before editing each batch because
nearby work may already have fixed some entries.

### Group A: src/ — Heavy Boilerplate Cleanup

These files have 20+ instances of the boilerplate pattern (`A value used by
the helper.` / `The returned X value used by the caller.`). Also check these
files for 4-space module docstring indentation before editing; some line and
formatting details may already have changed.

Priority order reflects current match count, with shared infrastructure kept
visible where it still has matches.

| File | Boilerplate count | Notes |
|---|---|---|
| `src/flytetest/tasks/pasa.py` | 113 | Highest count |
| `src/flytetest/tasks/consensus.py` | 85 | |
| `src/flytetest/tasks/filtering.py` | 65 | |
| `src/flytetest/tasks/transcript_evidence.py` | 51 | |
| `src/flytetest/tasks/agat.py` | 36 | |
| `src/flytetest/tasks/protein_evidence.py` | 33 | |
| `src/flytetest/tasks/eggnog.py` | 30 | |
| `src/flytetest/planner_adapters.py` | 29 | |
| `src/flytetest/tasks/transdecoder.py` | 28 | |
| `src/flytetest/tasks/functional.py` | 27 | |
| `src/flytetest/tasks/annotation.py` | 26 | |

### Group B: src/ — Moderate Boilerplate Cleanup

| File | Boilerplate count | Notes |
|---|---|---|
| `src/flytetest/workflows/pasa.py` | 18 | |
| `src/flytetest/workflows/transcript_evidence.py` | 14 | |
| `src/flytetest/workflows/consensus.py` | 12 | |
| `src/flytetest/tasks/quant.py` | 11 | |
| `src/flytetest/gff3.py` | 11 | |
| `src/flytetest/spec_artifacts.py` | 10 | |
| `src/flytetest/config.py` | 9 | |
| `src/flytetest/workflows/filtering.py` | 9 | |
| `src/flytetest/types/assets.py` | 7 | |
| `src/flytetest/manifest_envelope.py` | 6 | |
| `src/flytetest/manifest_io.py` | 6 | |
| `src/flytetest/workflows/protein_evidence.py` | 6 | |
| `src/flytetest/workflows/rnaseq_qc_quant.py` | 6 | |
| `src/flytetest/workflows/agat.py` | 5 | |
| `src/flytetest/tasks/qc.py` | 4 | |
| `src/flytetest/workflows/annotation.py` | 4 | |
| `src/flytetest/workflows/eggnog.py` | 4 | |
| `src/flytetest/workflows/functional.py` | 4 | |
| `src/flytetest/workflows/transdecoder.py` | 4 | |
| `src/flytetest/mcp_contract.py` | 1 | |

### Group C: src/ — Special Cases

**`src/flytetest/spec_executor.py`** has copy-paste problems, but the old
helper-boilerplate query no longer matches it:

- The exact `A value used by the helper` / `The returned .* value used by the
  caller` search returns 0 matches.
- The old exact phrase
  `It captures the node metadata, resolved planner inputs, and frozen runtime policy`
  no longer appears on one line, but the same body still appears split across
  lines in 7 class/dataclass docstrings.
- One occurrence is the source `LocalNodeExecutionRequest` docstring at line
  119 and can stay if it remains accurate.
- Six wrong copies remain and should be replaced at the current line starts:
  `LocalSpecExecutionResult` line 152, `SlurmRetryPolicy` line 209,
  `SlurmFailureClassification` line 220, `SlurmRunRecord` line 237,
  `LocalWorkflowSpecExecutor` line 1491, and `SlurmWorkflowSpecExecutor` line
  1747.
- Each needs a replacement docstring that describes the actual class and its
  fields (with `Attributes:` where fields are non-obvious)
- Refresh exact locations with:
  ```
  rg -n "It captures the node metadata|resolved planner inputs, and frozen runtime policy|handler needs in order to execute one stage" src/flytetest/spec_executor.py
  ```

**Module docstring indentation:** A 2026-04-13 first-non-comment-line scan of
`src/**/*.py` and `tests/**/*.py` found no remaining files whose module
docstring starts with a 4-space indent. The broader `rg -n "^    \"\"\""` scan
still finds function/class docstrings, but those are not module docstring
indentation issues.

### Group D: tests/ — Boilerplate + Closure Fixes

These test files have boilerplate Args/Returns and/or full Google-style sections
on nested closure functions (which should be one-liners per the updated standard).

| File | Boilerplate count | Notes |
|---|---|---|
| `tests/test_server.py` | 27 | |
| `tests/test_protein_evidence.py` | 25 | |
| `tests/test_consensus.py` | 24 | |
| `tests/test_spec_executor.py` | 19 | Also has closure docstrings to trim |
| `tests/test_pasa_update.py` | 13 | |
| `tests/test_transcript_contract.py` | 10 | |
| `tests/test_agat.py` | 9 | |
| `tests/test_transdecoder.py` | 9 | |
| `tests/test_repeat_filtering.py` | 8 | |
| `tests/test_eggnog.py` | 7 | |
| `tests/test_specs.py` | 7 | |
| `tests/test_functional.py` | 6 | |
| `tests/test_planning.py` | 6 | |
| `tests/test_annotation.py` | 5 | |
| `tests/flyte_stub.py` | 4 | |

### Group E: Non-Python Files

**Shell scripts** in `scripts/rcc/` (~34 files). Most already use comments
that explain cluster config reasons (which is the correct pattern). The sweep
should confirm each file has:
- A header comment explaining what the script does and when to use it
- Inline comments that explain *why* (cluster policy, resource constraint) not
  just *what*
- No stale or redundant comments

**Already clean — no changes needed:**
- `src/flytetest/registry.py`
- `src/flytetest/composition.py`
- `src/flytetest/slurm_monitor.py`
- `src/flytetest/server.py` (under the exact helper-boilerplate query)
- `src/flytetest/spec_executor.py` (under the exact helper-boilerplate query;
  copy-paste class docstrings remain tracked above)
- `src/flytetest/resolver.py`
- `src/flytetest/specs.py`
- `src/flytetest/planning.py`
- `src/flytetest/__init__.py`
- `tests/test_slurm_async_monitor.py`
- `.codex/documentation.md` (intentional boilerplate in anti-pattern examples)
- `.codex/comments.md` (same — examples are illustrative, not production code)

---

## Target Docstring Depth

The canonical example is `slurm_poll_loop` in `src/flytetest/slurm_monitor.py`.
Every non-trivial function should aim for that level of content:

- Summary line: what the function does and *where it lives* in the system
  (e.g. "Designed to be started as a background task inside the MCP server
  event loop via `anyio.create_task_group().start_soon(...)`")
- Behavioral contract: what invariants the caller can rely on, what the
  function does on error, whether it ever returns normally
- Named sub-sections where the behavior is complex:
  `Error handling:`, `Retry logic:`, `Output contract:` — anything a
  maintainer would need to know without reading the full body
- Args entries that explain *why the parameter exists* — the engineering
  constraint, the injection point, the pipeline boundary — not just the type:
  ```
  run_root: Directory under `.runtime/runs/` where Slurm run records are stored.
  scheduler_runner: Injectable subprocess runner for testing.
  command_available: Injectable command-availability checker for testing.
  ```

**The goal is not to add words — it is to add knowledge.** If a one-liner
captures everything a maintainer needs to know, that is correct. If a function
has non-obvious lifecycle behavior, error handling, or pipeline assumptions,
the docstring must document them at the depth of `slurm_poll_loop`.

---

## What Each Change Looks Like

**Boilerplate Args/Returns fix:** Replace entries like
```
directory: A value used by the helper.
Returns: The returned `Path` value used by the caller.
```
with descriptions that explain:
- for task inputs: the biological role, the upstream contract, which output
  bundle the value comes from
- for workflow inputs: the pipeline position, what stage produces this value
- for helper inputs: the constraint that governs the value, why this function
  needs it specifically
- for Returns: what invariant the caller can rely on, what errors are raised
  so the caller never silently proceeds without a valid result

Omit the section only when the name and type hint are genuinely unambiguous
and there is no behavioral contract worth documenting.

**Module docstring indent fix:** Move 4-space-indented continuation lines
flush to column 0.

**Class/dataclass docstring fix (spec_executor.py):** Replace the copy-pasted
`LocalNodeExecutionRequest` body with a class-specific description + an
`Attributes:` section for non-obvious fields.

**Test closure fix:** Replace full Google-style Args/Returns blocks on inner
functions with a single-sentence docstring — the test method is the caller
and is always visible.
