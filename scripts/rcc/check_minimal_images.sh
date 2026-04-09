#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

required_files=(
  "data/images/trinity_2.13.2.sif"
  "data/images/star_2.7.10b.sif"
  "data/images/stringtie_2.2.3.sif"
  "data/images/pasa_2.5.3.sif"
  "data/images/braker3.sif"
  "data/images/busco_v6.0.0_cv1.sif"
)

missing=0
for rel_path in "${required_files[@]}"; do
  abs_path="$REPO_ROOT/$rel_path"
  if [[ ! -e "$abs_path" ]]; then
    echo "missing image: $rel_path" >&2
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "checked under: $REPO_ROOT" >&2
  exit 1
fi

echo "all minimal smoke images are present under $REPO_ROOT/data/images"
