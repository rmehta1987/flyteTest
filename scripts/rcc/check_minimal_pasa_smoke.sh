#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PASA_SMOKE_ROOT="${PASA_SMOKE_ROOT:-$REPO_ROOT/temp/minimal_pasa_smoke}"
TRANSCRIPTOMICS_SMOKE_ROOT="${TRANSCRIPTOMICS_SMOKE_ROOT:-$REPO_ROOT/temp/minimal_transcriptomics_smoke}"
TRINITY_OUTPUT_DIR="${TRINITY_OUTPUT_DIR:-$TRANSCRIPTOMICS_SMOKE_ROOT/trinity/trinity_out_dir}"
HOST_PASA_WORK_DIR="${HOST_PASA_WORK_DIR:-$PASA_SMOKE_ROOT/pasa}"
STAGED_TRINITY_FASTA="${STAGED_TRINITY_FASTA:-$HOST_PASA_WORK_DIR/trinity_transcripts.fa}"
STAGED_TRINITY_GENE_TRANS_MAP="${STAGED_TRINITY_GENE_TRANS_MAP:-$HOST_PASA_WORK_DIR/trinity_transcripts.fa.gene_trans_map}"

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

find_trinity_fasta() {
  local trinity_dir="$1"
  local candidate

  for candidate in \
    "$trinity_dir/Trinity.fasta" \
    "$trinity_dir/Trinity.tmp.fasta" \
    "$trinity_dir/trinity_out_dir.Trinity.fasta" \
    "$trinity_dir/trinity_denovo.Trinity.fasta" \
    "$trinity_dir/Trinity-GG.fasta" \
    "$trinity_dir/../Trinity.fasta" \
    "$trinity_dir/../Trinity.tmp.fasta" \
    "$trinity_dir/../trinity_out_dir.Trinity.fasta"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  shopt -s nullglob
  local named_candidates=("$trinity_dir"/*.Trinity.fasta)
  local fasta_candidates=("$trinity_dir"/*.fasta)
  local tmp_candidates=("$trinity_dir"/*.tmp.fasta)
  shopt -u nullglob

  if [[ ${#named_candidates[@]} -eq 1 ]]; then
    printf '%s\n' "${named_candidates[0]}"
    return 0
  fi

  if [[ ${#fasta_candidates[@]} -eq 1 ]]; then
    printf '%s\n' "${fasta_candidates[0]}"
    return 0
  fi

  if [[ ${#tmp_candidates[@]} -eq 1 ]]; then
    printf '%s\n' "${tmp_candidates[0]}"
    return 0
  fi

  echo "unable to resolve a single Trinity FASTA under: $trinity_dir" >&2
  exit 1
}

require_dir "$TRINITY_OUTPUT_DIR"
TRINITY_FASTA="$(find_trinity_fasta "$TRINITY_OUTPUT_DIR")"
require_dir "$HOST_PASA_WORK_DIR"
require_file "$STAGED_TRINITY_FASTA"
if [[ -f "$STAGED_TRINITY_GENE_TRANS_MAP" ]]; then
  require_file "$STAGED_TRINITY_GENE_TRANS_MAP"
fi

SEQCLEAN_CLEAN_FASTA="$(find "$HOST_PASA_WORK_DIR" -maxdepth 1 -type f -name '*.clean' | sort | head -n 1)"
if [[ -z "$SEQCLEAN_CLEAN_FASTA" ]]; then
  echo "missing PASA seqclean .clean file under: $HOST_PASA_WORK_DIR" >&2
  exit 1
fi
require_file "$SEQCLEAN_CLEAN_FASTA"

TDN_FILE="${TDN_FILE:-$HOST_PASA_WORK_DIR/tdn.accs}"
require_file "$TDN_FILE"

echo "minimal PASA smoke artifacts are present"
echo "trinity fasta: $TRINITY_FASTA"
if [[ -f "$STAGED_TRINITY_GENE_TRANS_MAP" ]]; then
  echo "staged trinity gene-transcript map: $STAGED_TRINITY_GENE_TRANS_MAP"
fi
echo "seqclean clean fasta: $SEQCLEAN_CLEAN_FASTA"
echo "tdn accessions: $TDN_FILE"
