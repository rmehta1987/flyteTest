# Step 08 — `germline_short_variant_discovery` Workflow

## Goal

Add the `germline_short_variant_discovery` workflow to
`src/flytetest/workflows/variant_calling.py` and register it.

## Context

- Plan §4: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Stargazer reference:
  `stargazer/src/stargazer/workflows/germline_short_variant_discovery.py`.
- All sub-tasks and sub-workflows exist: `preprocess_sample` (Step 07),
  `haplotype_caller` (Milestone A Step 07), `combine_gvcfs` (Milestone A
  Step 08), `joint_call_gvcfs` (Milestone A Step 09).
- FLyteTest is synchronous — per-sample loop is a Python `for` loop,
  NOT `asyncio.gather`. Never use `async def` or `await`.

## What to build

### Workflow function

```python
@variant_calling_env.task
def germline_short_variant_discovery(
    ref_path: str,
    sample_ids: list[str],
    r1_paths: list[str],
    known_sites: list[str],
    intervals: list[str],
    cohort_id: str,
    results_dir: str,
    r2_paths: list[str] | None = None,
    sif_path: str = "",
) -> dict:
    """
    End-to-end germline short variant discovery from raw reads to joint VCF.

    Steps (per sample, sequential):
    1. preprocess_sample — align, sort, dedup, BQSR
    2. haplotype_caller  — per-sample GVCF

    Then cohort-level:
    3. combine_gvcfs     — merge per-sample GVCFs
    4. joint_call_gvcfs  — GenomicsDBImport + GenotypeGVCFs
    """
    if len(sample_ids) != len(r1_paths):
        raise ValueError("sample_ids and r1_paths must be the same length")
    if r2_paths is not None and len(r2_paths) != len(sample_ids):
        raise ValueError("r2_paths must match sample_ids length when provided")

    gvcfs = []
    for i, (sid, r1) in enumerate(zip(sample_ids, r1_paths)):
        r2 = r2_paths[i] if r2_paths else ""
        sample_results = str(Path(results_dir) / sid)
        Path(sample_results).mkdir(parents=True, exist_ok=True)

        preprocessed = preprocess_sample(
            ref_path=ref_path, r1_path=r1, sample_id=sid,
            known_sites=known_sites, results_dir=sample_results,
            r2_path=r2, sif_path=sif_path,
        )
        gvcf_result = haplotype_caller(
            ref_path=ref_path, bam_path=preprocessed["preprocessed_bam"],
            sample_id=sid, results_dir=sample_results, sif_path=sif_path,
        )
        gvcfs.append(gvcf_result["gvcf"])

    combined = combine_gvcfs(
        ref_path=ref_path, gvcf_paths=gvcfs,
        cohort_id=cohort_id, results_dir=results_dir, sif_path=sif_path,
    )
    joint = joint_call_gvcfs(
        ref_path=ref_path, sample_ids=sample_ids, gvcfs=gvcfs,
        intervals=intervals, cohort_id=cohort_id,
        results_dir=results_dir, sif_path=sif_path,
    )

    manifest = build_manifest_envelope(
        task_name="germline_short_variant_discovery",
        results_dir=results_dir,
        outputs={"genotyped_vcf": joint["joint_vcf"]},
    )
    _write_json(manifest, results_dir, "run_manifest.json")
    return manifest
```

### `MANIFEST_OUTPUT_KEYS` update

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "prepared_ref",
    "preprocessed_bam",
    "genotyped_vcf",  # ← new
)
```

### Registry entry

```python
RegistryEntry(
    name="germline_short_variant_discovery",
    category="workflow",
    description="End-to-end germline SNP and indel discovery from raw reads to joint-genotyped VCF.",
    pipeline_family="variant_calling",
    pipeline_stage_order=3,
    showcase_module="",
    accepted_planner_types=("ReferenceGenome", "ReadPair", "KnownSites"),
    produced_planner_types=("VariantCallSet",),
    inputs=[
        InterfaceField("ref_path", "str", "Absolute path to reference FASTA."),
        InterfaceField("sample_ids", "list[str]", "Sample identifiers."),
        InterfaceField("r1_paths", "list[str]", "R1 FASTQ paths, 1:1 with sample_ids."),
        InterfaceField("known_sites", "list[str]", "Indexed known-sites VCF paths."),
        InterfaceField("intervals", "list[str]", "Genomic intervals for GenomicsDBImport."),
        InterfaceField("cohort_id", "str", "Cohort identifier."),
        InterfaceField("results_dir", "str", "Output directory."),
        InterfaceField("r2_paths", "list[str]", "Optional R2 FASTQ paths (None for single-end)."),
        InterfaceField("sif_path", "str", "Optional GATK4/BWA SIF image path."),
    ],
    outputs=[
        InterfaceField("genotyped_vcf", "str", "Path to joint-genotyped VCF."),
    ],
    compatibility=RegistryCompatibilityMetadata(
        local_resources={"cpu": "8", "memory": "32Gi"},
        slurm_hints={"cpus_per_task": 16, "mem": "64G", "time": "48:00:00"},
    ),
)
```

### Tests (`tests/test_variant_calling_workflows.py`)

Add `GermlineShortVariantDiscoveryRegistryTests`,
`GermlineShortVariantDiscoveryInvocationTests`,
`GermlineShortVariantDiscoveryManifestTests`:

- Registry entry shape (category="workflow", stage_order=3).
- `ValueError` when `sample_ids` length differs from `r1_paths`.
- `ValueError` when `r2_paths` is provided but length mismatches.
- With mocked sub-steps: `preprocess_sample` and `haplotype_caller` called
  once per sample; `combine_gvcfs` and `joint_call_gvcfs` called once.
- Correct GVCF list passed to `combine_gvcfs` and `joint_call_gvcfs`.
- Manifest emits `"genotyped_vcf"`.

### `CHANGELOG.md`

```
### GATK Milestone B Step 08 — germline_short_variant_discovery workflow (YYYY-MM-DD)
- [x] YYYY-MM-DD added `germline_short_variant_discovery` to workflow module.
- [x] YYYY-MM-DD added registry entry (category=workflow, stage_order 3).
- [x] YYYY-MM-DD extended workflow MANIFEST_OUTPUT_KEYS with `"genotyped_vcf"`.
- [x] YYYY-MM-DD added N tests; all tests passing.
```

## Commit message

```
variant_calling: add germline_short_variant_discovery workflow + registry entry
```

## Hard constraints for this step

- The per-sample loop MUST be a synchronous `for` loop — no `async def`,
  no `await`, no `asyncio.gather`. This is enforced by the grep gate in §8
  of the milestone plan.
- `r2_paths=None` must be handled gracefully (single-end or pre-paired mode).

## Checklist

- [ ] `germline_short_variant_discovery` in workflow module; synchronous loop.
- [ ] Input length validation (`ValueError` on mismatches).
- [ ] Per-sample subdirectory created under `results_dir`.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"genotyped_vcf"`.
- [ ] Registry entry category="workflow", stage_order=3.
- [ ] Tests: validation errors, call counts, GVCF list threading, manifest.
- [ ] `pytest tests/test_variant_calling_workflows.py -xvs` green.
- [ ] `pytest tests/test_registry_manifest_contract.py -xvs` green.
- [ ] CHANGELOG updated.
- [ ] Step 08 marked Complete in checklist.
