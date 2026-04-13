#!/usr/bin/env bash
set -euo pipefail

# Run the wiki-shaped PASA align/assemble smoke against the Trinity and genome
# fixtures on the host binary path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Smoke root that collects the PASA align/assemble inputs and outputs.
ALIGN_SMOKE_ROOT="${ALIGN_SMOKE_ROOT:-$REPO_ROOT/results/minimal_pasa_align_smoke}"
# Host PASA workspace used for the wiki-shaped align/assemble smoke run.
HOST_PASA_WORK_DIR="${HOST_PASA_WORK_DIR:-$ALIGN_SMOKE_ROOT/pasa}"
# Container view of the same PASA workspace.
CONTAINER_PASA_WORK_DIR="${CONTAINER_PASA_WORK_DIR:-/workspace/results/minimal_pasa_align_smoke/pasa}"
# Repo-local transcriptomics smoke root that provides the Trinity FASTA.
TRANSCRIPTOMICS_SMOKE_ROOT="${TRANSCRIPTOMICS_SMOKE_ROOT:-$REPO_ROOT/results/minimal_transcriptomics_smoke}"
# Trinity transcript FASTA emitted by the transcriptomics smoke.
TRINITY_OUTPUT_DIR="${TRINITY_OUTPUT_DIR:-$TRANSCRIPTOMICS_SMOKE_ROOT/trinity/trinity_out_dir}"
# Reference genome used by the align/assemble smoke.
HOST_GENOME_FASTA="${HOST_GENOME_FASTA:-$REPO_ROOT/data/braker3/reference/genome.fa}"
# PASA config staged inside the smoke workspace.
HOST_PASA_CONFIG="${HOST_PASA_CONFIG:-$HOST_PASA_WORK_DIR/config/pasa.alignAssembly.config}"
PASA_CPU="${PASA_CPU:-4}"
if [[ -z "${PASA_ALIGNERS:-}" ]]; then
  if command -v pblat >/dev/null 2>&1; then
    PASA_ALIGNERS="blat,gmap"
  else
    PASA_ALIGNERS="gmap"
  fi
fi
PASA_TRANSCRIBED_IS_ALIGNED_ORIENT="${PASA_TRANSCRIBED_IS_ALIGNED_ORIENT:-0}"
WORK_DIR="${WORK_DIR:-$ALIGN_SMOKE_ROOT/runtime}"

# Pick the single Trinity FASTA emitted by the transcriptomics smoke.
find_trinity_fasta() {
  local trinity_dir="$1"
  local candidate

  for candidate in \
    "$trinity_dir/Trinity.fasta" \
    "$trinity_dir/trinity_out_dir.Trinity.fasta" \
    "$trinity_dir/trinity_denovo.Trinity.fasta" \
    "$trinity_dir/Trinity-GG.fasta" \
    "$trinity_dir/../Trinity.fasta" \
    "$trinity_dir/../trinity_out_dir.Trinity.fasta" \
    "$trinity_dir/Trinity.tmp.fasta" \
    "$trinity_dir/../Trinity.tmp.fasta"; do
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

# Validate the source inputs before staging the PASA workspace.
require_dir "$TRINITY_OUTPUT_DIR"
require_file "$HOST_GENOME_FASTA"
require_dir "$HOST_PASA_WORK_DIR"
command -v Launch_PASA_pipeline.pl >/dev/null 2>&1 || {
  echo "missing host PASA Launch_PASA_pipeline.pl on PATH" >&2
  exit 1
}

# Rebuild the smoke workspace from scratch on each run.
rm -rf "$ALIGN_SMOKE_ROOT"
mkdir -p "$WORK_DIR"
mkdir -p "$HOST_PASA_WORK_DIR/transcripts" "$HOST_PASA_WORK_DIR/reference" \
  "$HOST_PASA_WORK_DIR/config"

TRINITY_FASTA="$(find_trinity_fasta "$TRINITY_OUTPUT_DIR")"
STAGED_TRINITY_FASTA="$HOST_PASA_WORK_DIR/transcripts/$(basename "$TRINITY_FASTA")"
STAGED_GENOME_FASTA="$HOST_PASA_WORK_DIR/reference/$(basename "$HOST_GENOME_FASTA")"

cp -f "$TRINITY_FASTA" "$STAGED_TRINITY_FASTA"
cp -f "$HOST_GENOME_FASTA" "$STAGED_GENOME_FASTA"

# Keep the SQLite database local to the smoke workspace.
DATABASE_PATH="$HOST_PASA_WORK_DIR/minimal_pasa_align.sqlite"
cat >"$HOST_PASA_CONFIG" <<EOF
DATABASE=$DATABASE_PATH
OTHER=1
EOF

TRANSCRIBED_FLAG=""
if [[ "$PASA_TRANSCRIBED_IS_ALIGNED_ORIENT" == "1" ]]; then
  TRANSCRIBED_FLAG="--transcribed_is_aligned_orient"
fi

echo "PASA align smoke root: $ALIGN_SMOKE_ROOT"
echo "PASA work dir: $HOST_PASA_WORK_DIR"
echo "Trinity FASTA source: $TRINITY_FASTA"
echo "Staged Trinity FASTA: $STAGED_TRINITY_FASTA"
echo "Genome FASTA: $STAGED_GENOME_FASTA"
echo "PASA config: $HOST_PASA_CONFIG"
echo "PASA binary: $(command -v Launch_PASA_pipeline.pl)"

# Run the wiki-shaped PASA command directly on the host-installed binary.
cd "$HOST_PASA_WORK_DIR"
Launch_PASA_pipeline.pl \
  -c "$HOST_PASA_CONFIG" \
  -C \
  -R \
  -g "$STAGED_GENOME_FASTA" \
  --ALIGNERS "$PASA_ALIGNERS" \
  --CPU "$PASA_CPU" \
  $TRANSCRIBED_FLAG \
  -t "$STAGED_TRINITY_FASTA"

echo "minimal PASA align smoke completed"
