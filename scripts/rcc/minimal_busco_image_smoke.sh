#!/usr/bin/env bash
set -euo pipefail

# Run the BUSCO image smoke against the repo-local fixture tree and compare the
# short summary output in the smoke results directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-$REPO_ROOT}"
CONTAINER_PROJECT_DIR="${CONTAINER_PROJECT_DIR:-/workspace}"
BUSCO_SMOKE_ROOT="${BUSCO_SMOKE_ROOT:-$REPO_ROOT/results/minimal_busco_image_smoke}"
HOST_BUSCO_DATA_DIR="${HOST_BUSCO_DATA_DIR:-$REPO_ROOT/data/busco/test_data/eukaryota}"
HOST_BUSCO_WORK_DIR="${HOST_BUSCO_WORK_DIR:-$BUSCO_SMOKE_ROOT/busco}"
CONTAINER_BUSCO_WORK_DIR="${CONTAINER_BUSCO_WORK_DIR:-/workspace/results/minimal_busco_image_smoke/busco}"
BUSCO_SIF="${BUSCO_SIF:-$(resolve_smoke_image BUSCO_SIF "$REPO_ROOT/data/images/busco_v6.0.0_cv1.sif" "/project/rcc/hyadav/genomes/software/busco_v6.0.0_cv1.sif")}"
HOST_BUSCO_GENOME_FASTA="${HOST_BUSCO_GENOME_FASTA:-$HOST_BUSCO_DATA_DIR/genome.fna}"
CONTAINER_BUSCO_GENOME_FASTA="${CONTAINER_BUSCO_GENOME_FASTA:-/workspace/data/busco/test_data/eukaryota/genome.fna}"
BUSCO_OUTPUT_NAME="${BUSCO_OUTPUT_NAME:-test_eukaryota}"
BUSCO_MODE="${BUSCO_MODE:-geno}"
BUSCO_CPU="${BUSCO_CPU:-2}"
BUSCO_EXTRA_ARGS="${BUSCO_EXTRA_ARGS:-}"
# runtime_exec binds this host path to container /tmp, so the container sees a
# normal scratch path while the cluster host writes under repo-local results/.
WORK_DIR="${WORK_DIR:-$BUSCO_SMOKE_ROOT/runtime}"

if [[ ! -s "$HOST_BUSCO_GENOME_FASTA" ]]; then
  BUSCO_FIXTURE_FASTA="$HOST_BUSCO_GENOME_FASTA" bash "$SCRIPT_DIR/download_minimal_busco_fixture.sh"
fi

require_file "$HOST_BUSCO_GENOME_FASTA"
require_file "$BUSCO_SIF"

rm -rf "$HOST_BUSCO_WORK_DIR"
mkdir -p "$HOST_BUSCO_WORK_DIR" "$WORK_DIR"

echo "BUSCO image smoke root: $BUSCO_SMOKE_ROOT"
echo "BUSCO work dir: $HOST_BUSCO_WORK_DIR"
echo "BUSCO genome FASTA: $HOST_BUSCO_GENOME_FASTA"
echo "BUSCO image: $BUSCO_SIF"
echo "BUSCO output name: $BUSCO_OUTPUT_NAME"
echo "BUSCO mode: $BUSCO_MODE"
echo "BUSCO CPU: $BUSCO_CPU"
if [[ -n "$BUSCO_EXTRA_ARGS" ]]; then
  echo "BUSCO extra args: $BUSCO_EXTRA_ARGS"
fi

# This mirrors the upstream BUSCO test-data instruction:
#   busco -i genome.fna -c 8 -m geno -f --out test_eukaryota
runtime_exec "$BUSCO_SIF" bash -lc \
  "cd '$CONTAINER_BUSCO_WORK_DIR' && busco -i '$CONTAINER_BUSCO_GENOME_FASTA' -c '$BUSCO_CPU' -m '$BUSCO_MODE' -f --out '$BUSCO_OUTPUT_NAME' $BUSCO_EXTRA_ARGS"

bash "$SCRIPT_DIR/check_minimal_busco_image_smoke.sh"
echo "minimal BUSCO image smoke completed"
