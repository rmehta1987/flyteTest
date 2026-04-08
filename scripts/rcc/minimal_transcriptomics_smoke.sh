#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SMOKE_ROOT="${SMOKE_ROOT:-$PWD/temp/minimal_transcriptomics_smoke}"

mkdir -p "$SMOKE_ROOT"

bash "$SCRIPT_DIR/check_minimal_fixtures.sh"

TRINITY_SMOKE_DIR="$SMOKE_ROOT/trinity"
STAR_SMOKE_DIR="$SMOKE_ROOT/star"
STRINGTIE_SMOKE_DIR="$SMOKE_ROOT/stringtie"

mkdir -p "$TRINITY_SMOKE_DIR" "$STAR_SMOKE_DIR" "$STRINGTIE_SMOKE_DIR"

TRINITY_CPU="${TRINITY_CPU:-2}"
TRINITY_MAX_MEMORY_GB="${TRINITY_MAX_MEMORY_GB:-4}"
STAR_THREADS="${STAR_THREADS:-2}"
STRINGTIE_THREADS="${STRINGTIE_THREADS:-2}"

WORK_DIR="$TRINITY_SMOKE_DIR" \
TRINITY_CPU="$TRINITY_CPU" \
TRINITY_MAX_MEMORY_GB="$TRINITY_MAX_MEMORY_GB" \
bash "$SCRIPT_DIR/trinity.sh"

WORK_DIR="$STAR_SMOKE_DIR" \
STAR_THREADS="$STAR_THREADS" \
MODE=index \
bash "$SCRIPT_DIR/star.sh"

WORK_DIR="$STAR_SMOKE_DIR" \
STAR_THREADS="$STAR_THREADS" \
MODE=align \
bash "$SCRIPT_DIR/star.sh"

WORK_DIR="$STRINGTIE_SMOKE_DIR" \
STRINGTIE_THREADS="$STRINGTIE_THREADS" \
bash "$SCRIPT_DIR/stringtie.sh"

echo "minimal transcriptomics smoke completed"
echo "results root: $SMOKE_ROOT"
