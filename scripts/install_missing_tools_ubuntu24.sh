#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This helper is intended for Ubuntu/Debian systems with apt-get." >&2
  exit 1
fi

BIN_DIR="${HOME}/bin"
OPT_DIR="${HOME}/opt"
PASA_HOME="${OPT_DIR}/PASApipeline"
SHELL_INIT="${HOME}/.bashrc"
BLAT_URL="https://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/blat/blat"
PASA_REPO="https://github.com/PASApipeline/PASApipeline.git"

append_if_missing() {
  local line="$1"
  local file="$2"
  if ! grep -Fqx "$line" "$file" 2>/dev/null; then
    printf '%s\n' "$line" >>"$file"
  fi
}

echo "==> Installing Ubuntu-packaged tools"
sudo apt-get update
sudo apt-get install -y \
  rna-star \
  trinityrnaseq \
  stringtie \
  gmap \
  minimap2 \
  exonerate \
  transdecoder \
  sqlite3 \
  bioperl \
  libdbi-perl \
  libdbd-sqlite3-perl \
  build-essential \
  git \
  curl \
  wget

mkdir -p "$BIN_DIR" "$OPT_DIR"

if ! command -v blat >/dev/null 2>&1; then
  echo "==> Installing UCSC blat into ${BIN_DIR}"
  curl -fL "$BLAT_URL" -o "${BIN_DIR}/blat"
  chmod +x "${BIN_DIR}/blat"
else
  echo "==> blat already present on PATH"
fi

if [[ ! -d "$PASA_HOME/.git" ]]; then
  echo "==> Cloning PASA into ${PASA_HOME}"
  git clone "$PASA_REPO" "$PASA_HOME"
else
  echo "==> Updating existing PASA checkout in ${PASA_HOME}"
  git -C "$PASA_HOME" pull --ff-only
fi

echo "==> Building PASA"
make -C "$PASA_HOME"

append_if_missing 'export PATH="$HOME/bin:$PATH"' "$SHELL_INIT"
append_if_missing 'export PASAHOME="$HOME/opt/PASApipeline"' "$SHELL_INIT"
append_if_missing 'export PATH="$PASAHOME:$PASAHOME/bin:$PASAHOME/misc_utilities:$PASAHOME/seqclean:$PATH"' "$SHELL_INIT"

cat <<EOF

Install step completed.

Restart your shell or run:
  source "$SHELL_INIT"

Then verify:
  which STAR
  which Trinity
  which stringtie
  which gmap
  which minimap2
  which exonerate
  which blat
  which TransDecoder.LongOrfs
  which accession_extractor.pl
  which Launch_PASA_pipeline.pl
  which seqclean

If 'seqclean' is still missing after sourcing your shell init, follow the
bundled PASA instructions under:
  ${PASA_HOME}/seqclean

Later, for PASA workflow runs, you will also need:
  - a UniVec_Core FASTA
  - a PASA alignAssembly template config file

Later, for BRAKER3 workflow runs, this helper does not install BRAKER3 itself.
Provide either:
  - an existing local BRAKER3 installation with `braker.pl` on PATH
  - or a container image passed via `braker3_sif`

EOF
