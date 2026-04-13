#!/usr/bin/env bash
set -euo pipefail

# Run the Trinity, STAR, and StringTie smoke sequence that feeds the PASA
# smoke paths.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Top-level project-local results tree for the whole smoke workflow.
SMOKE_ROOT="${SMOKE_ROOT:-$REPO_ROOT/results/minimal_transcriptomics_smoke}"

mkdir -p "$SMOKE_ROOT"

# The transcriptomics smoke must run first because PASA reuses the Trinity FASTA it emits.
bash "$SCRIPT_DIR/check_minimal_fixtures.sh"

# Separate stage directories keep the Trinity, STAR, and StringTie outputs easy to inspect.
TRINITY_SMOKE_DIR="$SMOKE_ROOT/trinity"
STAR_SMOKE_DIR="$SMOKE_ROOT/star"
STRINGTIE_SMOKE_DIR="$SMOKE_ROOT/stringtie"

mkdir -p "$TRINITY_SMOKE_DIR" "$STAR_SMOKE_DIR" "$STRINGTIE_SMOKE_DIR"

TRINITY_CPU="${TRINITY_CPU:-2}"
TRINITY_MAX_MEMORY_GB="${TRINITY_MAX_MEMORY_GB:-4}"
STAR_THREADS="${STAR_THREADS:-2}"
STRINGTIE_THREADS="${STRINGTIE_THREADS:-2}"
# Minimal paired reads used by Trinity and STAR alignment.
LEFT_FASTQ="${LEFT_FASTQ:-$REPO_ROOT/data/transcriptomics/ref-based/reads_1.fq.gz}"
RIGHT_FASTQ="${RIGHT_FASTQ:-$REPO_ROOT/data/transcriptomics/ref-based/reads_2.fq.gz}"
# Minimal reference genome for STAR indexing.
HOST_GENOME_FASTA="${HOST_GENOME_FASTA:-$REPO_ROOT/data/braker3/reference/genome.fa}"
# Minimal merged RNA-seq BAM used by StringTie.
INPUT_BAM="${INPUT_BAM:-$REPO_ROOT/data/braker3/rnaseq/RNAseq.bam}"

echo "transcriptomics smoke root: $SMOKE_ROOT"
echo "trinity reads: $LEFT_FASTQ"
echo "trinity reads: $RIGHT_FASTQ"
echo "star genome: $HOST_GENOME_FASTA"
echo "stringtie bam: $INPUT_BAM"

# Run Trinity first to produce the transcript FASTA consumed later by PASA.
WORK_DIR="$TRINITY_SMOKE_DIR" \
LEFT_FASTQ="$LEFT_FASTQ" \
RIGHT_FASTQ="$RIGHT_FASTQ" \
TRINITY_CPU="$TRINITY_CPU" \
TRINITY_MAX_MEMORY_GB="$TRINITY_MAX_MEMORY_GB" \
bash "$SCRIPT_DIR/trinity.sh"

# Build the STAR genome index in the same smoke scratch tree.
WORK_DIR="$STAR_SMOKE_DIR" \
HOST_GENOME_FASTA="$HOST_GENOME_FASTA" \
STAR_THREADS="$STAR_THREADS" \
MODE=index \
bash "$SCRIPT_DIR/star.sh"

# Reuse the STAR index for the alignment run.
WORK_DIR="$STAR_SMOKE_DIR" \
HOST_GENOME_FASTA="$HOST_GENOME_FASTA" \
LEFT_FASTQ="$LEFT_FASTQ" \
RIGHT_FASTQ="$RIGHT_FASTQ" \
STAR_THREADS="$STAR_THREADS" \
MODE=align \
bash "$SCRIPT_DIR/star.sh"

# Run StringTie against the merged BAM fixture.
WORK_DIR="$STRINGTIE_SMOKE_DIR" \
INPUT_BAM="$INPUT_BAM" \
STRINGTIE_THREADS="$STRINGTIE_THREADS" \
bash "$SCRIPT_DIR/stringtie.sh"

echo "minimal transcriptomics smoke completed"
echo "results root: $SMOKE_ROOT"
