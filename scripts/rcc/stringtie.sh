#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-$REPO_ROOT}"
CONTAINER_PROJECT_DIR="${CONTAINER_PROJECT_DIR:-/workspace}"
WORK_DIR="${WORK_DIR:-$PWD/temp}"

STRINGTIE_SIF="${STRINGTIE_SIF:-/project/rcc/hyadav/genomes/software/StringTie.sif}"
STRINGTIE_THREADS="${STRINGTIE_THREADS:-4}"
INPUT_BAM="${INPUT_BAM:-$HOST_PROJECT_DIR/data/braker3/rnaseq/RNAseq.bam}"
CONTAINER_INPUT_BAM="${CONTAINER_INPUT_BAM:-${INPUT_BAM//$HOST_PROJECT_DIR/$CONTAINER_PROJECT_DIR}}"
HOST_OUT_DIR="${HOST_OUT_DIR:-${OUT_DIR:-$WORK_DIR/stringtie}}"
CONTAINER_OUT_DIR="${CONTAINER_OUT_DIR:-/tmp/stringtie}"
OUT_GTF="${OUT_GTF:-$CONTAINER_OUT_DIR/stringtie_yeast.gtf}"
OUT_ABUNDANCE="${OUT_ABUNDANCE:-$CONTAINER_OUT_DIR/stringtie_yeast_abundances.txt}"

require_dir "$WORK_DIR"
require_file "$STRINGTIE_SIF"

require_file "$INPUT_BAM"
require_dir "$HOST_OUT_DIR"

runtime_exec "$STRINGTIE_SIF" stringtie "$CONTAINER_INPUT_BAM" \
  -p "$STRINGTIE_THREADS" \
  -o "$OUT_GTF" \
  -l STRG \
  -f 0.10 \
  -A "$OUT_ABUNDANCE" \
  -c 3 \
  -j 3
