#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-$REPO_ROOT}"
CONTAINER_PROJECT_DIR="${CONTAINER_PROJECT_DIR:-/workspace}"
WORK_DIR="${WORK_DIR:-$PWD/temp}"
MODE="${MODE:-index}" # index | align

STAR_SIF="${STAR_SIF:-/project/rcc/hyadav/genomes/software/STAR.sif}"
STAR_THREADS="${STAR_THREADS:-4}"
HOST_GENOME_FASTA="${HOST_GENOME_FASTA:-$HOST_PROJECT_DIR/data/braker3/reference/genome.fa}"
STAR_INDEX_DIR="${STAR_INDEX_DIR:-/tmp/star_index}"
HOST_STAR_INDEX_DIR="${HOST_STAR_INDEX_DIR:-$WORK_DIR/star_index}"
HOST_LEFT_FASTQ="${HOST_LEFT_FASTQ:-$HOST_PROJECT_DIR/data/transcriptomics/ref-based/reads_1.fq.gz}"
HOST_RIGHT_FASTQ="${HOST_RIGHT_FASTQ:-$HOST_PROJECT_DIR/data/transcriptomics/ref-based/reads_2.fq.gz}"

require_dir "$WORK_DIR"
require_file "$STAR_SIF"

to_container_path() {
  local path="$1"
  printf '%s\n' "${path//$HOST_PROJECT_DIR/$CONTAINER_PROJECT_DIR}"
}

case "$MODE" in
  index)
    require_file "$HOST_GENOME_FASTA"
    require_dir "$HOST_STAR_INDEX_DIR"
    echo "STAR index input genome: $HOST_GENOME_FASTA"
    echo "STAR index output dir: $HOST_STAR_INDEX_DIR"

    runtime_exec "$STAR_SIF" STAR \
      --runMode genomeGenerate \
      --runThreadN "$STAR_THREADS" \
      --genomeDir "$STAR_INDEX_DIR" \
      --genomeFastaFiles "$(to_container_path "$HOST_GENOME_FASTA")"
    ;;

  align)
    HOST_GENOME_DIR="${HOST_GENOME_DIR:-$HOST_STAR_INDEX_DIR}"
    GENOME_DIR="${GENOME_DIR:-$STAR_INDEX_DIR}"
    LEFT_FASTQ="${LEFT_FASTQ:-$HOST_LEFT_FASTQ}"
    RIGHT_FASTQ="${RIGHT_FASTQ:-$HOST_RIGHT_FASTQ}"
    STAR_ALIGN_DIR="${STAR_ALIGN_DIR:-$WORK_DIR/star_alignment}"
    require_dir "$HOST_GENOME_DIR"
    require_file "$LEFT_FASTQ"
    require_file "$RIGHT_FASTQ"
    require_dir "$STAR_ALIGN_DIR"
    echo "STAR align genome dir: $HOST_GENOME_DIR"
    echo "STAR align reads: $LEFT_FASTQ"
    echo "STAR align reads: $RIGHT_FASTQ"
    echo "STAR align output dir: $STAR_ALIGN_DIR"

    cmd=(
      STAR
      --runThreadN "$STAR_THREADS"
      --genomeDir "$GENOME_DIR"
      --readFilesIn "$(to_container_path "$LEFT_FASTQ")" "$(to_container_path "$RIGHT_FASTQ")"
      --outSAMtype BAM SortedByCoordinate
      --outFileNamePrefix "$STAR_ALIGN_DIR/"
    )

    if [[ "$LEFT_FASTQ" == *.gz && "$RIGHT_FASTQ" == *.gz ]]; then
      cmd+=(--readFilesCommand zcat)
    fi

    runtime_exec "$STAR_SIF" "${cmd[@]}"
    ;;

  *)
    echo "MODE must be index or align" >&2
    exit 2
    ;;
esac
