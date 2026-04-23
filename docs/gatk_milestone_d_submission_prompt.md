# GATK Milestone D — Submission Prompt

Branch: `gatkport-d`

Milestone D adds VQSR (Variant Quality Score Recalibration) to the germline
variant calling pipeline. It ports `variant_recalibrator` and `apply_vqsr`
from the Stargazer reference, wires them into a two-pass `genotype_refinement`
workflow (SNP pass on the joint VCF, INDEL pass on the SNP-filtered VCF), and
supplies a full-chr20 NA12878 fixture bundle backed by the Broad public GCS
reference bundle. Training VCFs are downloaded by a new helper script; the
NA12878 chr20 BAM is user-staged via SCP.

## What Was Built

- `variant_recalibrator` — GATK4 VariantRecalibrator task (stage 12). Accepts
  parallel `known_sites` / `known_sites_flags` lists. SNP annotations: QD, MQ,
  MQRankSum, ReadPosRankSum, FS, SOR. INDEL annotations: QD, FS, SOR.
- `apply_vqsr` — GATK4 ApplyVQSR task (stage 13). Defaults 99.5 SNP / 99.0
  INDEL filter level; always emits `.vcf.gz` with `.tbi` companion.
- `genotype_refinement` — two-pass VQSR workflow (stage 4). INDEL pass
  consumes the SNP-filtered VCF, not the original joint VCF.
- `variant_calling_vqsr_chr20` bundle — full-chr20 NA12878 WGS demo with 4 SNP
  resources (HapMap, Omni, 1000G, dbSNP) and 2 INDEL resources (Mills, dbSNP).
- `scripts/rcc/download_vqsr_training_vcfs.sh` — downloads 10 files (5 VCFs +
  5 indices) from `gs://gcp-public-data--broad-references/hg38/v0/`.

## Key Files

| File | Role |
|---|---|
| `src/flytetest/tasks/variant_calling.py` | `variant_recalibrator`, `apply_vqsr` + updated `MANIFEST_OUTPUT_KEYS` |
| `src/flytetest/workflows/variant_calling.py` | `genotype_refinement` + updated `MANIFEST_OUTPUT_KEYS` |
| `src/flytetest/registry/_variant_calling.py` | Registry entries at stages 12, 13 (tasks) and 4 (workflow) |
| `src/flytetest/bundles.py` | `variant_calling_vqsr_chr20` bundle |
| `scripts/rcc/download_vqsr_training_vcfs.sh` | GCS download script for training VCFs |
| `tests/test_variant_calling.py` | 16 new tests (VariantRecalibrator + ApplyVQSR) |
| `tests/test_variant_calling_workflows.py` | 4 new tests (GenotypeRefinement) |
| `docs/tool_refs/gatk4.md` | `variant_recalibrator` and `apply_vqsr` sections added |

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling_workflows.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" \
  src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "variant_recalibrator|apply_vqsr|genotype_refinement" src/flytetest/registry/_variant_calling.py
```

## Scope Boundaries

- `merge_bam_alignment` (uBAM path) — deferred.
- Interval-scoped HaplotypeCaller — deferred.
- `CalculateGenotypePosteriors` — deferred.
- NA12878 chr20 full-depth BAM — user-staged via SCP; not automated.

## Not Implemented (by design)

- `async def` / `await` / `asyncio.gather` patterns.
- IPFS / Pinata / TinyDB patterns.
