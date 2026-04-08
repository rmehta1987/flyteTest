#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-$REPO_ROOT}"
CONTAINER_PROJECT_DIR="${CONTAINER_PROJECT_DIR:-/workspace}"
TRANSCRIPTOMICS_SMOKE_ROOT="${TRANSCRIPTOMICS_SMOKE_ROOT:-$REPO_ROOT/temp/minimal_transcriptomics_smoke}"
PASA_SMOKE_ROOT="${PASA_SMOKE_ROOT:-$REPO_ROOT/temp/minimal_pasa_smoke}"
WORK_DIR="${WORK_DIR:-$PASA_SMOKE_ROOT/runtime}"
HOST_PASA_WORK_DIR="${HOST_PASA_WORK_DIR:-$PASA_SMOKE_ROOT/pasa}"
CONTAINER_PASA_WORK_DIR="${CONTAINER_PASA_WORK_DIR:-$CONTAINER_PROJECT_DIR/temp/minimal_pasa_smoke/pasa}"
PASA_SIF="${PASA_SIF:-/project/rcc/hyadav/genomes/software/PASA.sif}"
SEQCLEAN_THREADS="${SEQCLEAN_THREADS:-4}"
HOST_VECTOR_SEQUENCE_PATH="${HOST_VECTOR_SEQUENCE_PATH:-/project/rcc/hyadav/genomes/scripts/RCC/PASA/UniVec}"
CONTAINER_VECTOR_SEQUENCE_PATH="${CONTAINER_VECTOR_SEQUENCE_PATH:-/project/rcc/hyadav/genomes/scripts/RCC/PASA/UniVec}"
HOST_TDN_FILE="${HOST_TDN_FILE:-$HOST_PASA_WORK_DIR/tdn.accs}"
CONTAINER_TDN_FILE="${CONTAINER_TDN_FILE:-$CONTAINER_PASA_WORK_DIR/tdn.accs}"

append_bind_mounts() {
  local existing="$1"
  local addition="$2"
  if [[ -n "$existing" ]]; then
    printf '%s,%s\n' "$existing" "$addition"
  else
    printf '%s\n' "$addition"
  fi
}

find_trinity_fasta() {
  local trinity_dir="$1"
  local candidate

  for candidate in \
    "$trinity_dir/Trinity.fasta" \
    "$trinity_dir/trinity_denovo.Trinity.fasta" \
    "$trinity_dir/Trinity-GG.fasta"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  shopt -s nullglob
  local named_candidates=("$trinity_dir"/*.Trinity.fasta)
  local fasta_candidates=("$trinity_dir"/*.fasta)
  shopt -u nullglob

  if [[ ${#named_candidates[@]} -eq 1 ]]; then
    printf '%s\n' "${named_candidates[0]}"
    return 0
  fi

  if [[ ${#fasta_candidates[@]} -eq 1 ]]; then
    printf '%s\n' "${fasta_candidates[0]}"
    return 0
  fi

  echo "Unable to resolve a single Trinity FASTA under $trinity_dir" >&2
  echo "Looked for Trinity.fasta, trinity_denovo.Trinity.fasta, Trinity-GG.fasta, and a single *.Trinity.fasta or *.fasta file." >&2
  exit 1
}

require_dir "$WORK_DIR"
require_dir "$HOST_PASA_WORK_DIR"
require_file "$PASA_SIF"

TRINITY_OUTPUT_DIR="${TRINITY_OUTPUT_DIR:-$TRANSCRIPTOMICS_SMOKE_ROOT/trinity/trinity_out_dir}"
[[ -d "$TRINITY_OUTPUT_DIR" ]] || {
  echo "missing Trinity output directory: $TRINITY_OUTPUT_DIR" >&2
  echo "run scripts/rcc/minimal_transcriptomics_smoke.sh first" >&2
  exit 1
}

TRINITY_FASTA="$(find_trinity_fasta "$TRINITY_OUTPUT_DIR")"
STAGED_TRINITY_FASTA="$HOST_PASA_WORK_DIR/trinity_transcripts.fa"
cp -f "$TRINITY_FASTA" "$STAGED_TRINITY_FASTA"

echo "PASA smoke root: $PASA_SMOKE_ROOT"
echo "Trinity output dir: $TRINITY_OUTPUT_DIR"
echo "Trinity FASTA source: $TRINITY_FASTA"
echo "PASA staged input: $STAGED_TRINITY_FASTA"
echo "PASA work dir: $HOST_PASA_WORK_DIR"
echo "PASA UniVec: $HOST_VECTOR_SEQUENCE_PATH"

PASA_BIND_MOUNTS_EXTRA="$(append_bind_mounts "${BIND_MOUNTS_EXTRA:-}" "/project/rcc/hyadav/genomes:/project/rcc/hyadav/genomes")"

WORK_DIR="$WORK_DIR" \
HOST_PROJECT_DIR="$HOST_PROJECT_DIR" \
CONTAINER_PROJECT_DIR="$CONTAINER_PROJECT_DIR" \
BIND_MOUNTS_EXTRA="$PASA_BIND_MOUNTS_EXTRA" \
PASA_SIF="$PASA_SIF" \
HOST_PASA_WORK_DIR="$HOST_PASA_WORK_DIR" \
CONTAINER_PASA_WORK_DIR="$CONTAINER_PASA_WORK_DIR" \
HOST_TRANSCRIPTS_UNTRIMMED_PATH="$STAGED_TRINITY_FASTA" \
CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH="$CONTAINER_PASA_WORK_DIR/trinity_transcripts.fa" \
HOST_VECTOR_SEQUENCE_PATH="$HOST_VECTOR_SEQUENCE_PATH" \
CONTAINER_VECTOR_SEQUENCE_PATH="$CONTAINER_VECTOR_SEQUENCE_PATH" \
MODE=seqclean \
bash "$SCRIPT_DIR/pasa.sh"

SEQCLEAN_CLEAN_FASTA="$(find "$HOST_PASA_WORK_DIR" -maxdepth 1 -type f -name '*.clean' | sort | head -n 1)"
if [[ -z "$SEQCLEAN_CLEAN_FASTA" ]]; then
  echo "PASA seqclean did not produce a cleaned FASTA under $HOST_PASA_WORK_DIR" >&2
  exit 1
fi
echo "PASA clean FASTA: $SEQCLEAN_CLEAN_FASTA"

WORK_DIR="$WORK_DIR" \
HOST_PROJECT_DIR="$HOST_PROJECT_DIR" \
CONTAINER_PROJECT_DIR="$CONTAINER_PROJECT_DIR" \
BIND_MOUNTS_EXTRA="$PASA_BIND_MOUNTS_EXTRA" \
PASA_SIF="$PASA_SIF" \
HOST_PASA_WORK_DIR="$HOST_PASA_WORK_DIR" \
CONTAINER_PASA_WORK_DIR="$CONTAINER_PASA_WORK_DIR" \
HOST_TRANSCRIPTS_UNTRIMMED_PATH="$STAGED_TRINITY_FASTA" \
CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH="$CONTAINER_PASA_WORK_DIR/trinity_transcripts.fa" \
HOST_TDN_FILE="$HOST_TDN_FILE" \
CONTAINER_TDN_FILE="$CONTAINER_TDN_FILE" \
HOST_VECTOR_SEQUENCE_PATH="$HOST_VECTOR_SEQUENCE_PATH" \
CONTAINER_VECTOR_SEQUENCE_PATH="$CONTAINER_VECTOR_SEQUENCE_PATH" \
MODE=accession_extract \
bash "$SCRIPT_DIR/pasa.sh"

if [[ ! -f "$HOST_TDN_FILE" ]]; then
  echo "PASA accession extract did not produce $HOST_TDN_FILE" >&2
  exit 1
fi

echo "PASA TDN accessions: $HOST_TDN_FILE"
echo "minimal PASA smoke completed"
echo "results root: $PASA_SMOKE_ROOT"
