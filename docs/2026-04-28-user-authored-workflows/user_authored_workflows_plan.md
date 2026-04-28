# Plan — User-Authored Workflow Composition

_Created 2026-04-28. To be refined before implementation._

## Context — what the on-ramp milestone delivered

The `onramp-impl` milestone (archived 2026-04-24) delivered:

- `run_tool` python_callable mode in `src/flytetest/config.py:246`
- `src/flytetest/tasks/_filter_helpers.py` — pure-Python `filter_vcf` function
- `my_custom_filter` task in `src/flytetest/tasks/variant_calling.py:1272`
- `RegistryEntry` for `my_custom_filter` in `src/flytetest/registry/_variant_calling.py`
- `TASK_PARAMETERS["my_custom_filter"]` in `src/flytetest/server.py:308`
- Full test coverage: `MyCustomFilterInvocationTests`, `MyCustomFilterRegistryTests`,
  `MyCustomFilterMCPExposureTests` in `tests/test_variant_calling.py`
- Documentation in `.codex/user_tasks.md` covering all three execution modes

## What is still missing

1. **Flat MCP tool for `my_custom_filter`** — no `vc_custom_filter` function in
   `src/flytetest/mcp_tools.py`. The task is callable via `run_task` power-tool
   but cannot be invoked by MCP clients that only navigate flat tools.

2. **Composed workflow** — no workflow wires `my_custom_filter` into the
   end-to-end germline pipeline. The "Wiring into a workflow" section in
   `.codex/user_tasks.md` shows the pattern in prose but no real implementation
   exists that a user can copy.

3. **Workflow registry entry** — a composed workflow needs a `RegistryEntry`
   with `category="workflow"` and appropriate `accepted_planner_types`.

4. **Flat MCP tool for the composed workflow** — following the `vc_*` naming
   convention, a `vc_apply_custom_filter` (or similar name) flat tool
   in `mcp_tools.py`.

5. **End-to-end test** — a dry-run test asserting the composed workflow plans
   successfully with `supported=True`.

## Proposed scope

### New workflow — `apply_custom_filter`

Compose: `germline_short_variant_discovery` → `my_custom_filter`

Input surface (inherits from the two constituent workflows):
- `reference_fasta: File`
- `known_sites: File`
- `sample_bam: File`  (or BAM list for small cohort)
- `min_qual: float = 30.0`
- `gatk_sif: str = ""`
- `snpeff_sif: str = ""`

Output: `File` — QUAL-filtered VCF

This gives users a complete copy-paste example of workflow composition that
they can adapt by swapping in their own task at the last stage.

### Step breakdown (to be refined)

| Step | Deliverable | Files touched |
|---|---|---|
| 01 | Flat MCP tool `vc_custom_filter` | `mcp_tools.py` |
| 02 | Composed workflow + registry entry | `workflows/variant_calling.py`, `registry/_variant_calling.py` |
| 03 | Flat MCP tool for composed workflow | `mcp_tools.py` |
| 04 | Tests — flat tool + dry-run workflow + registry entry | `tests/test_mcp_tools.py`, `tests/test_variant_calling.py` |
| 05 | Docs update — link real composed workflow in `user_tasks.md` | `.codex/user_tasks.md` |
| 06 | Closure | `CHANGELOG.md`, commit |

## Settled design decisions

- The composed workflow name should be short and descriptive. Candidate:
  `apply_custom_filter`. (**To confirm with user.**)
- The flat tool for the task follows the established pattern in `mcp_tools.py`
  (see `vc_annotate_variants_snpeff` as the closest parallel — task-level flat tool).
- `download_sync()` on the VCF input is acceptable for `my_custom_filter` because
  plain VCF has no companion index file. This is already the implemented pattern.
- The composed workflow's registry entry should set `category="workflow"` and
  `accepted_planner_types=("VariantCallSet",)` to allow direct invocation from
  an existing variant call set.
- `pipeline_stage_order=23` is the next free slot.

## Open questions (resolve before starting)

1. **Workflow name** — `apply_custom_filter` or shorter?
2. **Input surface** — does the composed workflow accept a BAM (re-run discovery)
   or only a VCF (start from an existing call set)?
3. **Flat tool naming** — `vc_custom_filter` for the task, `vc_apply_custom_filter`
   for the composed workflow?
4. **Scope boundary** — should this milestone also add a second reference task
   in a different family (e.g. annotation), or stay narrowly in variant_calling?

## Current-state constraints

- 942 tests collected (1 error in `tests/test_compatibility_exports.py` —
  pre-existing, unrelated to this milestone)
- `MANIFEST_OUTPUT_KEYS` at `src/flytetest/tasks/variant_calling.py:25`
- `TASK_PARAMETERS` at `src/flytetest/server.py:186`
- Last workflow in `src/flytetest/workflows/variant_calling.py`:
  `annotate_variants_snpeff` at line 603
- Last `RegistryEntry` in `src/flytetest/registry/_variant_calling.py`:
  `my_custom_filter` at line 1312, `pipeline_stage_order=22`
- `mcp_tools.py` flat tools end at `annotation_exonerate_chunk` (line 1915)

## Verification gates (all must pass before merge)

```bash
# Syntax
python3 -m compileall \
    src/flytetest/mcp_tools.py \
    src/flytetest/workflows/variant_calling.py \
    src/flytetest/registry/_variant_calling.py

# Flat tool tests
PYTHONPATH=src pytest tests/test_mcp_tools.py -x -q

# New workflow tests
PYTHONPATH=src pytest \
    tests/test_variant_calling.py::GermlineFilteredWorkflowRegistryTests \
    -x -v

# Full suite (excluding pre-existing error)
PYTHONPATH=src pytest --ignore=tests/test_compatibility_exports.py -q

# Scope guard
git diff --name-only | grep -E \
    "planning\.py|spec_executor\.py|planner_types\.py|bundles\.py"
# Must return nothing
```
