# Step 01 — Variant Calling Flat Tools

**SHOWCASE PRIORITY — implement this before the demo.**

## Context

`run_workflow` accepts `bindings: Mapping[str, Mapping[str, Any]]` and `inputs: Mapping[str, Any]`. Smaller MCP clients cannot navigate this two-layer surface: they confuse binding type names with scalar parameter names, and the JSON schema provides no signal about valid keys. This step introduces ten flat-parameter MCP tools that wrap the ten showcase variant_calling workflows with an explicit, schema-visible parameter surface.

## Files to read before editing

- `src/flytetest/mcp_contract.py` — understand `EXPERIMENT_LOOP_TOOLS`, `TOOL_DESCRIPTIONS`, existing tool name constants, `QUEUE_ACCOUNT_HANDOFF`
- `src/flytetest/server.py` — lines 1–120 (imports), `create_mcp_server()` (find where tools are registered via `@mcp.tool`)
- `src/flytetest/workflows/variant_calling.py` — understand each workflow's typed parameters
- `src/flytetest/planner_types.py` — understand `ReferenceGenome`, `ReadPair`, `VariantCallSet`, `AlignedSample`, `CohortCallSet` and their fields
- `tests/test_mcp_tools.py` — check if it already exists; if so read it before editing

## Files to create / edit

| Action | File |
|---|---|
| Create | `src/flytetest/mcp_tools.py` |
| Create | `tests/test_mcp_tools.py` |
| Edit | `src/flytetest/mcp_contract.py` |
| Edit | `src/flytetest/server.py` |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### `src/flytetest/mcp_tools.py`

Create this file. It must:

1. Start with a module docstring explaining that this module contains flat-parameter MCP tools wrapping `run_workflow` / `run_task`.
2. Import `run_workflow` and `run_task` from `flytetest.server` (or wherever `_execute_run_tool` / the public callable lives — check the import path carefully).
3. Implement all ten flat tools below.

**Flat tool template** (use this structure for each tool):

```python
def vc_<name>(
    # --- required biological inputs ---
    reference_fasta: str,
    ...,
    # --- optional biological inputs ---
    optional_param: str = "",
    threads: int = 4,
    # --- container images (optional) ---
    gatk_sif: str = "",
    bwa_sif: str = "",
    # --- resource request (all optional, empty = server default) ---
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """One-sentence summary.

    Parameters
    ----------
    reference_fasta : str
        Absolute path to the reference FASTA file.
    ...
    partition : str
        Slurm partition. Required for Slurm execution; must come from the user.
    account : str
        Slurm account. Required for Slurm execution; must come from the user.
    cpu : int
        CPU cores to request (0 = use server default).
    memory : str
        Memory string, e.g. ``"32G"``. Empty string = use server default.
    walltime : str
        Wall time string, e.g. ``"04:00:00"``. Empty string = use server default.
    shared_fs_roots : list[str] | None
        Paths that must be visible from compute nodes.
    module_loads : list[str] | None
        Full replacement of DEFAULT_SLURM_MODULE_LOADS; extend with
        ``[*DEFAULT_SLURM_MODULE_LOADS, "extra/1.0"]`` if needed.
    dry_run : bool
        If True, plan and freeze the recipe without executing it.

    Example
    -------
    >>> vc_<name>(
    ...     reference_fasta="/data/ref/hg38.fa",
    ...     ...,
    ...     partition="gpu",
    ...     account="mylab",
    ... )

    All paths must be absolute.
    """
    bindings: dict[str, dict[str, object]] = {
        "ReferenceGenome": {"fasta_path": reference_fasta},
        ...
    }
    inputs: dict[str, object] = {
        "threads": threads,
        ...
    }
    runtime_images: dict[str, str] = {}
    if gatk_sif:
        runtime_images["gatk_sif"] = gatk_sif
    if bwa_sif:
        runtime_images["bwa_sif"] = bwa_sif

    _rr: dict[str, object] = {}
    if partition:          _rr["partition"]        = partition
    if account:            _rr["account"]          = account
    if cpu:                _rr["cpu"]              = cpu
    if memory:             _rr["memory"]           = memory
    if walltime:           _rr["walltime"]         = walltime
    if shared_fs_roots:    _rr["shared_fs_roots"]  = shared_fs_roots
    if module_loads:       _rr["module_loads"]     = module_loads

    return run_workflow(
        target="<workflow_name>",
        bindings=bindings,
        inputs=inputs,
        runtime_images=runtime_images or None,
        resource_request=_rr or None,
        dry_run=dry_run,
    )
```

**The ten tools and their bindings:**

1. **`vc_germline_discovery`** → `germline_short_variant_discovery`
   - Required: `reference_fasta: str`, `sample_ids: list[str]`, `r1_paths: list[str]`, `known_sites: list[str]`, `intervals: list[str]`, `cohort_id: str`
   - Optional: `r2_paths: list[str] | None = None`, `threads: int = 4`, `gatk_sif: str = ""`, `bwa_sif: str = ""`
   - Bindings: `ReferenceGenome` (fasta_path), `ReadPairList` or per-sample binding — check workflow signature; `KnownSitesList` (paths)
   - Inputs: `cohort_id`, `intervals`, `threads`

2. **`vc_prepare_reference`** → `prepare_reference`
   - Required: `reference_fasta: str`, `known_sites: list[str]`
   - Optional: `gatk_sif: str = ""`, `bwa_sif: str = ""`, `force: bool = False`
   - Bindings: `ReferenceGenome` (fasta_path)
   - Inputs: `known_sites`, `force`

3. **`vc_preprocess_sample`** → `preprocess_sample`
   - Required: `reference_fasta: str`, `r1: str`, `sample_id: str`, `known_sites: list[str]`
   - Optional: `r2: str = ""`, `threads: int = 4`, `gatk_sif: str = ""`, `bwa_sif: str = ""`
   - Bindings: `ReferenceGenome` (fasta_path), `ReadPair` (sample_id, r1_path, r2_path)
   - Inputs: `known_sites`, `threads`

4. **`vc_genotype_refinement`** → `genotype_refinement`
   - Required: `reference_fasta: str`, `joint_vcf: str`, `snp_resources: list[str]`, `snp_resource_flags: list[str]`, `indel_resources: list[str]`, `indel_resource_flags: list[str]`, `cohort_id: str`, `sample_count: int`
   - Optional: `gatk_sif: str = ""`
   - Bindings: `ReferenceGenome` (fasta_path), `VariantCallSet` (vcf_path → joint_vcf)
   - Inputs: `snp_resources`, `snp_resource_flags`, `indel_resources`, `indel_resource_flags`, `cohort_id`, `sample_count`

5. **`vc_small_cohort_filter`** → `small_cohort_filter`
   - Required: `reference_fasta: str`, `joint_vcf: str`, `cohort_id: str`
   - Optional: `gatk_sif: str = ""`
   - Bindings: `ReferenceGenome` (fasta_path), `VariantCallSet` (vcf_path → joint_vcf)
   - Inputs: `cohort_id`

6. **`vc_post_genotyping_refinement`** → `post_genotyping_refinement`
   - Required: `input_vcf: str`, `cohort_id: str`
   - Optional: `gatk_sif: str = ""`
   - Bindings: `VariantCallSet` (vcf_path → input_vcf)
   - Inputs: `cohort_id`

7. **`vc_sequential_interval_haplotype_caller`** → `sequential_interval_haplotype_caller`
   - Required: `reference_fasta: str`, `aligned_bam: str`, `sample_id: str`, `intervals: list[str]`
   - Optional: `gatk_sif: str = ""`
   - Bindings: `ReferenceGenome` (fasta_path), `AlignedSample` (bam_path → aligned_bam, sample_id)
   - Inputs: `intervals`

8. **`vc_pre_call_coverage_qc`** → `pre_call_coverage_qc`
   - Required: `reference_fasta: str`, `aligned_bams: list[str]`, `sample_ids: list[str]`, `cohort_id: str`
   - Optional: `gatk_sif: str = ""`
   - Bindings: `ReferenceGenome` (fasta_path), `AlignedSampleList` or per-sample — check workflow signature
   - Inputs: `cohort_id`

9. **`vc_post_call_qc_summary`** → `post_call_qc_summary`
   - Required: `input_vcf: str`, `cohort_id: str`
   - Optional: `gatk_sif: str = ""`
   - Bindings: `VariantCallSet` (vcf_path → input_vcf)
   - Inputs: `cohort_id`

10. **`vc_annotate_variants_snpeff`** → `annotate_variants_snpeff`
    - Required: `input_vcf: str`, `cohort_id: str`, `snpeff_database: str`, `snpeff_data_dir: str`
    - Optional: `gatk_sif: str = ""`
    - Bindings: `VariantCallSet` (vcf_path → input_vcf)
    - Inputs: `cohort_id`, `snpeff_database`, `snpeff_data_dir`

> Note: Check the actual workflow function signatures in `src/flytetest/workflows/variant_calling.py` and the planner type field names in `src/flytetest/planner_types.py` before finalizing binding keys. The table above shows the intent; the actual field names are authoritative.

### `src/flytetest/mcp_contract.py`

Add after the existing `EXPERIMENT_LOOP_TOOLS` block:

1. One string constant per tool: `VC_GERMLINE_DISCOVERY_TOOL_NAME = "vc_germline_discovery"` etc.
2. Add each name to `EXPERIMENT_LOOP_TOOLS`.
3. Add a `TOOL_DESCRIPTIONS` entry for each tool under the `# -- experiment-loop` section. Format: `"[experiment-loop] Flat-parameter wrapper for <workflow_name>. All paths must be absolute. " + QUEUE_ACCOUNT_HANDOFF`.

### `src/flytetest/server.py`

In `create_mcp_server()`:

1. Import the ten functions from `flytetest.mcp_tools` at the top of the file.
2. Register each as an `@mcp.tool` using the matching tool name constant from `mcp_contract.py` and the matching description from `TOOL_DESCRIPTIONS`.

### `tests/test_mcp_tools.py`

Create this file. For each of the ten tools write:
- A happy-path test that patches `run_workflow` and verifies `bindings`, `inputs`, and `resource_request` are assembled correctly.
- A test that verifies a missing required parameter raises `TypeError` (Python's default for missing positional args).

Use `unittest.mock.patch` to patch `flytetest.mcp_tools.run_workflow`.

## Acceptance criteria

- `python -m py_compile src/flytetest/mcp_tools.py` exits 0
- `python -m py_compile src/flytetest/mcp_contract.py` exits 0
- `python -m pytest tests/test_mcp_tools.py -v` passes with no failures
- All ten tool names appear in `MCP_TOOL_NAMES` (via `EXPERIMENT_LOOP_TOOLS`)
- Each tool docstring contains an absolute-path example and states that all paths must be absolute

## CHANGELOG entry template

```
## 2026-04-28

### Added
- `src/flytetest/mcp_tools.py`: ten flat-parameter MCP tools for the variant_calling
  family (`vc_germline_discovery`, `vc_prepare_reference`, `vc_preprocess_sample`,
  `vc_genotype_refinement`, `vc_small_cohort_filter`, `vc_post_genotyping_refinement`,
  `vc_sequential_interval_haplotype_caller`, `vc_pre_call_coverage_qc`,
  `vc_post_call_qc_summary`, `vc_annotate_variants_snpeff`).
- `tests/test_mcp_tools.py`: happy-path and missing-param tests for all ten tools.
- Tool name constants and TOOL_DESCRIPTIONS entries added to `mcp_contract.py`.
- All ten tools registered in `create_mcp_server()` and added to EXPERIMENT_LOOP_TOOLS.
```
