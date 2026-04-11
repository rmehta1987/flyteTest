#!/usr/bin/env python3
"""Retry a Milestone 18 Slurm smoke run from a durable run record.

    This module keeps the current repo contract explicit and reviewable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flytetest.server import _retry_slurm_job_impl


def main(argv: list[str]) -> int:
    """Retry the requested run record, persist a child pointer, and print JSON.

    Args:
        argv: The argument vector forwarded to the helper.

    Returns:
        The returned `int` value used by the caller.
"""
    if len(argv) != 2:
        raise SystemExit("usage: m18_retry_slurm_job.py RUN_RECORD_PATH")

    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    run_record_path = Path(argv[1])
    runtime_dir = repo_root / ".runtime/runs"

    result = _retry_slurm_job_impl(run_record_path, run_dir=runtime_dir)
    if not result["supported"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    retry_run_record_path = Path(result["retry_run_record_path"])
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "latest_m18_retry_child_run_record.txt").write_text(f"{retry_run_record_path}\n")

    # Keep the retry summary compact; the linked child run record contains the
    # full retry lineage and scheduler submission details.
    print(
        json.dumps(
            {
                "job_id": result["job_id"],
                "retry_run_record_path": str(retry_run_record_path),
                "source_run_record_path": str(run_record_path),
                "failure_classification": result["retry_result"].get("failure_classification"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
