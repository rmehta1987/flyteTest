#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLYTE_BIN="${ROOT_DIR}/flytetest/bin/flyte"

detect_runtime() {
  for candidate in apptainer singularity; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! RUNTIME="$(detect_runtime)"; then
  echo "No Apptainer/Singularity runtime found on PATH." >&2
  exit 1
fi

if [[ -z "${FASTQC_SIF:-}${SALMON_SIF:-}${STAR_SIF:-}${TRINITY_SIF:-}${STRINGTIE_SIF:-}${PASA_SIF:-}${TRANSDECODER_SIF:-}${EXONERATE_SIF:-}${BRAKER3_SIF:-}${BUSCO_SIF:-}" ]]; then
  cat <<'EOF'
Set one or more image paths before running this script.

Examples:
  FASTQC_SIF=/path/fastqc.sif SALMON_SIF=/path/salmon.sif \
    bash scripts/test_singularity_images.sh

  STAR_SIF=/path/star.sif TRINITY_SIF=/path/trinity.sif STRINGTIE_SIF=/path/stringtie.sif \
    bash scripts/test_singularity_images.sh

  PASA_SIF=/path/pasa.sif TRANSDECODER_SIF=/path/transdecoder.sif \
    bash scripts/test_singularity_images.sh

  EXONERATE_SIF=/path/exonerate.sif \
    bash scripts/test_singularity_images.sh

  BRAKER3_SIF=/path/to/data/images/braker3.sif \
    bash scripts/test_singularity_images.sh

  BUSCO_SIF=/path/to/data/images/busco_v6.0.0_cv1.sif \
    bash scripts/test_singularity_images.sh
EOF
  exit 1
fi

run_check() {
  local label="$1"
  shift
  echo "==> ${label}"
  "$@"
}

run_shell_in_image() {
  local image="$1"
  local snippet="$2"
  "$RUNTIME" exec --cleanenv "$image" sh -lc "$snippet"
}

if [[ -n "${FASTQC_SIF:-}" ]]; then
  run_check "FastQC image" "$RUNTIME" exec --cleanenv "$FASTQC_SIF" fastqc --version
fi

if [[ -n "${SALMON_SIF:-}" ]]; then
  run_check "Salmon image" "$RUNTIME" exec --cleanenv "$SALMON_SIF" salmon --version
fi

if [[ -n "${STAR_SIF:-}" ]]; then
  run_check "STAR image" run_shell_in_image "$STAR_SIF" 'command -v STAR && STAR --version'
fi

if [[ -n "${TRINITY_SIF:-}" ]]; then
  run_check "Trinity image" run_shell_in_image "$TRINITY_SIF" 'command -v Trinity'
fi

if [[ -n "${STRINGTIE_SIF:-}" ]]; then
  run_check "StringTie image" "$RUNTIME" exec --cleanenv "$STRINGTIE_SIF" stringtie --version
fi

if [[ -n "${PASA_SIF:-}" ]]; then
  run_check "PASA image" run_shell_in_image "$PASA_SIF" \
    'command -v seqclean && command -v Launch_PASA_pipeline.pl && command -v accession_extractor.pl && command -v gmap && command -v minimap2 && command -v blat'
fi

if [[ -n "${TRANSDECODER_SIF:-}" ]]; then
  run_check "TransDecoder image" run_shell_in_image "$TRANSDECODER_SIF" \
    'command -v TransDecoder.LongOrfs && command -v TransDecoder.Predict && command -v cdna_alignment_orf_to_genome_orf.pl'
fi

if [[ -n "${EXONERATE_SIF:-}" ]]; then
  run_check "Exonerate image" run_shell_in_image "$EXONERATE_SIF" \
    'command -v exonerate'
fi

if [[ -n "${BRAKER3_SIF:-}" ]]; then
  run_check "BRAKER3 image" run_shell_in_image "$BRAKER3_SIF" \
    'command -v braker.pl'
fi

if [[ -n "${BUSCO_SIF:-}" ]]; then
  run_check "BUSCO image" run_shell_in_image "$BUSCO_SIF" \
    'command -v busco'
fi

if [[ -n "${FASTQC_SIF:-}" && -n "${SALMON_SIF:-}" ]]; then
  echo "==> Running rnaseq_qc_quant smoke test against bundled example data"
  "$FLYTE_BIN" run --local "${ROOT_DIR}/flyte_rnaseq_workflow.py" rnaseq_qc_quant \
    --ref "${ROOT_DIR}/data/transcriptomics/ref-based/transcriptome.fa" \
    --left "${ROOT_DIR}/data/transcriptomics/ref-based/reads_1.fq.gz" \
    --right "${ROOT_DIR}/data/transcriptomics/ref-based/reads_2.fq.gz" \
    --fastqc-sif "$FASTQC_SIF" \
    --salmon-sif "$SALMON_SIF"
else
  cat <<'EOF'
Skipping rnaseq_qc_quant smoke test because both FASTQC_SIF and SALMON_SIF were not provided.
The repo does not yet include bundled reference inputs for a full transcript-evidence or PASA end-to-end smoke run.
For those stages, this helper performs image-level command checks only.
EOF
fi
