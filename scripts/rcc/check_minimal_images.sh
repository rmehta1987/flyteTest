#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_IMAGE_ROOT="/project/rcc/hyadav/genomes/software"

check_file() {
  local path="$1"
  local label="${2:-$1}"
  local abs_path="$path"

  if [[ "$path" != /* ]]; then
    abs_path="$REPO_ROOT/$path"
  fi

  if [[ ! -e "$abs_path" ]]; then
    echo "missing image: $label" >&2
    missing=1
  fi
}

required_files=(
  "data/images/trinity_2.13.2.sif"
  "data/images/star_2.7.10b.sif"
  "data/images/stringtie_2.2.3.sif"
  "data/images/braker3.sif"
  "data/images/busco_v6.0.0_cv1.sif"
)

missing=0
for rel_path in "${required_files[@]}"; do
  check_file "$rel_path"
done

check_file "${PASA_SIF:-data/images/pasa_2.5.3.sif}" "PASA image (${PASA_SIF:-data/images/pasa_2.5.3.sif})"

if [[ -d "$PROJECT_IMAGE_ROOT" ]]; then
  check_file "$PROJECT_IMAGE_ROOT/trinityrnaseq.v2.15.2.simg" "cluster Trinity image ($PROJECT_IMAGE_ROOT/trinityrnaseq.v2.15.2.simg)"
  check_file "$PROJECT_IMAGE_ROOT/STAR.sif" "cluster STAR image ($PROJECT_IMAGE_ROOT/STAR.sif)"
  check_file "$PROJECT_IMAGE_ROOT/StringTie.sif" "cluster StringTie image ($PROJECT_IMAGE_ROOT/StringTie.sif)"
else
  echo "skipping cluster image checks; $PROJECT_IMAGE_ROOT is not present" >&2
fi

if [[ "$missing" -ne 0 ]]; then
  echo "checked under: $REPO_ROOT" >&2
  exit 1
fi

echo "all minimal smoke images are present"
