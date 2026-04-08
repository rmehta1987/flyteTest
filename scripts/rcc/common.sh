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
