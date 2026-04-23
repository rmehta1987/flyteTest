# GATK4 Germline Variant Calling — Milestone G

`CalculateGenotypePosteriors` task, `post_genotyping_refinement` workflow,
and full GATK pipeline closure documentation.

Source-of-truth references:

- `AGENTS.md`, `DESIGN.md`, `.codex/` — project rules and patterns.
- Milestones A–F plans under `docs/gatk_milestone_*/`.
- GATK Best Practices docs (no Stargazer reference — CGP is not in Stargazer).

## §1 Context

Milestones A–F delivered: BQSR, GVCF calling, joint genotyping, VQSR, uBAM
preprocessing, and interval-scattered calling. The remaining standard
Best Practices step is `CalculateGenotypePosteriors` (CGP): a post-joint-
genotyping tool that refines per-sample genotype probabilities using
population-level priors from a supporting callset (e.g., 1000 Genomes).

Milestone G adds CGP as a standalone task and wires it into a
`post_genotyping_refinement` workflow that accepts any joint VCF (hard-
filtered or VQSR-filtered) and optionally applies CGP. It also closes the
GATK pipeline story with an end-to-end pipeline reference document.

## §2 Pillars / Invariants

Same four pillars as Milestones A–F. No new exceptions.

## §3 Data Model

### No new planner type.

### New `MANIFEST_OUTPUT_KEYS` additions — tasks module

```python
"cgp_vcf",    # calculate_genotype_posteriors
```

### New `MANIFEST_OUTPUT_KEYS` additions — workflows module

```python
"refined_vcf_cgp",    # post_genotyping_refinement
```

### Registry stage orders

| stage_order | item |
|---|---|
| 1–15 | Milestones A–F (unchanged) |
| 16 | `calculate_genotype_posteriors` |

Workflow uses `pipeline_stage_order` 7 within category `"workflow"`.

## §4 Implementation Notes

### calculate_genotype_posteriors

```
gatk CalculateGenotypePosteriors \
  -V <joint_or_vqsr_vcf> \
  -O <cohort_id>_cgp.vcf.gz \
  [--supporting-callsets <supporting_vcf>] \
  --create-output-variant-index true
```

`--supporting-callsets` is optional. When provided it should point to a
population VCF such as `1000G_omni2.5.hg38.vcf.gz`. When omitted, CGP runs
with pedigree-only priors (still valid for trios; less useful for unrelated
samples).

Output: `<cohort_id>_cgp.vcf.gz` with companion `.tbi`.
Raises `FileNotFoundError` if output absent after run.

Signature:

```python
def calculate_genotype_posteriors(
    ref_path: str,
    vcf_path: str,
    cohort_id: str,
    results_dir: str,
    supporting_callsets: list[str] | None = None,
    sif_path: str = "",
) -> dict:
```

Manifest outputs: `{"cgp_vcf": str(output_vcf)}`.

### post_genotyping_refinement workflow

```python
cgp = calculate_genotype_posteriors(
    ref_path, vcf_path, cohort_id, results_dir,
    supporting_callsets, sif_path)
emit manifest: refined_vcf_cgp = cgp["outputs"]["cgp_vcf"]
```

Signature:

```python
def post_genotyping_refinement(
    ref_path: str,
    vcf_path: str,
    cohort_id: str,
    results_dir: str,
    supporting_callsets: list[str] | None = None,
    sif_path: str = "",
) -> dict:
```

`vcf_path` accepts both joint-called VCFs (from `joint_call_gvcfs`) and
VQSR-filtered VCFs (from `genotype_refinement`). The workflow is intentionally
thin — one task call — to keep it composable.

### End-to-end pipeline reference doc

`docs/gatk_pipeline_overview.md` — a ≤150-line reference covering:

1. The full pipeline DAG from raw input to final VCF in plain text.
2. Two entry paths: FASTQ path (`preprocess_sample`) and uBAM path
   (`preprocess_sample_from_ubam`).
3. Two calling modes: whole-genome (`haplotype_caller`) and scattered
   (`scattered_haplotype_caller`).
4. Two refinement paths: VQSR (`genotype_refinement`) and CGP
   (`post_genotyping_refinement`), composable in sequence.
5. Table of all tasks and workflows with their stage numbers and milestone.
6. Pointers to fixture bundles and download scripts.

## §5 Backward Compatibility

Purely additive. No existing task or workflow is modified.

## §6 Steps

| # | Step | Prompt |
|---|------|--------|
| 01 | `calculate_genotype_posteriors` task + registry + tests | `prompts/step_01_calculate_genotype_posteriors.md` |
| 02 | `post_genotyping_refinement` workflow + registry + tests | `prompts/step_02_post_genotyping_refinement.md` |
| 03 | End-to-end pipeline reference doc + GATK pipeline closure | `prompts/step_03_closure.md` |

## §7 Out of Scope (this milestone)

- `VariantFiltration` (hard-filtering) — not part of Best Practices for
  deep WGS; users run VQSR or CGP.
- `GenotypeGVCFs` re-genotyping after CGP — out of scope.
- VQSR on CGP output — users compose `genotype_refinement` → `post_genotyping_refinement` themselves.

## §8 Verification Gates

- `python -m compileall src/flytetest/` clean.
- `pytest tests/test_variant_calling.py -xvs` green.
- `pytest tests/test_variant_calling_workflows.py -xvs` green.
- `pytest tests/test_registry_manifest_contract.py -xvs` green.
- `pytest` full suite green.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits.
- `rg "calculate_genotype_posteriors|post_genotyping_refinement" src/flytetest/registry/_variant_calling.py` → matches.
- `test -f docs/gatk_pipeline_overview.md && wc -l docs/gatk_pipeline_overview.md` ≤150 lines.
