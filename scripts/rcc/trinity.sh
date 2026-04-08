#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Host checkout root; the wrappers default to the repo-local minimal fixtures.
HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-$REPO_ROOT}"
# Container bind target for the checkout root.
CONTAINER_PROJECT_DIR="${CONTAINER_PROJECT_DIR:-/workspace}"
# Host scratch area for Trinity outputs and temp intermediates.
WORK_DIR="${WORK_DIR:-$PWD/temp}"
MODE="${MODE:-denovo}" # denovo | genome_guided

TRINITY_SIF="${TRINITY_SIF:-/project/rcc/hyadav/genomes/software/trinityrnaseq.v2.15.2.simg}"
TRINITY_CPU="${TRINITY_CPU:-4}"
TRINITY_MAX_MEMORY_GB="${TRINITY_MAX_MEMORY_GB:-8}"
GENOME_GUIDED_MAX_INTRON="${GENOME_GUIDED_MAX_INTRON:-100000}"
# Repo-local minimal paired-end reads used by the smoke path.
HOST_FASTQ_DIR="${HOST_FASTQ_DIR:-$HOST_PROJECT_DIR/data/transcriptomics/ref-based}"
BIND_MOUNTS_EXTRA="${BIND_MOUNTS_EXTRA:-}"
# Repo-local minimal merged BAM used by the genome-guided path.
HOST_MERGED_BAM="${HOST_MERGED_BAM:-$HOST_PROJECT_DIR/data/braker3/rnaseq/RNAseq.bam}"

require_dir "$WORK_DIR"
require_file "$TRINITY_SIF"

to_container_path() {
  local path="$1"
  printf '%s\n' "${path//$HOST_PROJECT_DIR/$CONTAINER_PROJECT_DIR}"
}

case "$MODE" in
  denovo)
    [[ -d "$HOST_FASTQ_DIR" ]] || { echo "missing Trinity FASTQ directory: $HOST_FASTQ_DIR" >&2; exit 1; }
    LEFT_FASTQ="${LEFT_FASTQ:-}"
    RIGHT_FASTQ="${RIGHT_FASTQ:-}"
    if [[ -z "$LEFT_FASTQ" || -z "$RIGHT_FASTQ" ]]; then
      shopt -s nullglob
      LEFT_FILES=("$HOST_FASTQ_DIR"/*1.fastq.gz)
      RIGHT_FILES=("$HOST_FASTQ_DIR"/*2.fastq.gz)
      if [[ ${#LEFT_FILES[@]} -eq 0 || ${#RIGHT_FILES[@]} -eq 0 ]]; then
        LEFT_FILES=("$HOST_FASTQ_DIR"/*reads_1.fq.gz)
        RIGHT_FILES=("$HOST_FASTQ_DIR"/*reads_2.fq.gz)
      fi
      shopt -u nullglob
      if [[ ${#LEFT_FILES[@]} -eq 0 || ${#RIGHT_FILES[@]} -eq 0 ]]; then
        echo "missing Trinity FASTQ inputs under $HOST_FASTQ_DIR" >&2
        echo "expected one of:" >&2
        echo "  $HOST_FASTQ_DIR/*1.fastq.gz" >&2
        echo "  $HOST_FASTQ_DIR/*reads_1.fq.gz" >&2
        echo "and matching right reads patterns" >&2
        exit 1
      fi
      LEFT_FASTQ="$(printf '%s\n' "${LEFT_FILES[@]}" | paste -sd, -)"
      RIGHT_FASTQ="$(printf '%s\n' "${RIGHT_FILES[@]}" | paste -sd, -)"
    else
      require_file "$LEFT_FASTQ"
      require_file "$RIGHT_FASTQ"
    fi
    LEFT_FASTQ="$(to_container_path "$LEFT_FASTQ")"
    RIGHT_FASTQ="$(to_container_path "$RIGHT_FASTQ")"
    HOST_OUTPUT_DIR="${HOST_OUTPUT_DIR:-${OUT_DIR:-$WORK_DIR/trinity_out_dir}}"
    # Trinity writes its assembly into the mounted host output directory via /tmp.
    CONTAINER_OUT_DIR="${CONTAINER_OUT_DIR:-/tmp/trinity_out_dir}"
    require_dir "$HOST_OUTPUT_DIR"

    runtime_exec "$TRINITY_SIF" Trinity \
      --seqType fq \
      --left "$LEFT_FASTQ" \
      --right "$RIGHT_FASTQ" \
      --max_memory "${TRINITY_MAX_MEMORY_GB}G" \
      --CPU "$TRINITY_CPU" \
      --normalize_by_read_set \
      --min_kmer_cov 2 \
      --no_parallel_norm_stats \
      --output "$CONTAINER_OUT_DIR"
    ;;

  genome_guided)
    # Genome-guided Trinity writes into a separate mounted scratch directory.
    HOST_OUTPUT_DIR="${HOST_OUTPUT_DIR:-${OUT_DIR:-$WORK_DIR/trinity_gg}}"
    CONTAINER_OUT_DIR="${CONTAINER_OUT_DIR:-/tmp/trinity_gg}"
    MERGED_BAM="${MERGED_BAM:-$HOST_MERGED_BAM}"
    require_file "$MERGED_BAM"
    require_dir "$HOST_OUTPUT_DIR"

    runtime_exec "$TRINITY_SIF" Trinity \
      --genome_guided_bam "$(to_container_path "$MERGED_BAM")" \
      --genome_guided_max_intron "$GENOME_GUIDED_MAX_INTRON" \
      --CPU "$TRINITY_CPU" \
      --max_memory "${TRINITY_MAX_MEMORY_GB}G" \
      --output "$CONTAINER_OUT_DIR"
    ;;

  *)
    echo "MODE must be denovo or genome_guided" >&2
    exit 2
    ;;
esac
