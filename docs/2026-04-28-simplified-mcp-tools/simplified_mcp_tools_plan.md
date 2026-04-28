# Simplified MCP Tools — Milestone Plan

**Date:** 2026-04-28
**Status:** Planning

## Problem

`run_workflow` and `run_task` expose a two-layer input surface:

- `bindings: Mapping[str, Mapping[str, Any]]` — keyed by planner type name (e.g. `"ReferenceGenome"`, `"ReadPair"`)
- `inputs: Mapping[str, Any]` — keyed by scalar workflow parameter name

Smaller MCP clients cannot navigate this reliably. Common failure modes:

- Agent confuses `inputs` keys with `bindings` keys (passes `reference_fasta` directly to `inputs` instead of nesting under `"ReferenceGenome"`)
- Agent passes a Flyte `FlyteFile` object instead of a plain string path
- Agent does not know what valid binding type names exist; JSON schema provides no signal

## Solution

New file `src/flytetest/mcp_tools.py` with flat-parameter MCP tools that wrap `run_workflow` / `run_task` internally. Each tool has explicit named parameters that appear directly in the JSON schema. Existing `run_workflow` and `run_task` are kept as power tools.

## Architecture

| Concern | Location |
|---|---|
| Flat tool implementations | `src/flytetest/mcp_tools.py` (new file) |
| Tool name constants | `src/flytetest/mcp_contract.py` |
| Tool descriptions | `TOOL_DESCRIPTIONS` dict in `mcp_contract.py` |
| Tool group membership | `EXPERIMENT_LOOP_TOOLS` tuple in `mcp_contract.py` |
| Registration | `create_mcp_server()` in `server.py` |
| Tests | `tests/test_mcp_tools.py` (new file) |

`server.py` is already ~4 580 lines, so tool implementations live in `mcp_tools.py` to keep concerns separate.

## Naming Convention

| Pipeline family | Tool name prefix | Example |
|---|---|---|
| variant_calling | `vc_` | `vc_germline_discovery` |
| annotation | `annotation_` | `annotation_braker3` |
| rnaseq | `rnaseq_` | `rnaseq_qc` |

## Flat Tool Pattern

Each flat tool:
1. Accepts only plain Python scalars (str, int, bool, list[str]) as named parameters
2. Assembles `bindings` from those scalars (one entry per planner type the workflow needs)
3. Assembles an optional `resource_request` dict from the flattened resource params
4. Calls `run_workflow` (or `run_task`) and returns the result directly

### Bindings assembly

```python
bindings = {
    "ReferenceGenome": {"fasta_path": reference_fasta},
    "ReadPair": {
        "sample_id": sample_ids[0],
        "r1_path": r1_paths[0],
        "r2_path": r2_paths[0] if r2_paths else "",
    },
}
```

### Resource request assembly

```python
_rr: dict[str, object] = {}
if partition:        _rr["partition"]        = partition
if account:          _rr["account"]          = account
if cpu:              _rr["cpu"]              = cpu
if memory:           _rr["memory"]           = memory
if walltime:         _rr["walltime"]         = walltime
if shared_fs_roots:  _rr["shared_fs_roots"]  = shared_fs_roots
if module_loads:     _rr["module_loads"]     = module_loads
return run_workflow(..., resource_request=_rr or None, ...)
```

Resource params with empty defaults: `partition=""`, `account=""`, `cpu=0`, `memory=""`, `walltime=""`, `shared_fs_roots=[]`, `module_loads=[]`.

## Docstring Standard

Every flat tool docstring must follow the `@mcp.tool` rule:
- Name every valid parameter key
- Show a concrete example with absolute paths
- State that all paths must be absolute

## Tool Inventory

### Step 1 — variant_calling (SHOWCASE PRIORITY)

| Tool | Wraps | Required params |
|---|---|---|
| `vc_germline_discovery` | `germline_short_variant_discovery` | `reference_fasta`, `sample_ids`, `r1_paths`, `known_sites`, `intervals`, `cohort_id` |
| `vc_prepare_reference` | `prepare_reference` | `reference_fasta`, `known_sites` |
| `vc_preprocess_sample` | `preprocess_sample` | `reference_fasta`, `r1`, `sample_id`, `known_sites` |
| `vc_genotype_refinement` | `genotype_refinement` | `reference_fasta`, `joint_vcf`, `snp_resources`, `snp_resource_flags`, `indel_resources`, `indel_resource_flags`, `cohort_id`, `sample_count` |
| `vc_small_cohort_filter` | `small_cohort_filter` | `reference_fasta`, `joint_vcf`, `cohort_id` |
| `vc_post_genotyping_refinement` | `post_genotyping_refinement` | `input_vcf`, `cohort_id` |
| `vc_sequential_interval_haplotype_caller` | `sequential_interval_haplotype_caller` | `reference_fasta`, `aligned_bam`, `sample_id`, `intervals` |
| `vc_pre_call_coverage_qc` | `pre_call_coverage_qc` | `reference_fasta`, `aligned_bams`, `sample_ids`, `cohort_id` |
| `vc_post_call_qc_summary` | `post_call_qc_summary` | `input_vcf`, `cohort_id` |
| `vc_annotate_variants_snpeff` | `annotate_variants_snpeff` | `input_vcf`, `cohort_id`, `snpeff_database`, `snpeff_data_dir` |

### Step 2 — annotation

| Tool | Wraps | Required params |
|---|---|---|
| `annotation_braker3` | `ab_initio_annotation_braker3` | `genome` |
| `annotation_protein_evidence` | `protein_evidence_alignment` | `genome`, `protein_fastas` |

### Step 3 — rnaseq

| Tool | Wraps | Required params |
|---|---|---|
| `rnaseq_qc` | `rnaseq_qc_quant` | `ref`, `left`, `right` |

### Step 4 — convention docs

Update `.codex/workflows.md`, `.codex/tasks.md`, and `AGENTS.md` to codify the forward convention: every new registered workflow/task with `showcase_module` must ship a corresponding flat tool.

## Forward Convention

Every new `showcase_module` workflow or task gets a corresponding flat tool at the same time it is registered. The checklist in `.codex/workflows.md` and `.codex/tasks.md` enforces this.

## Files Changed

**New:**
- `src/flytetest/mcp_tools.py`
- `tests/test_mcp_tools.py`

**Modified:**
- `src/flytetest/mcp_contract.py` — new tool name constants, `TOOL_DESCRIPTIONS` entries, `EXPERIMENT_LOOP_TOOLS` additions
- `src/flytetest/server.py` — import `mcp_tools` and register flat tools in `create_mcp_server()`
- `.codex/workflows.md` — forward-convention checklist
- `.codex/tasks.md` — forward-convention checklist
- `AGENTS.md` — note on flat-tool requirement
- `CHANGELOG.md`

## Non-Goals

- Do not remove or deprecate `run_workflow` / `run_task`
- Do not move existing tool implementations out of `server.py`
- Do not change biological pipeline logic, registry, or planner
