#!/usr/bin/env bash
# Build the bwa-mem2 + samtools Apptainer image used by bwa_mem2_index and bwa_mem2_mem tasks.
#
# Usage: bash scripts/rcc/pull_bwa_mem2_sif.sh [output_path]
#
# Requires: apptainer on PATH, internet access (downloads bwa-mem2 v2.3 from GitHub releases).
# Disk:     ~300 MB for the finished SIF.
# Time:     3–5 minutes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT="${1:-$REPO_ROOT/data/images/bwa_mem2.sif}"

if [[ -f "$OUTPUT" ]]; then
    echo "SIF already exists: $OUTPUT"
    if [[ "${FORCE:-0}" != "1" ]]; then
        echo "Re-run with FORCE=1 to rebuild."
        exit 0
    fi
fi

mkdir -p "$(dirname "$OUTPUT")"

echo "Building bwa-mem2+samtools SIF → $OUTPUT"
echo "Base: ubuntu:22.04 + bwa-mem2 v2.3 + samtools (apt)"
echo "(~3–5 min)"

apptainer build "$OUTPUT" "$SCRIPT_DIR/bwa_mem2.def"

echo ""
echo "SIF written to: $OUTPUT"
echo "Smoke test: apptainer exec $OUTPUT bwa-mem2 version"
echo "           apptainer exec $OUTPUT samtools --version"
