#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PASA_SMOKE_ROOT="${PASA_SMOKE_ROOT:-$REPO_ROOT/temp/minimal_pasa_smoke}"
TRANSCRIPTOMICS_SMOKE_ROOT="${TRANSCRIPTOMICS_SMOKE_ROOT:-$REPO_ROOT/temp/minimal_transcriptomics_smoke}"
TRINITY_OUTPUT_DIR="${TRINITY_OUTPUT_DIR:-$TRANSCRIPTOMICS_SMOKE_ROOT/trinity/trinity_out_dir}"
HOST_PASA_WORK_DIR="${HOST_PASA_WORK_DIR:-$PASA_SMOKE_ROOT/pasa}"
STAGED_TRINITY_FASTA="${STAGED_TRINITY_FASTA:-$HOST_PASA_WORK_DIR/trinity_transcripts.fa}"

require_file() {
  local path="$1"
  [[ -f "$path" ]] || {
    echo "missing file: $path" >&2
    exit 1
  }
  [[ -s "$path" ]] || {
    echo "empty file: $path" >&2
    exit 1
  }
}

require_dir() {
  local path="$1"
  [[ -d "$path" ]] || {
    echo "missing directory: $path" >&2
    exit 1
  }
}

require_dir "$TRINITY_OUTPUT_DIR"
require_file "$TRINITY_OUTPUT_DIR/Trinity.fasta"
require_dir "$HOST_PASA_WORK_DIR"
require_file "$STAGED_TRINITY_FASTA"

SEQCLEAN_CLEAN_FASTA="$(find "$HOST_PASA_WORK_DIR" -maxdepth 1 -type f -name '*.clean' | sort | head -n 1)"
if [[ -z "$SEQCLEAN_CLEAN_FASTA" ]]; then
  echo "missing PASA seqclean .clean file under: $HOST_PASA_WORK_DIR" >&2
  exit 1
fi
require_file "$SEQCLEAN_CLEAN_FASTA"

TDN_FILE="${TDN_FILE:-$HOST_PASA_WORK_DIR/tdn.accs}"
require_file "$TDN_FILE"

echo "minimal PASA smoke artifacts are present"
echo "trinity fasta: $TRINITY_OUTPUT_DIR/Trinity.fasta"
echo "seqclean clean fasta: $SEQCLEAN_CLEAN_FASTA"
echo "tdn accessions: $TDN_FILE"
