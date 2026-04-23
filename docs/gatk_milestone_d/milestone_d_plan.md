# GATK4 Germline Variant Calling — Milestone D

Two VQSR tasks, a `genotype_refinement` workflow, a full-chr20 NA12878
fixture bundle, and a training-VCF download script.

Source-of-truth references:

- `AGENTS.md` — hard constraints, efficiency notes, core rules.
- `DESIGN.md` — biological pipeline boundaries, planner types.
- `.codex/tasks.md`, `.codex/registry.md`, `.codex/workflows.md` — patterns.
- Milestone A plan: `docs/gatk_milestone_a/milestone_a_plan.md`.
- Milestone B plan: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Stargazer VQSR reference (read-only):
  - `stargazer/src/stargazer/tasks/gatk/variant_recalibrator.py`
  - `stargazer/src/stargazer/tasks/gatk/apply_vqsr.py`

## §1 Context

Milestones A–C delivered the full germline short-variant pipeline (raw reads →
joint-called VCF) plus cluster validation prompt sets. The joint VCF emitted
by `germline_short_variant_discovery` uses hard filters by default; VQSR
(Variant Quality Score Recalibration) is the statistically calibrated
alternative and the recommended production path for cohorts with enough
variants to train.

- **Milestone A** (complete) — seven GATK4 tasks, registry family.
- **Milestone B** (complete) — preprocessing tasks, three workflows.
- **Milestone C** (complete) — cluster validation prompt sets.
- **Milestone D** (this plan) — VQSR tasks, genotype_refinement workflow,
  full-chr20 fixture bundle, training-VCF download script.

Stargazer is async/IPFS; FLyteTest is synchronous/filesystem. Stargazer source
determines command argument ordering and output naming only; everything above
the tool invocation is re-implemented against FLyteTest patterns. No
`async def`, `await`, `asyncio.gather`, `.cid`, IPFS, Pinata, or TinyDB.

## §2 Pillars / Invariants (carried from Milestones A–C)

1. **Freeze before execute.** Tasks emit `run_manifest.json` via
   `build_manifest_envelope`; registry-manifest contract test enforces alignment.
2. **Typed surfaces everywhere.** Registry interface fields stay typed
   (`InterfaceField(name, type, description)`), not prose.
3. **Manifest envelope per task.** Every task and workflow emits
   `run_manifest.json`.
4. **No Stargazer-pattern bleed-in.** Grep gate in §8 must pass.

## §3 Data Model

### No new planner type

`KnownSites` already carries VQSR-facing fields added anticipatorily in
Milestone A (`training: bool`, `truth: bool`, `prior: float | None`,
`vqsr_mode: str | None`). No new type is needed.

`variant_recalibrator` emits `recal_file` and `tranches_file` as manifest
keys (path strings). `apply_vqsr` accepts them as path-string inputs — the
same pattern used by `bqsr_report` → `apply_bqsr`.

### New `MANIFEST_OUTPUT_KEYS` additions — tasks module

```python
"recal_file",      # variant_recalibrator
"tranches_file",   # variant_recalibrator
"vqsr_vcf",        # apply_vqsr
```

Full tuple after Step 02:

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    # Milestone A
    "sequence_dict", "feature_index", "bqsr_report",
    "recalibrated_bam", "gvcf", "combined_gvcf", "joint_vcf",
    # Milestone B
    "bwa_index_prefix", "aligned_bam", "sorted_bam",
    "dedup_bam", "duplicate_metrics",
    # Milestone D
    "recal_file", "tranches_file", "vqsr_vcf",
)
```

### New `MANIFEST_OUTPUT_KEYS` additions — workflows module

```python
"refined_vcf",     # genotype_refinement
```

### Registry stage orders

Tasks continue the Milestone B sequence:

| stage_order | task |
|---|---|
| 1–11 | Milestone A + B tasks (unchanged) |
| 12 | `variant_recalibrator` |
| 13 | `apply_vqsr` |

Workflow uses `pipeline_stage_order` 4 within category `"workflow"`.

## §4 Implementation Notes

### variant_recalibrator

```
gatk VariantRecalibrator
    -R <ref.fa>
    -V <joint.vcf.gz>
    -mode <SNP|INDEL>
    -O <cohort_id>_<mode.lower()>.recal
    --tranches-file <cohort_id>_<mode.lower()>.tranches
    --resource:<name>,known=<bool>,training=<bool>,truth=<bool>,prior=<float> <vcf>
        (one --resource flag per KnownSites entry)
    -an QD -an MQ -an MQRankSum -an ReadPosRankSum -an FS -an SOR  (SNP)
    -an QD -an FS -an SOR                                           (INDEL)
```

Per-resource flag format mirrors Stargazer: `--resource:{name},known={known},training={training},truth={truth},prior={prior}`.
`known` / `training` / `truth` are `"true"` / `"false"` strings (GATK expects lowercase).
`prior` is a float converted to string; default `"10"` if `None`.

Outputs (`recal_file`, `tranches_file`) go in `results_dir`; both appear in
manifest and registry outputs.

### apply_vqsr

```
gatk ApplyVQSR
    -R <ref.fa>
    -V <in.vcf.gz>
    --recal-file <recal_file>
    --tranches-file <tranches_file>
    --truth-sensitivity-filter-level <level>
    --create-output-variant-index true
    -mode <SNP|INDEL>
    -O <cohort_id>_vqsr_<mode.lower()>.vcf.gz
```

`truth_sensitivity_filter_level` defaults: `99.5` for SNP, `99.0` for INDEL
(matches Stargazer's `_DEFAULT_FILTER_LEVEL`).

Output VCF is `.vcf.gz`; `--create-output-variant-index true` writes a
companion `.vcf.gz.tbi`.

### genotype_refinement workflow

```python
# SNP pass
snp_recal, snp_tranches = variant_recalibrator(
    ref_path, joint_vcf, snp_resources, "SNP", cohort_id, results_dir, sif_path)
snp_vcf = apply_vqsr(
    ref_path, joint_vcf, snp_recal, snp_tranches, "SNP", cohort_id,
    results_dir, snp_filter_level, sif_path)

# INDEL pass on SNP-filtered VCF
indel_recal, indel_tranches = variant_recalibrator(
    ref_path, snp_vcf, indel_resources, "INDEL", cohort_id, results_dir, sif_path)
refined_vcf = apply_vqsr(
    ref_path, snp_vcf, indel_recal, indel_tranches, "INDEL", cohort_id,
    results_dir, indel_filter_level, sif_path)
→ emit manifest: refined_vcf = refined_vcf
```

INDEL pass consumes the SNP-filtered VCF, not the original joint VCF.

### Fixture bundle — `variant_calling_vqsr_chr20`

A new `ResourceBundle` in `src/flytetest/bundles.py`. This is a
documentation bundle pointing at real data that must be staged:

- Reference FASTA: `data/references/hg38/chr20.fa` (full chr20 from
  `Homo_sapiens_assembly38.fasta`, matching the CRAM alignment reference)
- Input VCF: `data/vcf/NA12878_chr20_joint.vcf.gz` (joint-called VCF
  produced by running `germline_short_variant_discovery` on the full-chr20
  NA12878 BAM — the user supplies this)
- Training VCFs (downloaded by `scripts/rcc/download_vqsr_training_vcfs.sh`):

| KnownSites entry | Path | training | truth | prior | vqsr_mode |
|---|---|---|---|---|---|
| hapmap | `data/references/hg38/hapmap_3.3.hg38.vcf.gz` | true | true | 15.0 | SNP |
| omni | `data/references/hg38/1000G_omni2.5.hg38.vcf.gz` | true | true | 12.0 | SNP |
| 1000g_snps | `data/references/hg38/1000G_phase1.snps.high_confidence.hg38.vcf.gz` | true | false | 10.0 | SNP |
| mills | `data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz` | true | true | 12.0 | INDEL |
| dbsnp | `data/references/hg38/Homo_sapiens_assembly38.dbsnp138.vcf` | false | false | 2.0 | both |

`applies_to`: `("variant_recalibrator", "apply_vqsr", "genotype_refinement")`

### Training-VCF download script — `scripts/rcc/download_vqsr_training_vcfs.sh`

Downloads the five training VCFs + their indices from
`gs://gcp-public-data--broad-references/hg38/v0/` using `gsutil cp`.
The NA12878 chr20 BAM/FASTQ is staged by the user separately (SCP from
local storage — too large for automated download in a script).

## §5 Backward Compatibility

Milestone D is purely additive:

- `MANIFEST_OUTPUT_KEYS` in tasks module extended (new keys only).
- `MANIFEST_OUTPUT_KEYS` in workflows module extended (new key only).
- Two new tasks appended to `variant_calling.py`.
- One new workflow appended to `workflows/variant_calling.py`.
- New registry entries appended to `VARIANT_CALLING_ENTRIES`.
- `bundles.py` gains one new entry (additive).
- `scripts/rcc/download_vqsr_training_vcfs.sh` is new (no existing script
  changed).

## §6 Steps

### VQSR Tasks

| # | Step | Prompt |
|---|------|--------|
| 01 | `variant_recalibrator` task + registry entry + unit test | `prompts/step_01_variant_recalibrator.md` |
| 02 | `apply_vqsr` task + registry entry + unit test | `prompts/step_02_apply_vqsr.md` |

### Workflow Composition

| # | Step | Prompt |
|---|------|--------|
| 03 | `genotype_refinement` workflow + registry entries + unit test | `prompts/step_03_genotype_refinement_workflow.md` |

### Fixture and Tooling

| # | Step | Prompt |
|---|------|--------|
| 04 | Fixture bundle + training-VCF download script | `prompts/step_04_fixture_and_download_script.md` |

### Closure

| # | Step | Prompt |
|---|------|--------|
| 05 | Tool ref + agent-context sweep + CHANGELOG + submission prompt | `prompts/step_05_closure.md` |

## §7 Out of Scope (this milestone)

- `merge_bam_alignment` (uBAM workflow path) — deferred.
- Interval-scoped HaplotypeCaller — deferred.
- Genotype refinement beyond VQSR (e.g. `CalculateGenotypePosteriors`) —
  deferred.
- Downloading the full NA12878 chr20 BAM/CRAM — user-supplied via SCP.
- Running `germline_short_variant_discovery` to produce the input VCF —
  covered by Milestone B workflow; documented in bundle fetch_hints.

## §8 Verification Gates

All must pass before marking Milestone D complete:

- `python -m compileall src/flytetest/` clean.
- `pytest tests/test_variant_calling.py -xvs` green.
- `pytest tests/test_variant_calling_workflows.py -xvs` green.
- `pytest tests/test_registry_manifest_contract.py -xvs` green.
- `pytest` full suite green.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits.
- `rg "variant_recalibrator|apply_vqsr|genotype_refinement" src/flytetest/registry/_variant_calling.py` → matches.

## §9 Hard Constraints

- No frozen-artifact mutation at retry/replay time.
- No Slurm submit without a frozen run record.
- No change to `classify_slurm_failure()` semantics.
- No async/IPFS/TinyDB patterns in ported code.
- Do not implement `merge_bam_alignment` or interval-scoped calling —
  out of scope.
