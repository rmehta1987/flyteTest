#!/usr/bin/env bash
# Pull the MultiQC Apptainer image used by multiqc_summarize.
#
# Usage: bash scripts/rcc/pull_multiqc_sif.sh [output_path]
#
# PREFERRED on HPC: add 'multiqc/<version>' to module_loads in your resource_request.
# Use this SIF only when multiqc is not available as a cluster module.
#
# Pulls from BioContainers (quay.io/biocontainers/multiqc).
# Disk:  ~400 MB. Time: ~3 minutes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT="${1:-$REPO_ROOT/data/images/multiqc.sif}"

if [[ -f "$OUTPUT" ]]; then
    echo "SIF already exists: $OUTPUT"
    [[ "${FORCE:-0}" == "1" ]] || exit 0
fi

mkdir -p "$(dirname "$OUTPUT")"

echo "Pulling MultiQC SIF → $OUTPUT"
apptainer pull "$OUTPUT" docker://quay.io/biocontainers/multiqc:1.21--pyhdfd78af_0

echo ""
echo "SIF written to: $OUTPUT"
echo "Smoke test: apptainer exec $OUTPUT multiqc --version"
