#!/usr/bin/env bash
# Pull the bcftools Apptainer image used by bcftools_stats.
#
# Usage: bash scripts/rcc/pull_bcftools_sif.sh [output_path]
#
# PREFERRED on HPC: add 'bcftools/<version>' to module_loads in your resource_request.
# Use this SIF only when bcftools is not available as a cluster module.
#
# Pulls from BioContainers (quay.io/biocontainers/bcftools).
# Disk:  ~200 MB. Time: ~2 minutes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT="${1:-$REPO_ROOT/data/images/bcftools.sif}"

if [[ -f "$OUTPUT" ]]; then
    echo "SIF already exists: $OUTPUT"
    [[ "${FORCE:-0}" == "1" ]] || exit 0
fi

mkdir -p "$(dirname "$OUTPUT")"

echo "Pulling bcftools SIF → $OUTPUT"
apptainer pull "$OUTPUT" docker://quay.io/biocontainers/bcftools:1.20--h8b25389_0

echo ""
echo "SIF written to: $OUTPUT"
echo "Smoke test: apptainer exec $OUTPUT bcftools --version"
