#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEFAULT_POINTER="$REPO_ROOT/.runtime/runs/latest_protein_evidence_slurm_run_record.txt"
RUN_RECORD_PATH="${1:-}"

if [[ -z "$RUN_RECORD_PATH" ]]; then
  if [[ -f "$DEFAULT_POINTER" ]]; then
    RUN_RECORD_PATH="$(tr -d '\n' <"$DEFAULT_POINTER")"
  fi
fi

if [[ -z "$RUN_RECORD_PATH" ]]; then
  echo "usage: $0 [run_record_path]" >&2
  echo "or set $DEFAULT_POINTER by running the protein evidence Slurm submit script first." >&2
  exit 1
fi

export FLYTETEST_REPO_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if command -v module >/dev/null 2>&1; then
  module load python/3.11.9
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"

"$PYTHON_BIN" - "$RUN_RECORD_PATH" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flytetest.server import _cancel_slurm_job_impl

repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
run_record_path = Path(sys.argv[1])
result = _cancel_slurm_job_impl(run_record_path, run_dir=repo_root / ".runtime/runs")
print(json.dumps(result, indent=2, sort_keys=True))
PY
