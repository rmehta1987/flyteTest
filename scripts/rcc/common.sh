#!/usr/bin/env bash
set -euo pipefail

# Resolve the container runtime used for smoke execution.
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

# Submit the Slurm wrapper when available, otherwise run the local smoke script.
submit_or_run_smoke() {
  local repo_root="$1"
  local sbatch_script="$2"
  local local_script="$3"

  if command -v sbatch >/dev/null 2>&1; then
    sbatch --chdir "$repo_root" "$sbatch_script"
    return 0
  fi

  echo "sbatch not found; running smoke locally: $local_script" >&2
  bash "$local_script"
}

# Fail fast when a required file is missing.
require_file() {
  local path="$1"
  [[ -f "$path" ]] || {
    echo "missing file: $path" >&2
    exit 1
  }
}

# Create the working directory tree used by the smoke.
require_dir() {
  local path="$1"
  mkdir -p "$path"
}

# Build the comma-separated bind list expected by Apptainer/Singularity.
append_bind_mounts() {
  local existing="$1"
  local addition="$2"
  if [[ -n "$existing" ]]; then
    printf '%s,%s\n' "$existing" "$addition"
  else
    printf '%s\n' "$addition"
  fi
}

# Resolve a UniVec-style vector reference from either a file or a directory.
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
      "$candidate/UniVec_Core.txt" \
      "$candidate/UniVec_Core" \
      "$candidate/UniVec.txt" \
      "$candidate/UniVec"; do
      if [[ -f "$path" ]]; then
        printf '%s\n' "$path"
        return 0
      fi
    done

    shopt -s nullglob
    local matches=("$candidate"/UniVec_Core*.txt "$candidate"/UniVec_Core* "$candidate"/UniVec*.txt "$candidate"/UniVec*)
    shopt -u nullglob
    if [[ ${#matches[@]} -eq 1 && -f "${matches[0]}" ]]; then
      printf '%s\n' "${matches[0]}"
      return 0
    fi
  fi

  echo "Unable to resolve a UniVec FASTA file from: $candidate" >&2
  exit 1
}

# Find the legacy BLAST tools directory when seqclean compatibility is needed.
resolve_legacy_blast_tools_dir() {
  local blastall_path
  local formatdb_path

  blastall_path="$(command -v blastall 2>/dev/null || true)"
  formatdb_path="$(command -v formatdb 2>/dev/null || true)"
  if [[ -n "$blastall_path" && -n "$formatdb_path" ]]; then
    printf '%s\n' "$(dirname "$blastall_path")"
    return 0
  fi

  echo "Unable to resolve legacy BLAST tools; expected blastall and formatdb on PATH." >&2
  exit 1
}

# Create the BLAST index files needed by legacy seqclean paths.
ensure_formatdb_index() {
  local fasta_path="$1"
  local formatdb_path

  formatdb_path="$(command -v formatdb 2>/dev/null || true)"
  if [[ -z "$formatdb_path" ]]; then
    echo "Unable to locate formatdb on PATH for $fasta_path" >&2
    exit 1
  fi

  if [[ -s "${fasta_path}.nin" && -s "${fasta_path}.nhr" && -s "${fasta_path}.nsq" ]]; then
    return 0
  fi

  "$formatdb_path" -i "$fasta_path" -p F >/dev/null
}

# Stage host-side wrappers and compatibility libraries for seqclean in a container.
ensure_legacy_blast_bridge() {
  local wrapper_dir="$1"
  local container_blast_dir="$2"
  mkdir -p "$wrapper_dir"

cat >"$wrapper_dir/blastall" <<EOF
#!/usr/bin/env bash
set -euo pipefail
args=()
while ((\$#)); do
  case "\$1" in
    -G)
      shift
      if [[ "\${1:-}" == "3" ]]; then
        args+=(-G 4)
      else
        args+=(-G "\${1:-}")
      fi
      ;;
    -E)
      shift
      if [[ "\${1:-}" == "3" ]]; then
        args+=(-E 4)
      else
        args+=(-E "\${1:-}")
      fi
      ;;
    *)
      args+=("\$1")
      ;;
  esac
  shift || true
done
exec /usr/bin/perl ${container_blast_dir}/legacy_blast blastall --path ${container_blast_dir} "\${args[@]}"
EOF

cat >"$wrapper_dir/formatdb" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/perl ${container_blast_dir}/legacy_blast formatdb --path ${container_blast_dir} "\$@"
EOF

  local host_file copied_file candidate lib
  for host_file in \
    /usr/bin/legacy_blast \
    /usr/bin/blastn \
    /usr/bin/makeblastdb; do
    copied_file="$wrapper_dir/$(basename "$host_file")"
    cp -f "$host_file" "$copied_file"
    chmod 0755 "$copied_file"
  done

  for lib in \
    libutrtprof.so \
    libmbedtls.so.14 \
    libmbedcrypto.so.7 \
    libmbedx509.so.1; do
    for candidate in \
      "/usr/lib/ncbi-blast+/$lib" \
      "/lib/x86_64-linux-gnu/$lib" \
      "/usr/lib/x86_64-linux-gnu/$lib"; do
      if [[ -e "$candidate" ]]; then
        cp -f "$candidate" "$wrapper_dir/$lib"
        break
      fi
    done

    if [[ ! -e "$wrapper_dir/$lib" ]]; then
      echo "Unable to locate $lib for legacy BLAST support." >&2
      exit 1
    fi
  done

  chmod 0755 "$wrapper_dir/blastall" "$wrapper_dir/formatdb"
}

# Stage a simpler legacy-BLAST bridge when the tools are provided by Conda/host paths.
ensure_conda_legacy_blast_bridge() {
  local wrapper_dir="$1"
  local container_prefix="$2"
  mkdir -p "$wrapper_dir"

cat >"$wrapper_dir/blastall" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
args=()
while (($#)); do
  case "$1" in
    -G)
      shift
      if [[ "${1:-}" == "3" ]]; then
        args+=(-G 4)
      else
        args+=(-G "${1:-}")
      fi
      ;;
    -E)
      shift
      if [[ "${1:-}" == "3" ]]; then
        args+=(-E 4)
      else
        args+=(-E "${1:-}")
      fi
      ;;
    *)
      args+=("$1")
      ;;
  esac
  shift || true
done
exec /opt/blast-legacy-real/bin/blastall "${args[@]}"
EOF

cat >"$wrapper_dir/formatdb" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec /opt/blast-legacy-real/bin/formatdb "$@"
EOF

  chmod 0755 "$wrapper_dir/blastall" "$wrapper_dir/formatdb"
}

# Stage the minimal legacy-BLAST bridge inside an image workspace.
ensure_image_legacy_blast_bridge() {
  local wrapper_dir="$1"
  mkdir -p "$wrapper_dir"

cat >"$wrapper_dir/blastall" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
args=()
while (($#)); do
  case "$1" in
    -G)
      shift
      if [[ "${1:-}" == "3" ]]; then
        args+=(-G 4)
      else
        args+=(-G "${1:-}")
      fi
      ;;
    -E)
      shift
      if [[ "${1:-}" == "3" ]]; then
        args+=(-E 4)
      else
        args+=(-E "${1:-}")
      fi
      ;;
    *)
      args+=("$1")
      ;;
  esac
  shift || true
done
exec /usr/bin/perl /usr/bin/legacy_blast blastall --path /usr/bin "${args[@]}"
EOF

cat >"$wrapper_dir/formatdb" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/perl /usr/bin/legacy_blast formatdb --path /usr/bin "$@"
EOF

  chmod 0755 "$wrapper_dir/blastall" "$wrapper_dir/formatdb"
}

# Prefer an override, then a repo-local image, then the shared cluster path.
resolve_smoke_image() {
  local env_var_name="$1"
  local local_candidate="$2"
  local cluster_candidate="$3"
  local env_value="${!env_var_name:-}"

  # Prefer a caller override, then a repo-local smoke image, then the shared RCC path.
  if [[ -n "$env_value" ]]; then
    printf '%s\n' "$env_value"
    return 0
  fi

  if [[ -f "$local_candidate" ]]; then
    printf '%s\n' "$local_candidate"
    return 0
  fi

  printf '%s\n' "$cluster_candidate"
}

# Run a command inside the resolved image with the repo and scratch bind mounts.
runtime_exec() {
  local image_path="$1"
  shift

  local runtime="${RUNTIME:-}"
  if [[ -z "$runtime" ]]; then
    runtime="$(detect_runtime)"
  fi
  local runtime_user="${USER:-$(id -un 2>/dev/null || echo user)}"

  "$runtime" exec --cleanenv \
    --env USER="$runtime_user" \
    --bind "$WORK_DIR:/tmp,$HOST_PROJECT_DIR:$CONTAINER_PROJECT_DIR${BIND_MOUNTS_EXTRA:+,$BIND_MOUNTS_EXTRA}" \
    "$image_path" \
    "$@"
}
