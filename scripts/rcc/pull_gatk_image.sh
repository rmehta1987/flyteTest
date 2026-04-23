#!/usr/bin/env bash
# Pull the GATK4 SIF image used by all variant_calling tasks.
# Usage: bash scripts/rcc/pull_gatk_image.sh [output_path]
set -euo pipefail
OUTPUT="${1:-data/images/gatk4.sif}"
mkdir -p "$(dirname "$OUTPUT")"
apptainer pull "$OUTPUT" docker://broadinstitute/gatk:latest
echo "GATK4 image written to: $OUTPUT"
