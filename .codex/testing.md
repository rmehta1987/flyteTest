# Testing Guide

This file is a repo-specific guide for validation and testing work in FLyteTest.

## Purpose

Use this guide when validating new tasks, workflows, manifests, helper scripts, or registry wiring.

This repo often depends on external bioinformatics tools that may not be available in the current environment, so good testing work includes both executable checks and honest limits.
Default validation should stay local and offline-friendly unless the change truly depends on a cluster or real tool run.
When a new bioinformatics tool is introduced, look first for a small tutorial-backed dataset, mirrored fixture set, or similar ground-truth smoke test before relying on synthetic-only validation.

## Read First

Before testing, read:

1. the touched task/workflow modules
2. `src/flytetest/registry/` if the public interface changed
3. any helper scripts that were modified

If parameter names or example commands were changed, spot-check the relevant
Quick Start section in `README.md` — no need to read the full file.

## Testing Priorities

Prioritize tests and checks in this order:

1. imports and Python compilation
2. signature and registry consistency
3. deterministic path/result handling
4. manifest correctness
5. shell helper syntax
6. synthetic local execution when external tools are unavailable
7. real tool execution when the environment supports it

## Feasible Validation In This Repo

Often useful checks include:

- `python3 -m py_compile` on touched Python files
- small `python3` import checks against `src/`
- registry lookup checks
- package export checks
- `bash -n` for changed shell scripts
- synthetic fixture tests that stub or bypass unavailable external tools

When real binaries are present, add:

- direct tool version checks
- local workflow smoke runs
- container-image command checks through `scripts/test_singularity_images.sh`

## Test ladder for new tasks and workflows

Six layers — each guards a different failure mode. Most user-defined tasks
need 1–4; layers 5–6 catch the integration bugs that mock-based unit tests
silently miss. Run cheapest first; stop when you have enough confidence.

| # | Layer | Catches | What to read |
|---|-------|---------|--------------|
| 1 | Unit-test the pure-Python module against a tiny fixture | logic bugs in the pure function | `tests/test_my_filter.py` |
| 2 | Direct task / workflow invocation with a `flyte_stub.File` | manifest shape, output staging, file pathing | `MyCustomFilterInvocationTests` |
| 3 | Registry shape (`get_entry`, manifest-key alignment) | declared outputs not in `MANIFEST_OUTPUT_KEYS`, missing planner types | `MyCustomFilterRegistryTests`, `ApplyCustomFilterWorkflowRegistryTests` |
| 4 | MCP exposure (`TASK_PARAMETERS`, `SUPPORTED_TASK_NAMES`, `FLAT_TOOLS`) | task registered but unreachable from MCP clients | `MyCustomFilterMCPExposureTests`, `VcCustomFilterMCPContractTests` |
| 5 | **Flat-tool integration via `dry_run`, NO mocking** | binding ↔ planner-type ↔ function-signature collisions | `FlatToolDryRunResolverIntegrationTests` |
| 6 | Real local execution against a tiny fixture | end-to-end correctness of the task body | `_run_workflow_direct(...)` smoke (see "Local execution paths" below) |

Layer 5 is load-bearing. The unit tests at layer 4 mock `run_task` /
`run_workflow`, so they never reach the planner-type resolver. A binding
that omits a required planner-type field, or a parameter name that
collides with a planner-field name, will pass layers 1–4 silently and
explode at layer 5. **Every flat tool should have at least one entry in
`FlatToolDryRunResolverIntegrationTests`** with a real on-disk fixture file.

### Local execution paths

The `flyte run --local` CLI path used by `_execute_workflow_direct`
requires the workflow to be registered with the installed Flyte CLI; in a
fresh dev environment that registration step is typically deferred to
deployment. For pure-Python workflows (no SIF, no subprocess), the
in-process direct call is the canonical layer-6 path:

```python
from flytetest.server import _run_workflow_direct
result = _run_workflow_direct("apply_custom_filter", {"input_vcf": "/abs/path.vcf", "min_qual": 30.0})
# result["exit_status"] == 0 and result["output_paths"] == ["..."]
```

Slurm-backed workflows are exercised through `run_slurm_recipe` from an
authenticated login-node session — see `DESIGN.md §7.4` and the
`HPC 2FA Constraint` memory.

When writing or updating tests, keep them readable:

- add a short module docstring when the test file is not obvious from its path
- add concise test method docstrings when the test name does not fully explain the intent
- add inline comments for fixture setup, path handling, biological assumptions, and any shortcut that would otherwise be surprising

## Real-Data Fixtures

This repo now includes a lightweight real-data fixture set derived from the Galaxy Training Network Braker3 tutorial:

- `data/braker3/reference/genome.fa`
- `data/braker3/rnaseq/RNAseq.bam`
- `data/braker3/protein_data/fastas/proteins.fa`

Before defaulting to synthetic-only validation for a new pipeline milestone,
check whether that stage already has a documented tutorial-backed dataset or
local mirrored fixture directory in `README.md`, `docs/tutorial_context.md`, or
under `data/`.

Use these files for milestone-scoped smoke tests when the relevant binaries are available locally.

Guidelines:

- prefer copying or subsetting fixture inputs into a temp directory instead of editing them in place
- keep fixture-backed tests short and stage-focused
- use the fixture set to validate path discovery, command wiring, and output collection on realistic file shapes
- keep synthetic tests as the primary safety net for deterministic logic and no-binary environments
- if a tutorial-backed dataset or mirrored fixture exists, prefer it for the first smoke test over inventing new synthetic inputs
- if a stage needs larger or tool-specific fixtures later, document that gap explicitly instead of silently expanding scope
- prefer fixture-backed or synthetic tests over real cluster tests unless the new behavior truly requires Slurm

## Synthetic Testing Pattern

When a real tool like Exonerate, PASA, or STAR is unavailable:

- create minimal fake inputs
- exercise deterministic staging and collector logic
- simulate the expected raw output shape closely enough to test converters and manifests
- verify that stable result bundles and manifest keys are produced

When the real tool is available and the Galaxy-derived fixture files are sufficient:

- add one smoke test that uses the local fixture paths under `data/`
- keep runtime and fixture size bounded so the suite stays practical for milestone work

Synthetic validation is especially valuable for:

- chunking logic
- output discovery helpers
- concatenation logic
- manifest shaping
- registry/export integration

## What To Report

Every testing handoff should separate:

- verified directly
- verified synthetically
- not verified because the environment lacks dependencies

If the change touched docs, mention whether the README, DESIGN, or change logs were updated too.

Be explicit. “Untested” is better than implied confidence.

## MCP Reshape Patterns

The reshaped MCP surface has a small set of recurring test shapes that should
be used consistently when touching `run_task` / `run_workflow` / bundles /
`$ref` resolution / staging.

### Bundle availability (`bundles.py`)

`_check_bundle_availability` and `list_bundles` must resolve paths at call
time, not at import time.  Tests should build fixture trees under
`tmp_path` and point the bundle's `backing_data` entries at those paths, not
at `data/`.  A bundle whose backing data is missing should return
`supported=False` with a structured reason — never raise at import.

```python
def test_bundle_available_when_fixtures_present(tmp_path):
    genome = tmp_path / "genome.fa"
    genome.write_text(">chr1\nACGT\n")
    bundle = ResourceBundle(
        name="example",
        ...,
        backing_data={"genome": genome},
    )
    result = _check_bundle_availability(bundle)
    assert result.available is True
```

### `$ref` resolution and type-compatibility declines

Typed-binding tests should cover the three binding forms — raw path,
`$manifest`, and `$ref` — plus the type-mismatch paths:

- Unknown `run_id` → `UnknownRunIdError` → `PlanDecline` with
  `list_available_bindings` / durable-asset-index hints.
- Unknown `output_name` → `UnknownOutputNameError` listing the known outputs.
- `$ref`/`$manifest` produced type mismatches `accepted_planner_types` →
  `BindingTypeMismatchError` pointing at `produced_planner_types` plus the
  raw-path escape hatch.

Use exact-name comparisons against `accepted_planner_types`, not structural
equality.  Raw-path bindings are the deliberate type-check escape hatch —
they must keep passing when type compatibility would otherwise reject them.

### Preflight staging findings and failed-run replies

`check_offline_staging` returns `StagingFinding` lists; tests should cover
`container` / `tool_database` / `input_path` finding kinds, each with
`not_found` / `not_readable` / `not_on_shared_fs` reasons.  The executor-
level test should verify that a staging failure short-circuits `sbatch`
(no subprocess call) and returns
`RunReply(execution_status="failed", ...)` with the finding list in
`limitations` — the artifact must stay on disk so the caller can fix the
path and replay.

### Decline-to-bundles shape

When a run tool declines because the resolver could not materialize a
binding, the reply must be a `PlanDecline` carrying:

- `suggested_bundles: tuple[SuggestedBundle, ...]` — curated starter bundles
  whose `applies_to` overlaps the missing planner type.
- `suggested_prior_runs: tuple[SuggestedPriorRun, ...]` — durable-index
  entries whose `produced_type` matches.
- `next_steps: tuple[str, ...]` — concrete recovery actions
  (e.g. `"Call list_bundles(pipeline_family='annotation') to browse ..."`).

A decline that returns only a bare error string is a test failure.

## Common Risks To Check

- task/workflow signature drift from registry entries
- README examples using old parameter names
- manifest keys not matching collected outputs
- ignored files preventing new modules from showing up in git
- import failures caused by missing config constants or export wiring
- stale compatibility exports in `flyte_rnaseq_workflow.py`

## Don’t

- don’t claim end-to-end validation if only compilation was checked
- don’t skip cheap synthetic validation when real execution is unavailable
- don’t ignore helper scripts if the feature depends on them
- don’t focus only on happy-path biology and miss path/manifest bugs

## Handoff

When finishing testing work, communicate:

- exact commands run
- what passed
- what failed and why
- what remains unverified
- whether the next step should be code fixes, docs fixes, or broader review
