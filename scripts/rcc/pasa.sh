#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/rcc/common.sh
source "$SCRIPT_DIR/common.sh"

HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-/project/rcc/hyadav/genomes}"
CONTAINER_PROJECT_DIR="${CONTAINER_PROJECT_DIR:-/workspace}"
WORK_DIR="${WORK_DIR:-$PWD/temp}"
MODE="${MODE:-seqclean}" # seqclean | align_assemble | accession_extract

PASA_SIF="${PASA_SIF:-$HOST_PROJECT_DIR/software/PASA.sif}"
SEQCLEAN_THREADS="${SEQCLEAN_THREADS:-16}"
PASA_CPU="${PASA_CPU:-4}"
PASA_MAX_INTRON_LENGTH="${PASA_MAX_INTRON_LENGTH:-100000}"
PASA_ALIGNERS="${PASA_ALIGNERS:-gmap,blat,minimap2}"
HOST_PASA_WORK_DIR="${HOST_PASA_WORK_DIR:-$HOST_PROJECT_DIR/transcript_data/pasa}"
CONTAINER_PASA_WORK_DIR="${CONTAINER_PASA_WORK_DIR:-$CONTAINER_PROJECT_DIR/transcript_data/pasa}"
HOST_TRANSCRIPTS_UNTRIMMED_PATH="${HOST_TRANSCRIPTS_UNTRIMMED_PATH:-$HOST_PROJECT_DIR/transcript_data/pasa/trinity_transcripts.fa}"
CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH="${CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH:-$CONTAINER_PROJECT_DIR/transcript_data/pasa/trinity_transcripts.fa}"
HOST_TRANSCRIPTS_CLEAN_PATH="${HOST_TRANSCRIPTS_CLEAN_PATH:-$HOST_PROJECT_DIR/transcript_data/pasa/trinity_transcripts.fa.clean}"
CONTAINER_TRANSCRIPTS_CLEAN_PATH="${CONTAINER_TRANSCRIPTS_CLEAN_PATH:-$CONTAINER_PROJECT_DIR/transcript_data/pasa/trinity_transcripts.fa.clean}"
HOST_VECTOR_SEQUENCE_PATH="${HOST_VECTOR_SEQUENCE_PATH:-$HOST_PROJECT_DIR/scripts/RCC/PASA/UniVec}"
CONTAINER_VECTOR_SEQUENCE_PATH="${CONTAINER_VECTOR_SEQUENCE_PATH:-$CONTAINER_PROJECT_DIR/scripts/RCC/PASA/UniVec}"
HOST_PASA_CONFIG="${HOST_PASA_CONFIG:-$HOST_PROJECT_DIR/transcript_data/pasa/sqlite.confs/alignAssembly.config}"
CONTAINER_PASA_CONFIG="${CONTAINER_PASA_CONFIG:-$CONTAINER_PROJECT_DIR/transcript_data/pasa/sqlite.confs/alignAssembly.config}"
HOST_GENOME_FASTA="${HOST_GENOME_FASTA:-$HOST_PROJECT_DIR/transcript_data/yeast_genome/Scer_genome.fa}"
CONTAINER_GENOME_FASTA="${CONTAINER_GENOME_FASTA:-$CONTAINER_PROJECT_DIR/transcript_data/yeast_genome/Scer_genome.fa}"
HOST_TRANS_GTF_PATH="${HOST_TRANS_GTF_PATH:-$HOST_PROJECT_DIR/transcript_data/stringtie/stringtie_yeast.gtf}"
CONTAINER_TRANS_GTF_PATH="${CONTAINER_TRANS_GTF_PATH:-$CONTAINER_PROJECT_DIR/transcript_data/stringtie/stringtie_yeast.gtf}"
HOST_TDN_FILE="${HOST_TDN_FILE:-$HOST_PROJECT_DIR/transcript_data/pasa/tdn.accs}"
CONTAINER_TDN_FILE="${CONTAINER_TDN_FILE:-$CONTAINER_PROJECT_DIR/transcript_data/pasa/tdn.accs}"

require_dir "$WORK_DIR"
require_file "$PASA_SIF"

case "$MODE" in
  seqclean)
    require_file "$HOST_TRANSCRIPTS_UNTRIMMED_PATH"
    require_file "$HOST_VECTOR_SEQUENCE_PATH"
    require_dir "$HOST_PASA_WORK_DIR"

    runtime_exec "$PASA_SIF" bash -lc \
      "cd '$CONTAINER_PASA_WORK_DIR' && /usr/local/src/PASApipeline/bin/seqclean '$CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH' -v '$CONTAINER_VECTOR_SEQUENCE_PATH' -c '$SEQCLEAN_THREADS'"
    ;;

  accession_extract)
    require_file "$HOST_TRANSCRIPTS_UNTRIMMED_PATH"
    require_dir "$HOST_PASA_WORK_DIR"

    runtime_exec "$PASA_SIF" bash -lc \
      "cd '$CONTAINER_PASA_WORK_DIR' && /usr/local/src/PASApipeline/misc_utilities/accession_extractor.pl < '$CONTAINER_TRANSCRIPTS_UNTRIMMED_PATH' > '$CONTAINER_TDN_FILE'"
    ;;

  align_assemble)
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
