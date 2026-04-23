#!/usr/bin/env bash
# Download GATK4 VQSR training VCFs from the Broad public GCS reference bundle.
# Requires: gsutil on PATH, write access to data/references/hg38/
# Usage: bash scripts/rcc/download_vqsr_training_vcfs.sh [output_dir]
#
# The NA12878 chr20 BAM/FASTQ must be staged separately (SCP from local storage).
# See the variant_calling_vqsr_chr20 bundle in src/flytetest/bundles.py.
set -euo pipefail

if ! command -v gsutil &>/dev/null; then
    echo "ERROR: gsutil not found on PATH. Install the Google Cloud SDK first." >&2
    exit 1
fi

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
