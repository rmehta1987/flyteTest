#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Host project root bound into the image runtime.
HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-$REPO_ROOT}"
# Container project root used by the image runtime.
CONTAINER_PROJECT_DIR="${CONTAINER_PROJECT_DIR:-/workspace}"
# Root directory that collects the PASA image smoke inputs and outputs.
IMAGE_SMOKE_ROOT="${IMAGE_SMOKE_ROOT:-$REPO_ROOT/results/minimal_pasa_image_smoke}"
# Host PASA workspace used for the image-backed smoke run.
HOST_PASA_WORK_DIR="${HOST_PASA_WORK_DIR:-$IMAGE_SMOKE_ROOT/pasa}"
# Container view of the same PASA workspace.
CONTAINER_PASA_WORK_DIR="${CONTAINER_PASA_WORK_DIR:-/workspace/results/minimal_pasa_image_smoke/pasa}"
# Repo-local transcriptomics smoke root that provides the Trinity FASTA.
TRANSCRIPTOMICS_SMOKE_ROOT="${TRANSCRIPTOMICS_SMOKE_ROOT:-$REPO_ROOT/results/minimal_transcriptomics_smoke}"
# Trinity transcript FASTA emitted by the transcriptomics smoke.
TRINITY_OUTPUT_DIR="${TRINITY_OUTPUT_DIR:-$TRANSCRIPTOMICS_SMOKE_ROOT/trinity/trinity_out_dir}"
# Reference genome used by the image-backed smoke.
HOST_GENOME_FASTA="${HOST_GENOME_FASTA:-$REPO_ROOT/data/braker3/reference/genome.fa}"
# PASA image used for the Docker/wiki-style smoke.
PASA_SIF="${PASA_SIF:-$(resolve_smoke_image PASA_SIF "$REPO_ROOT/data/images/pasa_2.5.3.sif" "/project/rcc/hyadav/genomes/software/PASA.sif")}"
# Container view of the genome FASTA.
CONTAINER_GENOME_FASTA="${CONTAINER_GENOME_FASTA:-/workspace/data/braker3/reference/genome.fa}"
# Container view of the staged transcript FASTA.
CONTAINER_TRANSCRIPTS_FASTA="${CONTAINER_TRANSCRIPTS_FASTA:-/workspace/results/minimal_pasa_image_smoke/pasa/transcripts/transcripts.cdna.fasta}"
# PASA config staged inside the smoke workspace.
HOST_PASA_CONFIG="${HOST_PASA_CONFIG:-$HOST_PASA_WORK_DIR/config/alignAssembly.conf}"
CONTAINER_PASA_CONFIG="${CONTAINER_PASA_CONFIG:-/workspace/results/minimal_pasa_image_smoke/pasa/config/alignAssembly.conf}"
PASA_CPU="${PASA_CPU:-2}"
PASA_ALIGNER="${PASA_ALIGNER:-gmap}"
WORK_DIR="${WORK_DIR:-$IMAGE_SMOKE_ROOT/runtime}"

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

# Remove Trinity header annotations so PASA sees a simple accession-style FASTA.
stage_sanitized_fasta() {
  local source="$1"
  local dest="$2"
  # PASA's wiki example uses a cDNA-like FASTA without descriptive Trinity headers.
  awk 'BEGIN { OFS = "" } /^>/ { sub(/ .*/, "") } { print }' "$source" >"$dest"
}

# Validate the source inputs before staging the PASA workspace.
require_dir "$TRINITY_OUTPUT_DIR"
require_file "$HOST_GENOME_FASTA"
require_file "$PASA_SIF"
require_dir "$HOST_PASA_WORK_DIR"

# Rebuild the smoke workspace from scratch on each run.
rm -rf "$IMAGE_SMOKE_ROOT"
mkdir -p "$WORK_DIR"
mkdir -p "$HOST_PASA_WORK_DIR/transcripts" "$HOST_PASA_WORK_DIR/reference" \
  "$HOST_PASA_WORK_DIR/config"

TRINITY_FASTA="$(find_trinity_fasta "$TRINITY_OUTPUT_DIR")"
STAGED_TRANSCRIPTS_FASTA="$HOST_PASA_WORK_DIR/transcripts/transcripts.cdna.fasta"
STAGED_GENOME_FASTA="$HOST_PASA_WORK_DIR/reference/genome.fa"

cp -f "$HOST_GENOME_FASTA" "$STAGED_GENOME_FASTA"
stage_sanitized_fasta "$TRINITY_FASTA" "$STAGED_TRANSCRIPTS_FASTA"

# Keep the SQLite database inside the container-visible PASA workspace.
CONTAINER_DATABASE_PATH="$CONTAINER_PASA_WORK_DIR/minimal_pasa_image.sqlite"
cat >"$HOST_PASA_CONFIG" <<EOF
DATABASE=$CONTAINER_DATABASE_PATH
OTHER=1
EOF

echo "PASA image smoke root: $IMAGE_SMOKE_ROOT"
echo "PASA work dir: $HOST_PASA_WORK_DIR"
echo "Trinity FASTA source: $TRINITY_FASTA"
echo "Staged transcripts FASTA: $STAGED_TRANSCRIPTS_FASTA"
echo "Genome FASTA: $STAGED_GENOME_FASTA"
echo "PASA config: $HOST_PASA_CONFIG"
echo "PASA image: $PASA_SIF"

# Run the same PASA entrypoint inside the Apptainer image.
runtime_exec "$PASA_SIF" bash -lc \
  "cd '$CONTAINER_PASA_WORK_DIR' && /usr/local/src/PASApipeline/Launch_PASA_pipeline.pl -c '$CONTAINER_PASA_CONFIG' -C -R --ALIGNERS '$PASA_ALIGNER' --CPU '$PASA_CPU' -g '$CONTAINER_GENOME_FASTA' -t '$CONTAINER_TRANSCRIPTS_FASTA'"

echo "minimal PASA image smoke completed"
