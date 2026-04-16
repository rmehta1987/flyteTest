#!/usr/bin/env bash
set -euo pipefail

# Download the upstream BUSCO eukaryota fixture into data/ when the repo-local
# copy is missing or stale.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DATA_DIR="${DATA_DIR:-$REPO_ROOT/data}"
BUSCO_FIXTURE_DIR="${BUSCO_FIXTURE_DIR:-$DATA_DIR/busco/test_data/eukaryota}"
BUSCO_FIXTURE_URL="${BUSCO_FIXTURE_URL:-https://gitlab.com/ezlab/busco/-/raw/master/test_data/eukaryota/genome.fna?ref_type=heads}"
BUSCO_FIXTURE_INFO_URL="${BUSCO_FIXTURE_INFO_URL:-https://gitlab.com/ezlab/busco/-/raw/master/test_data/eukaryota/info.txt?ref_type=heads}"
BUSCO_FIXTURE_FASTA="${BUSCO_FIXTURE_FASTA:-$BUSCO_FIXTURE_DIR/genome.fna}"
BUSCO_FIXTURE_INFO="${BUSCO_FIXTURE_INFO:-$BUSCO_FIXTURE_DIR/info.txt}"
FORCE="${FORCE:-0}"

mkdir -p "$BUSCO_FIXTURE_DIR"
mkdir -p "$(dirname "$BUSCO_FIXTURE_FASTA")" "$(dirname "$BUSCO_FIXTURE_INFO")"

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
    echo "Need curl or wget on PATH to download the BUSCO test fixture." >&2
    exit 1
  fi

  mv "$tmp" "$dest"
  test -s "$dest"
  echo "downloaded $dest"
}

echo "downloading BUSCO eukaryota test genome"
echo "source: $BUSCO_FIXTURE_URL"
echo "info:   $BUSCO_FIXTURE_INFO_URL"
echo "dest:   $BUSCO_FIXTURE_DIR"

download_file "$BUSCO_FIXTURE_URL" "$BUSCO_FIXTURE_FASTA"
download_file "$BUSCO_FIXTURE_INFO_URL" "$BUSCO_FIXTURE_INFO"
