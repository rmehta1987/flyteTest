#!/usr/bin/env bash
# Stage all data required by the variant_calling_germline_minimal bundle
# for a local smoke test on the dev laptop.
#
# What this downloads / generates:
#   data/references/hg38/chr20.fa          — chr20 reference FASTA (~65 MB)
#   data/references/hg38/chr20.fa.fai      — samtools index (generated locally)
#   data/references/hg38/dbsnp_138.hg38.vcf.gz     — chr20 slice of dbSNP 138
#   data/references/hg38/dbsnp_138.hg38.vcf.gz.tbi — tabix index
#   data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz     — chr20 slice
#   data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz.tbi
#   data/reads/NA12878_chr20_R1.fastq.gz   — synthetic reads (wgsim, smoke-test only)
#   data/reads/NA12878_chr20_R2.fastq.gz
#
# Requires: samtools, tabix, bgzip, wgsim, wget or curl (all installed natively)
# Does NOT download the GATK SIF — run pull_gatk_image.sh for that.
#
# Usage:
#   bash scripts/rcc/stage_gatk_local.sh          # synthetic reads (fast, default)
#   REAL_READS=1 bash scripts/rcc/stage_gatk_local.sh  # placeholder only (see note)
#   FORCE=1 bash scripts/rcc/stage_gatk_local.sh  # re-download even if files exist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

REFDIR="$REPO_ROOT/data/references/hg38"
READSDIR="$REPO_ROOT/data/reads"
FORCE="${FORCE:-0}"
REAL_READS="${REAL_READS:-0}"

BROAD_GCS="https://storage.googleapis.com/gcp-public-data--broad-references/hg38/v0"

mkdir -p "$REFDIR" "$READSDIR"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

skip_or_continue() {
    local path="$1"
    if [[ -e "$path" && "$FORCE" != "1" ]]; then
        echo "skip $(basename "$path") (already exists)"
        return 1
    fi
    return 0
}

fetch() {
    local url="$1" dest="$2"
    local tmp="${dest}.download"
    rm -f "$tmp"
    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 --retry-delay 5 -o "$tmp" "$url"
    else
        wget -O "$tmp" "$url"
    fi
    mv "$tmp" "$dest"
}

# ---------------------------------------------------------------------------
# 1. chr20 reference FASTA
# ---------------------------------------------------------------------------

if skip_or_continue "$REFDIR/chr20.fa"; then
    echo "Downloading chr20.fa from UCSC (~65 MB) ..."
    fetch \
        "http://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr20.fa.gz" \
        "$REFDIR/chr20.fa.gz"
    gzip -d "$REFDIR/chr20.fa.gz"
    echo "Downloaded: $REFDIR/chr20.fa"
fi

if skip_or_continue "$REFDIR/chr20.fa.fai"; then
    echo "Indexing chr20.fa ..."
    samtools faidx "$REFDIR/chr20.fa"
    echo "Created: $REFDIR/chr20.fa.fai"
fi

# ---------------------------------------------------------------------------
# 2. chr20 slice of dbSNP 138
#    tabix streams just the chr20 region over HTTPS — no 10 GB full download.
# ---------------------------------------------------------------------------

if skip_or_continue "$REFDIR/dbsnp_138.hg38.vcf.gz"; then
    echo "Slicing chr20 from remote dbSNP 138 VCF via tabix (may take a few minutes) ..."
    tabix -h \
        "$BROAD_GCS/Homo_sapiens_assembly38.dbsnp138.vcf.gz" \
        chr20 \
        | bgzip > "$REFDIR/dbsnp_138.hg38.vcf.gz"
    tabix -p vcf "$REFDIR/dbsnp_138.hg38.vcf.gz"
    echo "Created: $REFDIR/dbsnp_138.hg38.vcf.gz"
fi

# ---------------------------------------------------------------------------
# 3. chr20 slice of Mills + 1000G gold-standard indels
# ---------------------------------------------------------------------------

MILLS="$REFDIR/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"
if skip_or_continue "$MILLS"; then
    echo "Slicing chr20 from remote Mills VCF via tabix ..."
    tabix -h \
        "$BROAD_GCS/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz" \
        chr20 \
        | bgzip > "$MILLS"
    tabix -p vcf "$MILLS"
    echo "Created: $MILLS"
fi

# ---------------------------------------------------------------------------
# 4. Reads — synthetic (default) or real (REAL_READS=1)
# ---------------------------------------------------------------------------

if [[ "$REAL_READS" == "1" ]]; then
    # Real NA12878 chr20 reads require manual staging from GIAB or NCBI SRA.
    # GIAB chr20 FASTQs: https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data/NA12878/
    # Download the paired FASTQs for a chr20 run, then place them at:
    #   data/reads/NA12878_chr20_R1.fastq.gz
    #   data/reads/NA12878_chr20_R2.fastq.gz
    echo ""
    echo "REAL_READS=1: manual staging required."
    echo "Place NA12878 chr20 FASTQs at:"
    echo "  $READSDIR/NA12878_chr20_R1.fastq.gz"
    echo "  $READSDIR/NA12878_chr20_R2.fastq.gz"
    echo "Source: GIAB ftp-trace.ncbi.nlm.nih.gov or NCBI SRA (SRR622461 / SRR622462)"
else
    # Generate synthetic reads with wgsim for smoke-test purposes.
    # 100 000 pairs × 2×150 bp ≈ 0.5× coverage of chr20 (63 Mbp).
    # Not biologically meaningful — use for pipeline plumbing validation only.
    if skip_or_continue "$READSDIR/NA12878_chr20_R1.fastq.gz"; then
        echo "Generating synthetic chr20 reads with wgsim (100 000 pairs, 2×150 bp) ..."
        wgsim \
            -N 100000 -1 150 -2 150 \
            -e 0.01 -d 400 -s 40 \
            -S 42 \
            "$REFDIR/chr20.fa" \
            "$READSDIR/NA12878_chr20_R1.fastq" \
            "$READSDIR/NA12878_chr20_R2.fastq"
        bgzip "$READSDIR/NA12878_chr20_R1.fastq"
        bgzip "$READSDIR/NA12878_chr20_R2.fastq"
        echo "Created: $READSDIR/NA12878_chr20_R1.fastq.gz"
        echo "Created: $READSDIR/NA12878_chr20_R2.fastq.gz"
        echo "NOTE: synthetic reads — use REAL_READS=1 for a presentation-quality run."
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Reference data staged under: $REFDIR"
echo "Reads staged under:          $READSDIR"
echo ""
echo "Next steps:"
echo "  1. Pull the GATK4 SIF (standard Broad image, ~8 GB):"
echo "       bash scripts/rcc/pull_gatk_image.sh"
echo "  2. Build the bwa-mem2+samtools SIF (~300 MB, ~5 min):"
echo "       bash scripts/rcc/build_bwa_mem2_sif.sh"
echo "  3. Verify all fixtures:"
echo "       bash scripts/rcc/check_gatk_fixtures.sh"
echo "  4. Run a dry-run smoke test:"
echo "       See SCIENTIST_GUIDE.md — GATK Germline Variant Calling"
