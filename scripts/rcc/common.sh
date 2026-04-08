#!/usr/bin/env bash
set -euo pipefail

detect_runtime() {
  for candidate in apptainer singularity; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  echo "No Apptainer/Singularity runtime found on PATH." >&2
  exit 1
}

require_file() {
  local path="$1"
  [[ -f "$path" ]] || {
    echo "missing file: $path" >&2
    exit 1
  }
}

require_dir() {
  local path="$1"
  mkdir -p "$path"
}

resolve_univec_reference() {
  local candidate="$1"
  if [[ -f "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  if [[ -d "$candidate" ]]; then
    # RCC may publish UniVec as a directory containing one of several file names.
    local path
    for path in \
      "$candidate/UniVec.txt" \
      "$candidate/UniVec" \
      "$candidate/UniVec_Core.txt" \
      "$candidate/UniVec_Core"; do
      if [[ -f "$path" ]]; then
        printf '%s\n' "$path"
        return 0
      fi
    done

    shopt -s nullglob
    local matches=("$candidate"/UniVec*.txt "$candidate"/UniVec*)
    shopt -u nullglob
    if [[ ${#matches[@]} -eq 1 && -f "${matches[0]}" ]]; then
      printf '%s\n' "${matches[0]}"
      return 0
    fi
  fi

  echo "Unable to resolve a UniVec FASTA file from: $candidate" >&2
  exit 1
}

runtime_exec() {
  local image_path="$1"
  shift

  local runtime="${RUNTIME:-}"
  if [[ -z "$runtime" ]]; then
    runtime="$(detect_runtime)"
  fi

  "$runtime" exec --cleanenv \
    --bind "$WORK_DIR:/tmp,$HOST_PROJECT_DIR:$CONTAINER_PROJECT_DIR${BIND_MOUNTS_EXTRA:+,$BIND_MOUNTS_EXTRA}" \
    "$image_path" \
    "$@"
}
