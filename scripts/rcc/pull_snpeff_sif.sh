#!/usr/bin/env bash
# Pull the SnpEff Apptainer image used by snpeff_annotate.
#
# Usage: bash scripts/rcc/pull_snpeff_sif.sh [output_path]
#
# Pulls from BioContainers (quay.io/biocontainers/snpeff).
# Disk:  ~600 MB. Time: ~5 minutes.
#
# After pulling, download the database separately:
#   bash scripts/rcc/download_snpeff_db.sh GRCh38.105
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT="${1:-$REPO_ROOT/data/images/snpeff.sif}"

if [[ -f "$OUTPUT" ]]; then
    echo "SIF already exists: $OUTPUT"
    [[ "${FORCE:-0}" == "1" ]] || exit 0
fi

mkdir -p "$(dirname "$OUTPUT")"

echo "Pulling SnpEff SIF → $OUTPUT"
apptainer pull "$OUTPUT" docker://quay.io/biocontainers/snpeff:5.2--hdfd78af_0

echo ""
echo "SIF written to: $OUTPUT"
echo "Smoke test: apptainer exec $OUTPUT snpEff -version"
echo ""
echo "Download the GRCh38 database (run once, requires internet on compute node or pre-stage):"
echo "  bash scripts/rcc/download_snpeff_db.sh GRCh38.105"
