#!/usr/bin/env python3
"""Request cancellation for one durable protein-evidence Slurm run record.

    This module keeps the current repo contract explicit and reviewable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flytetest.server import _cancel_slurm_job_impl


def main(argv: list[str]) -> int:
    """Load the requested run record, request cancellation, and print JSON.

    Args:
        argv: The argument vector forwarded to the helper.

    Returns:
        The returned `int` value used by the caller.
"""
    if len(argv) != 2:
        raise SystemExit("usage: cancel_protein_evidence_slurm.py RUN_RECORD_PATH")

    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    run_record_path = Path(argv[1])
    result = _cancel_slurm_job_impl(run_record_path, run_dir=repo_root / ".runtime/runs")

    # This JSON blob is the durable cancel summary. It mirrors the server-side
    # cancellation result so callers can see whether the request was accepted,
    # which run record was targeted, and any scheduler-side limitations.
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
