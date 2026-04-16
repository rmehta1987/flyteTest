#!/usr/bin/env bash
set -euo pipefail

# Verify the tutorial-backed smoke fixtures are present before running the
# local Trinity, STAR, PASA, BUSCO, repeat-masking, or protein-evidence flows.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

required_files=(
  "data/transcriptomics/ref-based/reads_1.fq.gz"
  "data/transcriptomics/ref-based/reads_2.fq.gz"
  "data/transcriptomics/ref-based/transcriptome.fa"
  "data/braker3/reference/genome.fa"
  "data/braker3/rnaseq/RNAseq.bam"
  "data/braker3/protein_data/fastas/proteins.fa"
  "data/braker3/protein_data/fastas/proteins_extra.fa"
)

missing=0
for rel_path in "${required_files[@]}"; do
  abs_path="$REPO_ROOT/$rel_path"
  if [[ ! -e "$abs_path" ]]; then
    echo "missing fixture: $rel_path" >&2
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "checked under: $REPO_ROOT" >&2
  exit 1
fi

echo "all minimal fixtures are present under $REPO_ROOT/data"
