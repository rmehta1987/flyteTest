# Step 02 — Annotation Flat Tools

## Prerequisites

Step 01 (variant_calling flat tools) must be complete:
- `src/flytetest/mcp_tools.py` exists with the ten `vc_*` tools
- `tests/test_mcp_tools.py` exists and passes

## Context

This step adds two flat-parameter MCP tools for the annotation pipeline family using the same pattern established in Step 01. Both tools wrap `ab_initio_annotation_braker3` and `protein_evidence_alignment`.

## Files to read before editing

- `src/flytetest/mcp_tools.py` — current state after Step 01; understand the module layout and the resource-request pattern to follow
- `src/flytetest/mcp_contract.py` — where to add new constants and `TOOL_DESCRIPTIONS` entries
- `src/flytetest/workflows/` — find the annotation workflow modules and check their typed parameter signatures
- `src/flytetest/planner_types.py` — check types used by annotation workflows (e.g. `Genome`, `ProteinEvidence`)
- `src/flytetest/config.py` — check `ANNOTATION_WORKFLOW_NAME`, `PROTEIN_EVIDENCE_WORKFLOW_NAME` (already imported in `mcp_contract.py`)
- `tests/test_mcp_tools.py` — existing tests; append annotation tests here

## Files to edit

| Action | File |
|---|---|
| Edit | `src/flytetest/mcp_tools.py` |
| Edit | `src/flytetest/mcp_contract.py` |
| Edit | `src/flytetest/server.py` |
| Edit | `tests/test_mcp_tools.py` |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### Tool: `annotation_braker3`

Wraps `ab_initio_annotation_braker3`.

```
annotation_braker3(
    genome: str,                          # required — absolute path to genome FASTA
    rnaseq_bam_path: str = "",            # optional — absolute path to RNA-seq BAM
    protein_fasta_path: str = "",         # optional — absolute path to protein FASTA
    braker_species: str = "",             # optional — BRAKER species name
    braker3_sif: str = "",               # optional — Apptainer SIF for BRAKER3
    partition: str = "", account: str = "", cpu: int = 0, memory: str = "",
    walltime: str = "", shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None, dry_run: bool = False,
) -> dict
```

Bindings:
```python
bindings = {
    "Genome": {"fasta_path": genome},
}
```

Inputs: `rnaseq_bam_path`, `protein_fasta_path`, `braker_species` (omit keys with empty-string values to avoid overriding workflow defaults).

Runtime images: `{"braker3_sif": braker3_sif}` if `braker3_sif` is non-empty.

Verify the exact binding type name and field names against `planner_types.py` and the workflow signature.

### Tool: `annotation_protein_evidence`

Wraps `protein_evidence_alignment`.

```
annotation_protein_evidence(
    genome: str,                            # required — absolute path to genome FASTA
    protein_fastas: list[str],              # required — list of absolute paths
    proteins_per_chunk: int = 100,          # optional
    exonerate_model: str = "protein2genome",# optional
    exonerate_sif: str = "",               # optional — Apptainer SIF for Exonerate
    partition: str = "", account: str = "", cpu: int = 0, memory: str = "",
    walltime: str = "", shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None, dry_run: bool = False,
) -> dict
```

Bindings:
```python
bindings = {
    "Genome": {"fasta_path": genome},
    "ProteinEvidenceSet": {"fasta_paths": protein_fastas},
}
```

Inputs: `proteins_per_chunk`, `exonerate_model`.

Runtime images: `{"exonerate_sif": exonerate_sif}` if non-empty.

Verify binding type names and field names against `planner_types.py`.

### `src/flytetest/mcp_contract.py`

Add:
```python
ANNOTATION_BRAKER3_TOOL_NAME = "annotation_braker3"
ANNOTATION_PROTEIN_EVIDENCE_TOOL_NAME = "annotation_protein_evidence"
```

Add both to `EXPERIMENT_LOOP_TOOLS`.

Add `TOOL_DESCRIPTIONS` entries:
```python
ANNOTATION_BRAKER3_TOOL_NAME: (
    "[experiment-loop] Flat-parameter wrapper for ab_initio_annotation_braker3."
    " Genome path is required; RNA-seq BAM and protein FASTA are optional evidence."
    " All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
),
ANNOTATION_PROTEIN_EVIDENCE_TOOL_NAME: (
    "[experiment-loop] Flat-parameter wrapper for protein_evidence_alignment."
    " Genome and protein_fastas (list of absolute paths) are required."
    " All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF
),
```

### `src/flytetest/server.py`

Import and register `annotation_braker3` and `annotation_protein_evidence` in `create_mcp_server()` using the same pattern as the Step 01 tools.

### `tests/test_mcp_tools.py`

Append tests for both annotation tools:
- Happy path for `annotation_braker3`: verify `bindings["Genome"]["fasta_path"]` is set.
- Happy path for `annotation_protein_evidence`: verify `bindings["ProteinEvidenceSet"]["fasta_paths"]` is a list.
- Missing `genome` raises `TypeError` for both tools.
- Missing `protein_fastas` raises `TypeError` for `annotation_protein_evidence`.

## Acceptance criteria

- `python -m py_compile src/flytetest/mcp_tools.py` exits 0
- `python -m pytest tests/test_mcp_tools.py -v` passes (all Step 01 tests still pass)
- Both tool names appear in `MCP_TOOL_NAMES`
- Docstrings name every parameter, show an absolute-path example, and state paths must be absolute

## CHANGELOG entry template

```
### Added
- `annotation_braker3` and `annotation_protein_evidence` flat MCP tools in
  `mcp_tools.py`; tool name constants and TOOL_DESCRIPTIONS added to
  `mcp_contract.py`; both registered in `create_mcp_server()`.
- Tests for both annotation tools added to `tests/test_mcp_tools.py`.
```
