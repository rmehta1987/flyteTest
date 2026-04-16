#!/usr/bin/env bash
set -euo pipefail

# Download the GTN RepeatMasker tutorial fixtures into data/ when the repo-local
# copy is missing or stale.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DATA_DIR="${DATA_DIR:-$REPO_ROOT/data}"
REPEATMASKER_FIXTURE_DIR="${REPEATMASKER_FIXTURE_DIR:-$DATA_DIR/repeatmasker}"
REPEATMASKER_ZENODO_RECORD="${REPEATMASKER_ZENODO_RECORD:-7085837}"
REPEATMASKER_ZENODO_BASE="${REPEATMASKER_ZENODO_BASE:-https://zenodo.org/record/$REPEATMASKER_ZENODO_RECORD/files}"
FORCE="${FORCE:-0}"

mkdir -p "$REPEATMASKER_FIXTURE_DIR"

download_file() {
  local url="$1"
  local dest="$2"

  if [[ -s "$dest" && "$FORCE" != "1" ]]; then
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
    echo "Need curl or wget on PATH to download the RepeatMasker test fixture." >&2
    exit 1
  fi

  mv "$tmp" "$dest"
  test -s "$dest"
  echo "downloaded $dest"
}

echo "downloading GTN RepeatMasker tutorial fixtures"
echo "source: $REPEATMASKER_ZENODO_BASE"
echo "dest:   $REPEATMASKER_FIXTURE_DIR"

download_file "$REPEATMASKER_ZENODO_BASE/genome_raw.fasta" "$REPEATMASKER_FIXTURE_DIR/genome_raw.fasta"
download_file "$REPEATMASKER_ZENODO_BASE/Muco_library_RM2.fasta" "$REPEATMASKER_FIXTURE_DIR/Muco_library_RM2.fasta"
download_file "$REPEATMASKER_ZENODO_BASE/Muco_library_EDTA.fasta" "$REPEATMASKER_FIXTURE_DIR/Muco_library_EDTA.fasta"
