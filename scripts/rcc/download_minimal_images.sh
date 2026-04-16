#!/usr/bin/env bash
set -euo pipefail

# Download all container images required for the annotation pipeline.
# Skips images that already exist unless FORCE=1 is set.
#
# Run from an authenticated RCC login session where apptainer is available.
# See docs/annotation_pipeline_setup.md for database/library requirements
# (RepeatMasker library, eggNOG database) that must be staged separately.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_DIR="${IMAGE_DIR:-$REPO_ROOT/data/images}"
FORCE="${FORCE:-0}"

mkdir -p "$IMAGE_DIR"

if ! command -v apptainer >/dev/null 2>&1 && ! command -v singularity >/dev/null 2>&1; then
  echo "Need apptainer or singularity on PATH to download container images." >&2
  exit 1
fi

RUNTIME="${RUNTIME:-$(command -v apptainer 2>/dev/null || command -v singularity)}"

pull_image() {
  local dest="$1"
  local source="$2"

  if [[ -e "$dest" && "$FORCE" != "1" ]]; then
    echo "skip  $dest (already exists)"
    return 0
  fi

  rm -f "$dest"
  "$RUNTIME" pull "$dest" "$source"
  echo "done  $dest"
}

echo "image dir: $IMAGE_DIR"
echo "runtime:   $RUNTIME"
echo "force:     $FORCE"
echo ""

# --- Transcript evidence ---
pull_image \
  "$IMAGE_DIR/trinity_2.13.2.sif" \
  "docker://quay.io/biocontainers/trinity:2.13.2--h15cb65e_2"

pull_image \
  "$IMAGE_DIR/star_2.7.10b.sif" \
  "docker://quay.io/biocontainers/star:2.7.10b--h9ee0642_0"

pull_image \
  "$IMAGE_DIR/stringtie_2.2.3.sif" \
  "docker://quay.io/biocontainers/stringtie:2.2.3--h43eeafb_0"

# --- PASA + protein evidence ---
pull_image \
  "$IMAGE_DIR/pasa_2.5.3.sif" \
  "docker://pasapipeline/pasapipeline:2.5.3"

pull_image \
  "$IMAGE_DIR/exonerate_2.2.0--1.sif" \
  "docker://quay.io/biocontainers/exonerate:2.2.0--1"

# --- TransDecoder ---
pull_image \
  "$IMAGE_DIR/transdecoder_6.0.0.sif" \
  "docker://quay.io/biocontainers/transdecoder:6.0.0--pl5321hdfd78af_0"

# --- BRAKER3 ---
pull_image \
  "$IMAGE_DIR/braker3.sif" \
  "docker://teambraker/braker3:latest"

# --- RepeatMasker ---
# Requires a repeat library (Dfam/RepBase) bind-mounted at runtime.
# See docs/annotation_pipeline_setup.md.
pull_image \
  "$IMAGE_DIR/repeatmasker_4.2.3.sif" \
  "docker://quay.io/biocontainers/repeatmasker:4.2.3--pl5321hdfd78af_0"

# --- EVidenceModeler (EVM 2.x — Python CLI, not Perl 1.x) ---
pull_image \
  "$IMAGE_DIR/evidencemodeler_2.1.0.sif" \
  "docker://quay.io/biocontainers/evidencemodeler:2.1.0--h9948957_5"

# --- BUSCO ---
pull_image \
  "$IMAGE_DIR/busco_v6.0.0_cv1.sif" \
  "docker://ezlabgva/busco:v6.0.0_cv1"

# --- eggNOG-mapper ---
# Requires the eggNOG database (~50 GB) staged separately and bind-mounted.
# See docs/annotation_pipeline_setup.md.
pull_image \
  "$IMAGE_DIR/eggnog_mapper_2.1.13.sif" \
  "docker://quay.io/biocontainers/eggnog-mapper:2.1.13--pyhdfd78af_2"

# --- AGAT ---
pull_image \
  "$IMAGE_DIR/agat_1.7.0.sif" \
  "docker://quay.io/biocontainers/agat:1.7.0--pl5321hdfd78af_0"

cat <<'EOF'

All images processed. Before running the full annotation pipeline:

  RepeatMasker  — repeat library (Dfam/RepBase) must be bind-mounted at runtime.
  eggNOG-mapper — eggNOG database (~50 GB) must be staged and bind-mounted.
  EVM 2.x       — uses Python CLI; verify task wrappers use 2.x command flags.
  TransDecoder  — BLAST or CD-HIT must be available via module load in the job.

See docs/annotation_pipeline_setup.md for bind-mount paths and setup steps.
EOF
