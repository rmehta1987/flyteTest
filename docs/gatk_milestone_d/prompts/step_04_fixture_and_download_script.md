# Step 04 — Fixture Bundle + Training-VCF Download Script

## Model

**Haiku 4.5** (`claude-haiku-4-5-20251001`). Mechanical work: write a bash
download script and add a documented bundle entry to `bundles.py`. All paths
and flag values are given explicitly below; no architectural judgment required.

## Goal

Add the `variant_calling_vqsr_chr20` bundle to `src/flytetest/bundles.py`
and create `scripts/rcc/download_vqsr_training_vcfs.sh` that pulls the five
VQSR training VCFs from GCS.

## Context

- Milestone D plan §4: `docs/gatk_milestone_d/milestone_d_plan.md`.
- Existing bundle pattern: `variant_calling_germline_minimal` in
  `src/flytetest/bundles.py` (lines 126–174) — copy the structure verbatim.
- Existing download script pattern: `scripts/rcc/pull_gatk_image.sh`.
- The NA12878 chr20 BAM/FASTQ is user-supplied via SCP — do not attempt to
  automate its download. The script only handles training VCFs.
- `gsutil` must be available on the cluster; add a preflight check.
- All five training VCFs are at
  `gs://gcp-public-data--broad-references/hg38/v0/`.

## What to build

### `scripts/rcc/download_vqsr_training_vcfs.sh`

```bash
#!/usr/bin/env bash
# Download GATK4 VQSR training VCFs from the Broad public GCS reference bundle.
# Requires: gsutil on PATH, write access to data/references/hg38/
# Usage: bash scripts/rcc/download_vqsr_training_vcfs.sh [output_dir]
#
# The NA12878 chr20 BAM/FASTQ must be staged separately (SCP from local storage).
# See the variant_calling_vqsr_chr20 bundle in src/flytetest/bundles.py.
set -euo pipefail

OUTDIR="${1:-data/references/hg38}"
mkdir -p "$OUTDIR"

BUCKET="gs://gcp-public-data--broad-references/hg38/v0"

FILES=(
    "hapmap_3.3.hg38.vcf.gz"
    "hapmap_3.3.hg38.vcf.gz.tbi"
    "1000G_omni2.5.hg38.vcf.gz"
    "1000G_omni2.5.hg38.vcf.gz.tbi"
    "1000G_phase1.snps.high_confidence.hg38.vcf.gz"
    "1000G_phase1.snps.high_confidence.hg38.vcf.gz.tbi"
    "Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"
    "Mills_and_1000G_gold_standard.indels.hg38.vcf.gz.tbi"
    "Homo_sapiens_assembly38.dbsnp138.vcf"
    "Homo_sapiens_assembly38.dbsnp138.vcf.idx"
)

for f in "${FILES[@]}"; do
    echo "Downloading $f ..."
    gsutil cp "$BUCKET/$f" "$OUTDIR/$f"
done

echo "Done. Training VCFs written to: $OUTDIR"
echo "Stage NA12878 chr20 BAM/FASTQ separately (SCP from local storage)."
```

Make it executable (`chmod +x`).

### `src/flytetest/bundles.py`

Add a `ResourceBundle` named `"variant_calling_vqsr_chr20"` after
`variant_calling_germline_minimal`. Copy the `ResourceBundle(...)` call
structure exactly from the existing entry.

Field values:

```python
name="variant_calling_vqsr_chr20",
description=(
    "Full-chr20 NA12878 WGS germline VQSR demo. "
    "Uses a joint-called VCF from germline_short_variant_discovery plus "
    "five GATK Best Practices training VCFs for SNP + INDEL recalibration. "
    "Reference data from gs://gcp-public-data--broad-references/hg38/v0/. "
    "NA12878 chr20 BAM and VCF are user-staged (SCP); "
    "training VCFs are downloaded by scripts/rcc/download_vqsr_training_vcfs.sh."
),
pipeline_family="variant_calling",
bindings={
    "ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"},
    "VariantCallSet": {
        "vcf_path": "data/vcf/NA12878_chr20_joint.vcf.gz",
        "variant_type": "vcf",
        "sample_id": "NA12878_chr20",
    },
},
inputs={
    "ref_path": "data/references/hg38/chr20.fa",
    "joint_vcf": "data/vcf/NA12878_chr20_joint.vcf.gz",
    "snp_resources": [
        "data/references/hg38/hapmap_3.3.hg38.vcf.gz",
        "data/references/hg38/1000G_omni2.5.hg38.vcf.gz",
        "data/references/hg38/1000G_phase1.snps.high_confidence.hg38.vcf.gz",
        "data/references/hg38/Homo_sapiens_assembly38.dbsnp138.vcf",
    ],
    "snp_resource_flags": [
        {"resource_name": "hapmap",   "known": "false", "training": "true",  "truth": "true",  "prior": "15"},
        {"resource_name": "omni",     "known": "false", "training": "true",  "truth": "true",  "prior": "12"},
        {"resource_name": "1000g",    "known": "false", "training": "true",  "truth": "false", "prior": "10"},
        {"resource_name": "dbsnp",    "known": "true",  "training": "false", "truth": "false", "prior": "2"},
    ],
    "indel_resources": [
        "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz",
        "data/references/hg38/Homo_sapiens_assembly38.dbsnp138.vcf",
    ],
    "indel_resource_flags": [
        {"resource_name": "mills",  "known": "false", "training": "true",  "truth": "true",  "prior": "12"},
        {"resource_name": "dbsnp",  "known": "true",  "training": "false", "truth": "false", "prior": "2"},
    ],
    "cohort_id": "NA12878_chr20",
    "results_dir": "results/vqsr_chr20/",
},
runtime_images={"sif_path": "data/images/gatk4.sif"},
tool_databases={
    "hapmap":  "data/references/hg38/hapmap_3.3.hg38.vcf.gz",
    "omni":    "data/references/hg38/1000G_omni2.5.hg38.vcf.gz",
    "1000g":   "data/references/hg38/1000G_phase1.snps.high_confidence.hg38.vcf.gz",
    "mills":   "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz",
    "dbsnp":   "data/references/hg38/Homo_sapiens_assembly38.dbsnp138.vcf",
},
applies_to=(
    "variant_recalibrator",
    "apply_vqsr",
    "genotype_refinement",
),
fetch_hints=(
    "Download training VCFs: bash scripts/rcc/download_vqsr_training_vcfs.sh",
    "Stage NA12878 chr20 BAM via SCP; run germline_short_variant_discovery to produce the joint VCF at data/vcf/NA12878_chr20_joint.vcf.gz",
    "Pull GATK4 SIF image: bash scripts/rcc/pull_gatk_image.sh",
    "chr20.fa must match the Homo_sapiens_assembly38.fasta reference used for alignment (contig name 'chr20', not '20')",
),
```

### `CHANGELOG.md`

```
### GATK Milestone D Step 04 — VQSR fixture bundle + download script (YYYY-MM-DD)
- [x] YYYY-MM-DD added variant_calling_vqsr_chr20 bundle to src/flytetest/bundles.py.
- [x] YYYY-MM-DD created scripts/rcc/download_vqsr_training_vcfs.sh.
```

## Verification

```bash
test -f scripts/rcc/download_vqsr_training_vcfs.sh
test -x scripts/rcc/download_vqsr_training_vcfs.sh
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/bundles.py
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c "
from flytetest.bundles import load_bundle
b = load_bundle('variant_calling_vqsr_chr20')
assert b['inputs']['cohort_id'] == 'NA12878_chr20'
assert len(b['inputs']['snp_resource_flags']) == 4
assert len(b['inputs']['indel_resource_flags']) == 2
print('OK: bundle loads correctly')
"
rg "variant_calling_vqsr_chr20" src/flytetest/bundles.py
```

## Commit message

```
variant_calling: add VQSR fixture bundle + training-VCF download script
```

## Checklist

- [ ] `scripts/rcc/download_vqsr_training_vcfs.sh` created and executable.
- [ ] Script downloads all 10 files (5 VCFs + 5 indices).
- [ ] Script contains the SCP note for the NA12878 chr20 data.
- [ ] `variant_calling_vqsr_chr20` bundle added after
  `variant_calling_germline_minimal` in `bundles.py`.
- [ ] `snp_resource_flags` has 4 entries (hapmap, omni, 1000g, dbsnp).
- [ ] `indel_resource_flags` has 2 entries (mills, dbsnp).
- [ ] `applies_to` covers all three VQSR targets.
- [ ] Bundle loads cleanly from Python.
- [ ] CHANGELOG updated.
- [ ] Step 04 marked Complete in `docs/gatk_milestone_d/checklist.md`.
