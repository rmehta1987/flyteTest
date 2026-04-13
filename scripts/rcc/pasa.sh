#!/usr/bin/env bash
set -euo pipefail

# Run PASA seqclean, accession extraction, or align/assemble against the
# staged project tree and shared RCC image paths.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

# Host project root for the cluster-side PASA layout.
HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-/project/rcc/hyadav/genomes}"
# Container bind target for the same project tree.
CONTAINER_PROJECT_DIR="${CONTAINER_PROJECT_DIR:-/workspace}"
# Host project-local results area for PASA temp files and outputs.
WORK_DIR="${WORK_DIR:-$HOST_PROJECT_DIR/results/rcc_pasa}"
MODE="${MODE:-seqclean}" # seqclean | align_assemble | accession_extract

# PASA prefers the repo-local smoke image, then the shared RCC cluster image.
PASA_SIF="$(resolve_smoke_image \
  PASA_SIF \
  "$HOST_PROJECT_DIR/data/images/pasa_2.5.3.legacyblast.sif" \
  "$HOST_PROJECT_DIR/data/images/pasa_2.5.3.sif" \
  "$HOST_PROJECT_DIR/software/PASA.sif")"
SEQCLEAN_THREADS="${SEQCLEAN_THREADS:-16}"
PASA_CPU="${PASA_CPU:-4}"
PASA_MAX_INTRON_LENGTH="${PASA_MAX_INTRON_LENGTH:-100000}"
PASA_ALIGNERS="${PASA_ALIGNERS:-gmap,blat,minimap2}"
# Host PASA workspace that receives the staged transcripts, config, and results.
HOST_PASA_WORK_DIR="${HOST_PASA_WORK_DIR:-$HOST_PROJECT_DIR/transcript_data/pasa}"
# Container PASA workspace, matching the host bind target above.
CONTAINER_PASA_WORK_DIR="${CONTAINER_PASA_WORK_DIR:-$CONTAINER_PROJECT_DIR/transcript_data/pasa}"
# Untrimmed Trinity transcript FASTA consumed by PASA seqclean.
HOST_TRANSCRIPTS_UNTRIMMED_PATH="${HOST_TRANSCRIPTS_UNTRIMMED_PATH:-$HOST_PROJECT_DIR/transcript_data/pasa/trinity_transcripts.fa}"
CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH="${CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH:-$CONTAINER_PROJECT_DIR/transcript_data/pasa/trinity_transcripts.fa}"
# Cleaned transcript FASTA produced by seqclean and consumed by align/assemble.
HOST_TRANSCRIPTS_CLEAN_PATH="${HOST_TRANSCRIPTS_CLEAN_PATH:-$HOST_PROJECT_DIR/transcript_data/pasa/trinity_transcripts.fa.clean}"
CONTAINER_TRANSCRIPTS_CLEAN_PATH="${CONTAINER_TRANSCRIPTS_CLEAN_PATH:-$CONTAINER_PROJECT_DIR/transcript_data/pasa/trinity_transcripts.fa.clean}"
# A vector reference path or directory may be supplied for the legacy seqclean mode.
HOST_VECTOR_SEQUENCE_PATH="$(resolve_univec_reference "${HOST_VECTOR_SEQUENCE_PATH:-$HOST_PROJECT_DIR/scripts/RCC/PASA/vector_reference}")"
CONTAINER_VECTOR_SEQUENCE_PATH="${CONTAINER_VECTOR_SEQUENCE_PATH:-${HOST_VECTOR_SEQUENCE_PATH//$HOST_PROJECT_DIR/$CONTAINER_PROJECT_DIR}}"
# Legacy PASA seqclean expects blastall/formatdb on PATH, so stage a tiny
# wrapper directory in the PASA workspace that carries the host legacy-BLAST
# shims, the helper binaries, and the small mbedTLS runtime libs they need.
HOST_BLAST_WRAPPER_DIR="${HOST_BLAST_WRAPPER_DIR:-$HOST_PASA_WORK_DIR/blast-bin}"
CONTAINER_BLAST_WRAPPER_DIR="${CONTAINER_BLAST_WRAPPER_DIR:-$CONTAINER_PASA_WORK_DIR/blast-bin}"
HOST_BLAST_LIB_DIR="${HOST_BLAST_LIB_DIR:-/usr/lib/ncbi-blast+}"
CONTAINER_BLAST_DIR="${CONTAINER_BLAST_DIR:-/host_blast}"
CONTAINER_BLAST_LIB_DIR="${CONTAINER_BLAST_LIB_DIR:-/host_blast_lib}"
BIND_MOUNTS_EXTRA="${BIND_MOUNTS_EXTRA:-}"
BIND_MOUNTS_EXTRA="$(append_bind_mounts "$BIND_MOUNTS_EXTRA" "$HOST_BLAST_WRAPPER_DIR:$CONTAINER_BLAST_WRAPPER_DIR")"
BIND_MOUNTS_EXTRA="$(append_bind_mounts "$BIND_MOUNTS_EXTRA" "$HOST_BLAST_LIB_DIR:$CONTAINER_BLAST_LIB_DIR")"
# PASA align/assemble template config rewritten to point at a local SQLite DB.
HOST_PASA_CONFIG="${HOST_PASA_CONFIG:-$HOST_PROJECT_DIR/transcript_data/pasa/sqlite.confs/alignAssembly.config}"
CONTAINER_PASA_CONFIG="${CONTAINER_PASA_CONFIG:-$CONTAINER_PROJECT_DIR/transcript_data/pasa/sqlite.confs/alignAssembly.config}"
# Reference genome used by PASA align/assemble.
HOST_GENOME_FASTA="${HOST_GENOME_FASTA:-$HOST_PROJECT_DIR/transcript_data/yeast_genome/Scer_genome.fa}"
CONTAINER_GENOME_FASTA="${CONTAINER_GENOME_FASTA:-$CONTAINER_PROJECT_DIR/transcript_data/yeast_genome/Scer_genome.fa}"
# StringTie GTF passed into PASA align/assemble.
HOST_TRANS_GTF_PATH="${HOST_TRANS_GTF_PATH:-$HOST_PROJECT_DIR/transcript_data/stringtie/stringtie_yeast.gtf}"
CONTAINER_TRANS_GTF_PATH="${CONTAINER_TRANS_GTF_PATH:-$CONTAINER_PROJECT_DIR/transcript_data/stringtie/stringtie_yeast.gtf}"
# TDN accession list produced from the Trinity FASTA.
HOST_TDN_FILE="${HOST_TDN_FILE:-$HOST_PROJECT_DIR/transcript_data/pasa/tdn.accs}"
CONTAINER_TDN_FILE="${CONTAINER_TDN_FILE:-$CONTAINER_PROJECT_DIR/transcript_data/pasa/tdn.accs}"

require_dir "$WORK_DIR"
require_file "$PASA_SIF"

stage_sanitized_fasta() {
  local source="$1"
  local dest="$2"
  # PASA seqclean is happier with simple FASTA headers than with Trinity's full
  # descriptive annotations, so keep only the accession token before the first
  # space when staging the input into the PASA workspace.
  awk 'BEGIN { OFS = "" } /^>/ { sub(/ .*/, "") } { print }' "$source" >"$dest"
}

case "$MODE" in
  seqclean)
    # Legacy mode keeps the old vector-cleaning path available for compatibility.
    require_file "$HOST_TRANSCRIPTS_UNTRIMMED_PATH"
    require_file "$HOST_VECTOR_SEQUENCE_PATH"
    require_dir "$HOST_PASA_WORK_DIR"
    # Stage the vector FASTA into the PASA workspace so seqclean can resolve it
    # by basename inside the container, regardless of whether the source came
    # from the repo-local fixture tree or the shared RCC path.
    HOST_VECTOR_SEQUENCE_BASENAME="$(basename "$HOST_VECTOR_SEQUENCE_PATH")"
    HOST_STAGED_VECTOR_SEQUENCE_PATH="$HOST_PASA_WORK_DIR/$HOST_VECTOR_SEQUENCE_BASENAME"
    cp -f "$HOST_VECTOR_SEQUENCE_PATH" "$HOST_STAGED_VECTOR_SEQUENCE_PATH"
    ensure_formatdb_index "$HOST_STAGED_VECTOR_SEQUENCE_PATH"
    ensure_legacy_blast_bridge "$HOST_BLAST_WRAPPER_DIR" "$CONTAINER_BLAST_DIR"
    CONTAINER_VECTOR_SEQUENCE_PATH="$HOST_VECTOR_SEQUENCE_BASENAME"
    # Stage the Trinity FASTA alongside the vector file and strip the Trinity
    # header suffixes so seqclean sees stable accession-style FASTA headers.
    HOST_STAGE_TRINITY_FASTA="$HOST_PASA_WORK_DIR/$(basename "$HOST_TRANSCRIPTS_UNTRIMMED_PATH")"
    stage_sanitized_fasta "$HOST_TRANSCRIPTS_UNTRIMMED_PATH" "$HOST_STAGE_TRINITY_FASTA"
    CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH="$CONTAINER_PASA_WORK_DIR/$(basename "$HOST_STAGE_TRINITY_FASTA")"

    runtime_exec "$PASA_SIF" bash -lc \
      "export PATH='$CONTAINER_BLAST_WRAPPER_DIR:/usr/bin:/bin'; export LD_LIBRARY_PATH='$CONTAINER_BLAST_WRAPPER_DIR:$CONTAINER_BLAST_LIB_DIR'; cd '$CONTAINER_PASA_WORK_DIR' && /usr/local/src/PASApipeline/bin/seqclean '$CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH' -v '$CONTAINER_VECTOR_SEQUENCE_PATH' -c '$SEQCLEAN_THREADS'"
    ;;

  accession_extract)
    # Extract Trinity accessions when the workflow needs a TDN file.
    require_file "$HOST_TRANSCRIPTS_UNTRIMMED_PATH"
    require_dir "$HOST_PASA_WORK_DIR"
    HOST_STAGE_TRINITY_FASTA="$HOST_PASA_WORK_DIR/$(basename "$HOST_TRANSCRIPTS_UNTRIMMED_PATH")"
    stage_sanitized_fasta "$HOST_TRANSCRIPTS_UNTRIMMED_PATH" "$HOST_STAGE_TRINITY_FASTA"
    CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH="$CONTAINER_PASA_WORK_DIR/$(basename "$HOST_STAGE_TRINITY_FASTA")"

    runtime_exec "$PASA_SIF" bash -lc \
      "cd '$CONTAINER_PASA_WORK_DIR' && /usr/local/src/PASApipeline/misc_utilities/accession_extractor.pl < '$CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH' > '$CONTAINER_TDN_FILE'"
    ;;

  align_assemble)
    # Run the align/assemble stage against the staged transcripts and genome.
    require_file "$HOST_PASA_CONFIG"
    require_file "$HOST_TRANSCRIPTS_UNTRIMMED_PATH"
    require_file "$HOST_TRANSCRIPTS_CLEAN_PATH"
    require_file "$HOST_GENOME_FASTA"
    require_file "$HOST_TRANS_GTF_PATH"
    require_file "$HOST_TDN_FILE"
    require_dir "$HOST_PASA_WORK_DIR"

    runtime_exec "$PASA_SIF" bash -lc \
      "cd '$CONTAINER_PASA_WORK_DIR' && /usr/local/src/PASApipeline/Launch_PASA_pipeline.pl -c '$CONTAINER_PASA_CONFIG' --ALIGNERS '$PASA_ALIGNERS' --MAX_INTRON_LENGTH '$PASA_MAX_INTRON_LENGTH' --CPU '$PASA_CPU' --trans_gtf '$CONTAINER_TRANS_GTF_PATH' --create --run --ALT_SPLICE --stringent_alignment_overlap 30.0 -T --genome '$CONTAINER_GENOME_FASTA' -u '$CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH' --transcripts '$CONTAINER_TRANSCRIPTS_CLEAN_PATH' --TDN '$CONTAINER_TDN_FILE'"
    ;;

  *)
    echo "MODE must be seqclean or align_assemble" >&2
    exit 2
    ;;
esac
