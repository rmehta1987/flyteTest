#!/usr/bin/env bash
# Download a SnpEff database to data/snpeff/data.
#
# Usage:  scripts/rcc/download_snpeff_db.sh <database_name>
# Example: scripts/rcc/download_snpeff_db.sh GRCh38.105
#
# The database will be placed under data/snpeff/data/<database_name>/.
# This path matches the default snpeff_data_dir used by the
# variant_calling_snpeff_chr20 fixture bundle.

set -euo pipefail

DATABASE="${1:?Usage: $0 <database_name>  (e.g. GRCh38.105)}"
OUTDIR="data/snpeff/data"

mkdir -p "${OUTDIR}"

echo "Downloading SnpEff database: ${DATABASE}"
echo "Target directory: ${OUTDIR}"

if command -v snpEff &>/dev/null; then
    snpEff download -dataDir "${OUTDIR}" "${DATABASE}"
elif command -v java &>/dev/null; then
    # Fallback: use bundled snpEff jar if available
    SNPEFF_JAR="$(find data/images/ -name 'snpEff.jar' 2>/dev/null | head -1)"
    if [[ -n "${SNPEFF_JAR}" ]]; then
        java -jar "${SNPEFF_JAR}" download -dataDir "${OUTDIR}" "${DATABASE}"
    else
        echo "ERROR: snpEff not found and no snpEff.jar available." >&2
        echo "Install SnpEff or run from inside the SnpEff Apptainer container." >&2
        exit 1
    fi
else
    echo "ERROR: snpEff not found. Install SnpEff or use the SIF container." >&2
    exit 1
fi

echo "Done. Database stored at: ${OUTDIR}/${DATABASE}/"
