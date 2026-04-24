# Step 02 — MCP Surface Wiring

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Mechanical: set a single field on
14 registry entries; add 7 `TASK_PARAMETERS` tuples; update README and
`mcp_showcase.md`.

## Goal

Make every variant_calling workflow and every Milestone A Flyte task
reachable through the MCP experiment loop (`list_entries → list_bundles
→ load_bundle → run_task / run_workflow`). Plain-Python helper tasks
stay workflow-internal (deferred to Milestone I).

## Context

- Milestone H plan §3 (table of 14 entries), §4 Step 02.
- `src/flytetest/mcp_contract.py:253-266` — derivation chain:
  `SHOWCASE_TARGETS = {e for e in registry if e.showcase_module}` →
  `SUPPORTED_WORKFLOW_NAMES` / `SUPPORTED_TASK_NAMES` → used by
  `_local_node_handlers()` and the `run_task` / `run_workflow`
  dispatchers in `server.py`.
- `src/flytetest/server.py:164-190` — `TASK_PARAMETERS` declares per-task
  scalar parameters for the reshaped run surface.
- README lines ~305-320 enumerate the "Current local MCP execution"
  target list; must be kept in sync.
- Branch: `gatkport-h`.

## What to build

### `src/flytetest/registry/_variant_calling.py`

Set `showcase_module` on 14 entries (7 tasks + 7 workflows). Entries to
update:

| Entry | Category | Module |
|---|---|---|
| `create_sequence_dictionary` | task | `flytetest.tasks.variant_calling` |
| `index_feature_file` | task | `flytetest.tasks.variant_calling` |
| `base_recalibrator` | task | `flytetest.tasks.variant_calling` |
| `apply_bqsr` | task | `flytetest.tasks.variant_calling` |
| `haplotype_caller` | task | `flytetest.tasks.variant_calling` |
| `combine_gvcfs` | task | `flytetest.tasks.variant_calling` |
| `joint_call_gvcfs` | task | `flytetest.tasks.variant_calling` |
| `prepare_reference` | workflow | `flytetest.workflows.variant_calling` |
| `preprocess_sample` | workflow | `flytetest.workflows.variant_calling` |
| `germline_short_variant_discovery` | workflow | `flytetest.workflows.variant_calling` |
| `genotype_refinement` | workflow | `flytetest.workflows.variant_calling` |
| `preprocess_sample_from_ubam` | workflow | `flytetest.workflows.variant_calling` |
| `scattered_haplotype_caller` | workflow | `flytetest.workflows.variant_calling` |
| `post_genotyping_refinement` | workflow | `flytetest.workflows.variant_calling` |

Plain-Python helpers (`bwa_mem2_index`, `bwa_mem2_mem`, `sort_sam`,
`mark_duplicates`, `variant_recalibrator`, `apply_vqsr`,
`merge_bam_alignment`, `gather_vcfs`,
`calculate_genotype_posteriors`) keep `showcase_module=""`.

### `src/flytetest/server.py`

Add `TASK_PARAMETERS` tuples for the 7 exposed tasks. Parameter shape
matches the registry `inputs` tuple, minus any parameter that is an
asset-shaped typed binding (those are supplied via `bindings`, not
`inputs`). For tasks whose inputs are all `File` + scalars, the scalar
names go in `TASK_PARAMETERS`:

```python
TASK_PARAMETERS: dict[str, tuple[tuple[str, bool], ...]] = {
    # ... existing entries ...
    "create_sequence_dictionary": (
        ("gatk_sif", False),
    ),
    "index_feature_file": (
        ("gatk_sif", False),
    ),
    "base_recalibrator": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "apply_bqsr": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "haplotype_caller": (
        ("sample_id", True),
        ("intervals", False),
        ("gatk_sif", False),
    ),
    "combine_gvcfs": (
        ("cohort_id", False),
        ("gatk_sif", False),
    ),
    "joint_call_gvcfs": (
        ("sample_ids", True),
        ("intervals", True),
        ("cohort_id", False),
        ("gatk_sif", False),
    ),
}
```

Check the exact parameter names against the task signatures in
`src/flytetest/tasks/variant_calling.py` before committing — some tasks
have asset-shaped list inputs (`known_sites`, `gvcfs`) that are handled
via `bindings`, not `inputs`.

### README

Update lines ~305-320 to add the 14 new entries to the "Current local MCP
execution" bullet list. Group them clearly:

```
- task: `create_sequence_dictionary`
- task: `index_feature_file`
- task: `base_recalibrator`
- task: `apply_bqsr`
- task: `haplotype_caller`
- task: `combine_gvcfs`
- task: `joint_call_gvcfs`
- workflow: `prepare_reference`
- workflow: `preprocess_sample`
- workflow: `germline_short_variant_discovery`
- workflow: `genotype_refinement`
- workflow: `preprocess_sample_from_ubam`
- workflow: `scattered_haplotype_caller`
- workflow: `post_genotyping_refinement`
```

Also update the README "Biological scope" bullet list (line ~38-39) to
include "GATK4 germline variant calling (A–G)" so the biology section
reflects the completed work.

### `docs/mcp_showcase.md`

If the file enumerates runnable targets, add the 14 new entries there as
well. If it only describes the tool surface at a higher level, leave it.

### Tests

Add assertions in `tests/test_mcp_contract.py`:

- `test_variant_calling_workflows_in_supported_names` — assert each of
  the 7 workflow names is in `SUPPORTED_WORKFLOW_NAMES`.
- `test_variant_calling_tasks_in_supported_names` — assert each of the
  7 Milestone A task names is in `SUPPORTED_TASK_NAMES`.
- `test_plain_python_helpers_not_exposed` — assert that
  `bwa_mem2_mem`, `variant_recalibrator`, `apply_vqsr`, `gather_vcfs`,
  `calculate_genotype_posteriors` (etc.) are *not* in
  `SUPPORTED_TASK_NAMES` (they remain internal until Milestone I).

Add assertions in `tests/test_server.py`:

- `test_run_workflow_supported_for_germline_short_variant_discovery` —
  call `run_workflow("germline_short_variant_discovery", bindings=...,
  inputs=..., dry_run=True)` and assert `supported=True`.
- `test_run_task_supported_for_haplotype_caller` — same shape for
  `run_task("haplotype_caller", ...)`.

## CHANGELOG

```
### GATK Milestone H Step 02 — MCP surface wiring (YYYY-MM-DD)
- [x] YYYY-MM-DD set showcase_module on 7 variant_calling workflow entries.
- [x] YYYY-MM-DD set showcase_module on 7 Milestone A task entries.
- [x] YYYY-MM-DD added TASK_PARAMETERS entries for the 7 exposed tasks.
- [x] YYYY-MM-DD README "Current local MCP execution" list updated.
- [x] YYYY-MM-DD mcp_showcase.md updated.
- [x] YYYY-MM-DD added MCP contract + server dispatch tests (5 tests).
- Plain-Python helper tasks remain workflow-internal; full port deferred to Milestone I.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_mcp_contract.py tests/test_server.py tests/test_registry.py -xvs
rg "showcase_module" src/flytetest/registry/_variant_calling.py | grep -v '""' | wc -l
# expected: 14
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c \
  "from flytetest.mcp_contract import SUPPORTED_WORKFLOW_NAMES, SUPPORTED_TASK_NAMES
print(sorted(n for n in SUPPORTED_WORKFLOW_NAMES if 'variant' in n or n.startswith(('prepare_ref','preprocess_','germline_','genotype_','scattered_','post_')) ))
print(sorted(n for n in SUPPORTED_TASK_NAMES if any(k in n for k in ('recal','bqsr','haplotype','combine_gvcf','joint_call','sequence_dict','index_feature'))))"
# expected: 7 workflows + 7 tasks printed
```

## Commit message

```
variant_calling: expose 14 GATK targets through MCP surface
```

## Checklist

- [ ] 14 `showcase_module` assignments in `_variant_calling.py`.
- [ ] 7 new `TASK_PARAMETERS` entries in `server.py`.
- [ ] README "Current local MCP execution" list includes the 14 entries.
- [ ] Biological scope bullet in README mentions GATK4 germline variant calling.
- [ ] `mcp_showcase.md` updated (or left with a note if it stays high-level).
- [ ] 5 new tests passing.
- [ ] `_local_node_handlers()` covers the 14 new names (verify by inspection; no code change expected).
- [ ] Plain-Python helpers verified absent from `SUPPORTED_TASK_NAMES`.
- [ ] Step 02 marked Complete in checklist.
