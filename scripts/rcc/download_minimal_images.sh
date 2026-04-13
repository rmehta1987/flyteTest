#!/usr/bin/env bash
set -euo pipefail

# Restore the minimal container images under data/images/ for the local smoke
# wrappers.
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
    echo "skip $dest (already exists)"
    return 0
  fi

  rm -f "$dest"
  "$RUNTIME" pull "$dest" "$source"
  echo "downloaded $dest"
}

echo "restoring minimal smoke images into $IMAGE_DIR"

pull_image \
  "$IMAGE_DIR/trinity_2.13.2.sif" \
  "docker://quay.io/biocontainers/trinity:2.13.2--h15cb65e_2"

pull_image \
  "$IMAGE_DIR/star_2.7.10b.sif" \
  "docker://quay.io/biocontainers/star:2.7.10b--h9ee0642_0"

pull_image \
  "$IMAGE_DIR/stringtie_2.2.3.sif" \
  "docker://quay.io/biocontainers/stringtie:2.2.3--h43eeafb_0"

pull_image \
  "$IMAGE_DIR/pasa_2.5.3.sif" \
  "docker://pasapipeline/pasapipeline:2.5.3"

pull_image \
  "$IMAGE_DIR/exonerate_2.2.0--1.sif" \
  "docker://quay.io/biocontainers/exonerate:2.2.0--1"

cat <<'EOF'
Done.

Next steps:
- run the local smoke tests with the images in data/images/
- if the PASA image layout differs, point PASA_SIF at the downloaded image explicitly
EOF
