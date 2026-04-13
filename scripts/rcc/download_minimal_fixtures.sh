#!/usr/bin/env bash
set -euo pipefail

# Restore the tutorial-backed smoke fixtures under data/ for the local Trinity,
# STAR, PASA, BUSCO, RepeatMasker, and protein-evidence paths.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="${DATA_DIR:-$REPO_ROOT/data}"
FORCE="${FORCE:-0}"
TRANSCRIPTOMICS_DIR="$DATA_DIR/transcriptomics/ref-based"
BRAKER3_REFERENCE_DIR="$DATA_DIR/braker3/reference"
BRAKER3_RNASEQ_DIR="$DATA_DIR/braker3/rnaseq"
BRAKER3_PROTEIN_DIR="$DATA_DIR/braker3/protein_data/fastas"
PASA_DIR="$DATA_DIR/pasa"
BUSCO_TEST_DIR="$DATA_DIR/busco/test_data/eukaryota"
REPEATMASKER_DIR="$DATA_DIR/repeatmasker"

mkdir -p "$DATA_DIR"
mkdir -p "$TRANSCRIPTOMICS_DIR" "$BRAKER3_REFERENCE_DIR" "$BRAKER3_RNASEQ_DIR" "$BRAKER3_PROTEIN_DIR"
mkdir -p "$PASA_DIR" "$BUSCO_TEST_DIR" "$REPEATMASKER_DIR"

download_file() {
  local url="$1"
  local dest="$2"

  if [[ -e "$dest" && "$FORCE" != "1" ]]; then
    echo "skip $dest (already exists)"
    return 0
  fi

  local tmp="${dest}.download"
  rm -f "$tmp"

  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --retry-delay 2 -o "$tmp" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$tmp" "$url"
  else
    echo "need curl or wget on PATH" >&2
    exit 1
  fi

  mv "$tmp" "$dest"
  echo "downloaded $dest"
}

download_and_unzip() {
  local url="$1"
  local dest="$2"

  if [[ -e "$dest" && "$FORCE" != "1" ]]; then
    echo "skip $dest (already exists)"
    return 0
  fi

  local tmp="${dest}.download.gz"
  rm -f "$tmp"

  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --retry-delay 2 -o "$tmp" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$tmp" "$url"
  else
    echo "need curl or wget on PATH" >&2
    exit 1
  fi

  gzip -dc "$tmp" > "$dest"
  rm -f "$tmp"
  echo "downloaded $dest"
}

echo "restoring tutorial-backed fixtures into $DATA_DIR"

# Trinity / STAR smoke fixtures from the de novo transcriptomics tutorial.
download_file \
  "https://zenodo.org/record/3541678/files/A1_left.fq.gz" \
  "$TRANSCRIPTOMICS_DIR/reads_1.fq.gz"
download_file \
  "https://zenodo.org/record/3541678/files/A1_right.fq.gz" \
  "$TRANSCRIPTOMICS_DIR/reads_2.fq.gz"

# Legacy transcriptome example used by README quick-start commands.
download_and_unzip \
  "https://zenodo.org/record/3709188/files/transcriptome.fa.gz" \
  "$TRANSCRIPTOMICS_DIR/transcriptome.fa"

# Genome annotation / StringTie / protein-evidence smoke fixtures from the Braker3 tutorial.
download_file \
  "https://zenodo.org/records/14770765/files/genome.fasta" \
  "$BRAKER3_REFERENCE_DIR/genome.fa"
download_file \
  "https://zenodo.org/records/14770765/files/RNASeq.bam" \
  "$BRAKER3_RNASEQ_DIR/RNAseq.bam"
download_file \
  "https://zenodo.org/records/14770765/files/protein_sequences.fasta" \
  "$BRAKER3_PROTEIN_DIR/proteins.fa"

# BUSCO upstream eukaryota image-smoke fixture.
download_file \
  "https://gitlab.com/ezlab/busco/-/raw/master/test_data/eukaryota/genome.fna?ref_type=heads" \
  "$BUSCO_TEST_DIR/genome.fna"
download_file \
  "https://gitlab.com/ezlab/busco/-/raw/master/test_data/eukaryota/info.txt?ref_type=heads" \
  "$BUSCO_TEST_DIR/info.txt"

# RepeatMasker tutorial fixtures from the GTN masking tutorial.
download_file \
  "https://zenodo.org/record/7085837/files/genome_raw.fasta" \
  "$REPEATMASKER_DIR/genome_raw.fasta"
download_file \
  "https://zenodo.org/record/7085837/files/Muco_library_RM2.fasta" \
  "$REPEATMASKER_DIR/Muco_library_RM2.fasta"
download_file \
  "https://zenodo.org/record/7085837/files/Muco_library_EDTA.fasta" \
  "$REPEATMASKER_DIR/Muco_library_EDTA.fasta"

# A second small protein FASTA keeps the multi-input planning tests realistic.
if [[ ! -e "$BRAKER3_PROTEIN_DIR/proteins_extra.fa" || "$FORCE" == "1" ]]; then
  cat > "$BRAKER3_PROTEIN_DIR/proteins_extra.fa" <<'EOF'
>prot_extra_1
MAMAPRTEINSEQ
>prot_extra_2
MSTNPKPQRITTF
EOF
  echo "wrote $BRAKER3_PROTEIN_DIR/proteins_extra.fa"
fi

cat <<'EOF'
Done.

Next steps:
- run the local smoke tests that use these fixtures
- keep PASA pointed at the existing cluster dataset for now
EOF
