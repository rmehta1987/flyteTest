#!/usr/bin/env python3
"""Reconcile one Milestone 18 Slurm run record and print JSON."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flytetest.server import _monitor_slurm_job_impl


def main(argv: list[str]) -> int:
    """Load the requested run record, reconcile scheduler state, and print JSON."""
    if len(argv) != 2:
        raise SystemExit("usage: m18_monitor_slurm_job.py RUN_RECORD_PATH")

    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    run_record_path = Path(argv[1])
    result = _monitor_slurm_job_impl(run_record_path, run_dir=repo_root / ".runtime/runs")

    # This JSON blob mirrors the server-side lifecycle result so callers can
    # see the observed scheduler state, run-record updates, and limitations.
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("supported") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
