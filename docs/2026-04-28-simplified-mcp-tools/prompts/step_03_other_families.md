# Step 03 — RNA-seq and Any Remaining Showcase Families

## Prerequisites

Steps 01 and 02 must be complete:
- `src/flytetest/mcp_tools.py` contains all `vc_*` and `annotation_*` tools
- `tests/test_mcp_tools.py` passes

## Context

This step adds the `rnaseq_qc` flat tool for the RNA-seq QC/quantification workflow, and serves as the catch-all slot for any remaining showcase-registered workflows or tasks that were not covered in Steps 01–02. At the time of writing only `rnaseq_qc_quant` is known to be in scope; if additional `showcase_module` entries are found they must each get a flat tool here.

## Files to read before editing

- `src/flytetest/mcp_tools.py` — current module after Steps 01–02
- `src/flytetest/mcp_contract.py` — existing constants; `EXPERIMENT_LOOP_TOOLS`; `TOOL_DESCRIPTIONS`
- `src/flytetest/registry/__init__.py` and `src/flytetest/registry/_*.py` — scan for `showcase_module` fields to discover any families not yet covered
- RNA-seq workflow module in `src/flytetest/workflows/` — check `rnaseq_qc_quant` parameter signature
- `src/flytetest/planner_types.py` — check types used by RNA-seq workflows
- `tests/test_mcp_tools.py` — append tests here

## Discovery step

Before implementing, run:
```
rg -rn "showcase_module" src/flytetest/registry/
```
For every `showcase_module` entry whose workflow/task does not yet have a flat tool in `mcp_tools.py`, add it to this step's scope.

## Files to edit

| Action | File |
|---|---|
| Edit | `src/flytetest/mcp_tools.py` |
| Edit | `src/flytetest/mcp_contract.py` |
| Edit | `src/flytetest/server.py` |
| Edit | `tests/test_mcp_tools.py` |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### Tool: `rnaseq_qc`

Wraps `rnaseq_qc_quant`.

```
rnaseq_qc(
    ref: str,                   # required — absolute path to reference (FASTA or index)
    left: str,                  # required — absolute path to R1 FASTQ
    right: str,                 # required — absolute path to R2 FASTQ
    salmon_sif: str = "",       # optional — Apptainer SIF for Salmon
    fastqc_sif: str = "",       # optional — Apptainer SIF for FastQC
    partition: str = "", account: str = "", cpu: int = 0, memory: str = "",
    walltime: str = "", shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None, dry_run: bool = False,
) -> dict
```

Bindings: check the workflow signature in `src/flytetest/workflows/` for the exact planner type names and field names. Likely:
```python
bindings = {
    "ReferenceTranscriptome": {"index_path": ref},   # or "fasta_path" — verify
    "ReadPair": {"r1_path": left, "r2_path": right},
}
```

Inputs: none expected beyond what is in bindings (verify).

Runtime images: `{"salmon_sif": salmon_sif}` and `{"fastqc_sif": fastqc_sif}` if non-empty.

### Additional families (if discovered)

For each additional `showcase_module` workflow/task found during the discovery step, add a flat tool following the same pattern:
- Function in `mcp_tools.py`
- Name constant in `mcp_contract.py`
- `TOOL_DESCRIPTIONS` entry
- Added to `EXPERIMENT_LOOP_TOOLS`
- Registered in `create_mcp_server()`
- Tests in `test_mcp_tools.py`

Name the function `<family_prefix>_<short_name>` per the convention table in `simplified_mcp_tools_plan.md`.

### `src/flytetest/mcp_contract.py`

Add:
```python
RNASEQ_QC_TOOL_NAME = "rnaseq_qc"
```

Add to `EXPERIMENT_LOOP_TOOLS`. Add `TOOL_DESCRIPTIONS` entry:
```python
RNASEQ_QC_TOOL_NAME: (
    "[experiment-loop] Flat-parameter wrapper for rnaseq_qc_quant."
    " ref, left, and right paths are required and must be absolute."
    " " + QUEUE_ACCOUNT_HANDOFF
),
```

### `src/flytetest/server.py`

Import and register `rnaseq_qc` (and any additional tools) in `create_mcp_server()`.

### `tests/test_mcp_tools.py`

For `rnaseq_qc`:
- Happy path: verify bindings contain the correct reference and read-pair keys.
- Missing `ref`, `left`, or `right` each raise `TypeError`.

## Acceptance criteria

- `python -m py_compile src/flytetest/mcp_tools.py` exits 0
- `python -m pytest tests/test_mcp_tools.py -v` passes (all prior steps still pass)
- Every `showcase_module` workflow and task in the registry has a corresponding flat tool
- All new tool names appear in `MCP_TOOL_NAMES`

## CHANGELOG entry template

```
### Added
- `rnaseq_qc` flat MCP tool in `mcp_tools.py` wrapping `rnaseq_qc_quant`;
  tool name constant and TOOL_DESCRIPTIONS entry added to `mcp_contract.py`;
  registered in `create_mcp_server()`.
- Tests for `rnaseq_qc` added to `tests/test_mcp_tools.py`.
- [List any additional family tools added here.]
```
