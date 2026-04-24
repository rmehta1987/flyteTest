# Plan — User-Authoring Guide + Unified Scaffolding Agent

_Updated 2026-04-24 after Milestones H and I landed._

## Context

A user who wants to add their own first-class task or workflow to FLyteTest
today must triangulate across `.codex/tasks.md`, `.codex/workflows.md`,
`.codex/registry.md`, `.codex/testing.md`, the `planner_types.py` dataclasses,
and representative modules like `src/flytetest/tasks/variant_calling.py`. The
existing `.codex/agent/task.md` / `.codex/agent/workflow.md` prompts assume the
reader already knows the repo layout and the registry contract; they are not
an on-ramp for someone bringing their own Python logic (e.g. a custom variant
filter) into the pipeline.

The repo has matured through Milestones H and I (closed 2026-04-24, 858
tests, 21 tasks + 11 workflows in `variant_calling` alone), which shifted
several conventions the plan needs to reflect — see "Milestone H/I deltas"
below.

We are adding two artifacts:

1. **`.codex/user_tasks.md`** — a condensed, user-centric walkthrough that
   answers the concrete questions a newcomer asks: *where does my module go,
   how do I define bindings, how do SIF images work, how do I test without
   one*. Cross-references the deeper guides rather than duplicating them.
2. **`.codex/agent/scaffold.md`** — a unified specialist role prompt that
   turns a stated user intent ("a task that runs my filter module after
   `joint_call_gvcfs`") into three coordinated stubs: task module edit,
   `RegistryEntry`, and test stub — all validated against the
   family-extensibility contract that `.codex/agent/task.md`,
   `.codex/agent/registry.md`, and `.codex/agent/test.md` already enforce.

Intended outcome: a user can run the scaffolding agent with a short intent,
get a review-ready patch, iterate locally without needing a container, and
land a new step in an existing pipeline family without the reviewer having
to re-teach the registry contract.

## Milestone H/I deltas folded into the guide

These are the post-H/I facts the original plan missed or got wrong; the
written guide and scaffold agent were authored against the updated shape:

- **Task signatures return `File`/`Dir`, not dict.** Milestone I's Step 01
  breaking change migrated `bwa_mem2_*`, `sort_sam`, `mark_duplicates`,
  `merge_bam_alignment`, `gather_vcfs`, `variant_recalibrator`, `apply_vqsr`,
  `calculate_genotype_posteriors` from `(str, ..., results_dir) → dict` to
  `(File, ...) → File`. Workflows `preprocess_sample`,
  `preprocess_sample_from_ubam`, `genotype_refinement`,
  `post_genotyping_refinement` now also return `File`. The guide's worked
  example and the scaffold agent's generation template must produce
  `File`-returning tasks, not dict-returning tasks.
- **Manifest filename is now `run_manifest_<stage>.json`**, not
  `run_manifest.json`. See `src/flytetest/tasks/variant_calling.py:99`.
- **`showcase_module` is a required registry field** in practice — every
  live entry sets it to e.g. `"flytetest.tasks.variant_calling"`
  (`src/flytetest/registry/_variant_calling.py:45`). The guide and scaffold
  agent include it.
- **`scattered_haplotype_caller` is gone**; it was renamed to
  `sequential_interval_haplotype_caller` (Milestone I Step 03). The scaffold
  agent's read-first list references the current file, not the old name.
- **A `variant_filtration` task already exists** (Milestone I Step 04,
  `src/flytetest/registry/_variant_calling.py:634`). The user guide's
  worked example ("custom Python variant filter") is framed as
  *additive/alternative* to GATK's hard-filter, not as filling a gap.
- **QC and annotation tasks landed** — `collect_wgs_metrics`,
  `bcftools_stats`, `multiqc_summarize`, `snpeff_annotate`, and their
  workflow wrappers (`pre_call_coverage_qc`, `post_call_qc_summary`,
  `annotate_variants_snpeff`). The scaffold agent's "pipeline_stage_order"
  guidance notes that variant_calling now uses stages through ~21; a new
  user task should pick an unused order in that range or beyond.
- **`TASK_PARAMETERS` is the one required `server.py` touch per new task.**
  The CHANGELOG confirms this as routine (Milestone I Step 07: *"all 14
  new/ported tasks added to TASK_PARAMETERS"*). `SHOWCASE_TARGETS` at
  `src/flytetest/mcp_contract.py:253` auto-derives from `showcase_module`,
  but `run_task` at the MCP boundary (`server.py:1440`, `:1708`, `:3686`)
  looks up scalar params in `TASK_PARAMETERS` at `server.py:164`. The
  scaffold agent's Decline Conditions carve out this one append as
  allowed; all other `server.py` edits still escalate. Workflows need no
  analogous edit — `showcase_module` alone exposes them.
- **Line numbers refreshed**: `MANIFEST_OUTPUT_KEYS` is at
  `src/flytetest/tasks/variant_calling.py:25`; reference task at `:72`;
  `VariantCallSet` at `src/flytetest/planner_types.py:221`;
  `VARIANT_CALLING_ENTRIES` at `src/flytetest/registry/_variant_calling.py:11`;
  `variant_calling_env` at `src/flytetest/config.py:164`; `run_tool` at `:245`
  with the no-SIF fallback at `:261`; reference workflow at
  `src/flytetest/workflows/variant_calling.py:54`; reference test shape at
  `tests/test_variant_calling.py:52` and invocation-test pattern with
  `patch.object(..., "run_tool", ...)` at `tests/test_variant_calling.py:78`.

## Files created

### 1. `.codex/user_tasks.md`

Condensed walkthrough, ~200 lines, same heading/bullet style as
`.codex/tasks.md`. Sections:

- When to read this vs. the specialist guides.
- Where your module lives (pure logic separate from task wrapper).
- Defining inputs (bindings) — signature stays `File`/`Dir` + scalars; the
  binding contract is set by matching param names to fields of the
  `accepted_planner_types` dataclass.
- Manifests and `MANIFEST_OUTPUT_KEYS` — appended-tuple contract; filename
  is `run_manifest_<stage>.json`.
- The registry entry — `inputs`/`outputs` mirror the signature,
  `accepted_planner_types` / `produced_planner_types` set the planner-graph
  edges, `execution_defaults.runtime_images` + `module_loads` declare
  SIF defaults, `showcase_module` enables MCP resolution.
- SIF images — three cases (pure-Python / native-binary / containerized)
  with the `run_tool` no-SIF fallback at `config.py:261` as the escape hatch.
- Testing without a SIF — three layers cheapest-first (pure-Python unit test
  → direct task call with `patch.object(..., "run_tool", ...)` fake →
  `load_bundle` + `run_task` with a frozen upstream artifact).
- Wiring into a workflow — workflows are `@<family>_env.task` composers in
  Flyte v2, not `@workflow`; bind by passing the upstream task's returned
  `File` through to the downstream task.
- Worked example — custom Python variant filter after `joint_call_gvcfs`,
  framed as additive to the existing `variant_filtration` GATK task.
- Hand-off to the scaffolding agent.
- Escalate, don't improvise — decline conditions that require architecture
  review instead of scaffolding.

### 2. `.codex/agent/scaffold.md`

Specialist role prompt, same structure as `.codex/agent/task.md` /
`workflow.md` / `registry.md`. Sections:

- Purpose + Read First.
- Your Role — generate minimum coordinated patch; never invent new planner
  types, families, or MCP surfaces.
- Core Principles (1 intent → 1 patch; `File`/`Dir` + scalar signatures;
  registry mirrors signature; MANIFEST_OUTPUT_KEYS contract; SIF declarative;
  never touch compatibility-critical surfaces).
- Intake Checklist (8 items: family, upstream planner type, produced type,
  execution mode, SIF default, scalar inputs, workflow wiring, stage order).
- Generation Order (task wrapper → MANIFEST_OUTPUT_KEYS append → registry
  entry → test stub → CHANGELOG line → optional workflow edit).
- SIF Image Decision — three modes declared consistently in signature + registry.
- Validation Checklist (compileall, pytest, name-consistency rg, no stray
  planner imports in signatures, no MCP-surface changes).
- Decline Conditions — new planner dataclass, new family, MCP edits,
  signature-breaking change, cross-family composition → escalate to
  `.codex/agent/architecture.md`.
- Handoff format.

## Files updated

- **`CLAUDE.md`** — added `User-authored tasks and workflows (on-ramp) →
  .codex/user_tasks.md` row and appended `.codex/agent/scaffold.md` to the
  specialist role prompts row.
- **`.codex/agent/README.md`** — added `scaffold.md` entry to the role index
  with one-line summary + delegation note (delegates depth to task.md /
  workflow.md / registry.md / test.md; escalates to architecture.md on new
  planner types / families / MCP edits).
- **`CHANGELOG.md`** — one dated `[x]` entry block under `## Unreleased` for
  2026-04-24 describing both new files plus the index/table updates.

## Critical files referenced (read-only — plan does not modify these)

- `src/flytetest/tasks/variant_calling.py:25` (`MANIFEST_OUTPUT_KEYS`),
  `:72` (reference task wrapper pattern), `:99` (manifest filename)
- `src/flytetest/registry/_variant_calling.py:11` (`VARIANT_CALLING_ENTRIES`),
  `:12` (reference `RegistryEntry`), `:45` (`showcase_module` usage),
  `:634` (existing `variant_filtration` — contextualizes worked example)
- `src/flytetest/planner_types.py:221` (`VariantCallSet` GVCF/VCF
  discriminator)
- `src/flytetest/config.py:164` (`variant_calling_env` lookup),
  `:245` (`run_tool`), `:261` (no-SIF native fallback)
- `src/flytetest/workflows/variant_calling.py:54` (`prepare_reference` —
  composition reference)
- `tests/test_variant_calling.py:52` (`RegistryEntryShapeTests` — registry
  stub pattern), `:78` (`patch.object(..., "run_tool", ...)` — invocation
  test pattern)

## Verification

1. **Citation audit.** For each `path:line` reference in the two new files,
   confirm the file exists and the cited symbol appears within ±5 lines of
   the cited line. (Ran during authoring; all hits.)
2. **Diff scope.** `git diff --stat` should show only: `.codex/user_tasks.md`
   (new), `.codex/agent/scaffold.md` (new), `CLAUDE.md`, `.codex/agent/README.md`,
   `CHANGELOG.md`. Any other staged/unstaged changes belong to Milestones H/I
   follow-ups already in flight — do not revert them.
3. **End-to-end dry run of the scaffolding agent.** Pick the worked example
   from the guide ("custom variant filter after joint_call_gvcfs") and run
   the scaffolding agent prompt against it in a scratch branch. Confirm the
   generated patch:
   - compiles (`python3 -m compileall src/flytetest/tasks/variant_calling.py
     src/flytetest/registry/_variant_calling.py`)
   - passes `pytest tests/test_registry.py tests/test_variant_calling.py`
   - touches only `src/flytetest/tasks/variant_calling.py`,
     `src/flytetest/registry/_variant_calling.py`,
     `tests/test_variant_calling.py`, and `CHANGELOG.md`
   - does not import any `planner_types.py` names into the task signature
   - does not modify `server.py`, `planning.py`, `mcp_contract.py`,
     `bundles.py`, or `spec_executor.py`
4. **Cross-reference audit.** `CLAUDE.md` specialist-guides table and
   `.codex/agent/README.md` index both list the new files.
