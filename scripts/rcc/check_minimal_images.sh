#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_IMAGE_ROOT="/project/rcc/hyadav/genomes/software"

# Check a repo-local file or a cluster-mounted absolute path.
check_file() {
  local path="$1"
  local label="${2:-$1}"
  local abs_path="$path"

  if [[ "$path" != /* ]]; then
    abs_path="$REPO_ROOT/$path"
  fi

  if [[ ! -e "$abs_path" ]]; then
    echo "missing artifact: $label" >&2
    missing=1
  else
    echo "found artifact: $label"
  fi
}

# Repo-local smoke images that should exist in every checkout.
required_files=(
  "data/images/trinity_2.13.2.sif"
  "data/images/star_2.7.10b.sif"
  "data/images/stringtie_2.2.3.sif"
  "data/images/braker3.sif"
  "data/images/busco_v6.0.0_cv1.sif"
  "data/images/exonerate_2.2.0--1.sif"
)

missing=0
for rel_path in "${required_files[@]}"; do
  check_file "$rel_path"
done

# Allow the PASA image path to be overridden for a scp'd cluster copy.
check_file "${PASA_SIF:-data/images/pasa_2.5.3.sif}" "PASA image (${PASA_SIF:-data/images/pasa_2.5.3.sif})"

if [[ -d "$PROJECT_IMAGE_ROOT" ]]; then
# Verify the shared cluster Trinity and STAR image defaults plus the StringTie binary.
  check_file "$PROJECT_IMAGE_ROOT/trinityrnaseq.v2.15.2.simg" "cluster Trinity image ($PROJECT_IMAGE_ROOT/trinityrnaseq.v2.15.2.simg)"
  check_file "$PROJECT_IMAGE_ROOT/STAR.sif" "cluster STAR image ($PROJECT_IMAGE_ROOT/STAR.sif)"
  check_file "$PROJECT_IMAGE_ROOT/stringtie/stringtie" "cluster StringTie binary ($PROJECT_IMAGE_ROOT/stringtie/stringtie)"
else
  echo "skipping cluster image checks; $PROJECT_IMAGE_ROOT is not present" >&2
fi

if [[ "$missing" -ne 0 ]]; then
  echo "checked under: $REPO_ROOT" >&2
  exit 1
fi

echo "all minimal smoke artifacts are present"
