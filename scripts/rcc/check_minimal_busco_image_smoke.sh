#!/usr/bin/env bash
set -euo pipefail

# Verify the BUSCO image smoke completed and left the expected short summary in
# the repo-local results tree.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BUSCO_SMOKE_ROOT="${BUSCO_SMOKE_ROOT:-$REPO_ROOT/results/minimal_busco_image_smoke}"
HOST_BUSCO_WORK_DIR="${HOST_BUSCO_WORK_DIR:-$BUSCO_SMOKE_ROOT/busco}"
BUSCO_OUTPUT_NAME="${BUSCO_OUTPUT_NAME:-test_eukaryota}"
BUSCO_OUTPUT_DIR="${BUSCO_OUTPUT_DIR:-$HOST_BUSCO_WORK_DIR/$BUSCO_OUTPUT_NAME}"
BUSCO_SIF="${BUSCO_SIF:-$REPO_ROOT/data/images/busco_v6.0.0_cv1.sif}"

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

find_output_file() {
  local root="$1"
  local pattern="$2"
  find "$root" -type f -name "$pattern" | sort | head -n 1
}

require_dir "$BUSCO_OUTPUT_DIR"

SHORT_SUMMARY="$(find_output_file "$BUSCO_OUTPUT_DIR" 'short_summary*.txt')"
if [[ -z "$SHORT_SUMMARY" ]]; then
  echo "missing BUSCO short summary under: $BUSCO_OUTPUT_DIR" >&2
  exit 1
fi
require_file "$SHORT_SUMMARY"

if ! grep -Eq 'C:.*S:.*D:.*F:.*M:' "$SHORT_SUMMARY"; then
  echo "BUSCO short summary lacks expected completeness notation: $SHORT_SUMMARY" >&2
  exit 1
fi

echo "minimal BUSCO image smoke artifacts are present"
echo "busco image: $BUSCO_SIF"
echo "busco output dir: $BUSCO_OUTPUT_DIR"
echo "busco short summary: $SHORT_SUMMARY"
