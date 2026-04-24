#!/usr/bin/env bash
# Verify all files required by the variant_calling_germline_minimal bundle
# are present before running a local smoke test.
#
# Usage: bash scripts/rcc/check_gatk_fixtures.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

required_files=(
    "data/references/hg38/chr20.fa"
    "data/references/hg38/chr20.fa.fai"
    "data/references/hg38/dbsnp_138.hg38.vcf.gz"
    "data/references/hg38/dbsnp_138.hg38.vcf.gz.tbi"
    "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"
    "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz.tbi"
    "data/reads/NA12878_chr20_R1.fastq.gz"
    "data/reads/NA12878_chr20_R2.fastq.gz"
    "data/images/gatk4.sif"
    "data/images/bwa_mem2.sif"
)

missing=0
for rel in "${required_files[@]}"; do
    abs="$REPO_ROOT/$rel"
    if [[ ! -e "$abs" ]]; then
        echo "MISSING: $rel" >&2
        missing=1
    else
        size=$(du -sh "$abs" 2>/dev/null | cut -f1)
        echo "OK ($size): $rel"
    fi
done

echo ""
if [[ "$missing" -ne 0 ]]; then
    echo "Fix missing files:" >&2
    echo "  Reference data + reads: bash scripts/rcc/stage_gatk_local.sh" >&2
    echo "  GATK SIF:               bash scripts/rcc/pull_gatk_image.sh" >&2
    echo "  bwa-mem2 SIF:           bash scripts/rcc/build_bwa_mem2_sif.sh" >&2
    exit 1
fi

echo "All GATK fixtures present under $REPO_ROOT"
echo ""
echo "SIF smoke tests:"
echo "  apptainer exec data/images/gatk4.sif   gatk --version"
echo "  apptainer exec data/images/bwa_mem2.sif bwa-mem2 version"
echo "  apptainer exec data/images/bwa_mem2.sif samtools --version"
