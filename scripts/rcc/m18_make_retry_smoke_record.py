#!/usr/bin/env python3
"""Create a synthetic retryable copy of a Slurm run record for Milestone 18.

    This module keeps the current repo contract explicit and reviewable.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    """Copy a run record, mark the copy retryable, and print JSON.

    Args:
        argv: The argument vector forwarded to the helper.

    Returns:
        The returned `int` value used by the caller.
"""
    if len(argv) != 2:
        raise SystemExit("usage: m18_make_retry_smoke_record.py RUN_RECORD_PATH")

    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    source_record = Path(argv[1])
    suffix = os.environ.get("FLYTETEST_M18_RETRY_SMOKE_SUFFIX", "m18-retry-smoke")
    state = os.environ.get("FLYTETEST_M18_RETRY_SMOKE_STATE", "NODE_FAIL")
    exit_code = os.environ.get("FLYTETEST_M18_RETRY_SMOKE_EXIT_CODE", "0:0")
    reason = os.environ.get(
        "FLYTETEST_M18_RETRY_SMOKE_REASON",
        "Synthetic Milestone 18 retry smoke: node failure classification.",
    )

    sandbox_dir = source_record.parent.parent / f"{source_record.parent.name}-{suffix}"
    shutil.copytree(source_record.parent, sandbox_dir, dirs_exist_ok=True)

    sandbox_record = sandbox_dir / "slurm_run_record.json"
    payload = json.loads(sandbox_record.read_text())
    payload.update(
        {
            "run_id": f"{payload.get('run_id', source_record.parent.name)}-{suffix}",
            "run_record_path": str(sandbox_record),
            "scheduler_state": state,
            "final_scheduler_state": state,
            "scheduler_state_source": "synthetic-hpc-retry-smoke",
            "scheduler_exit_code": exit_code,
            "scheduler_reason": reason,
            "retry_child_run_ids": [],
            "retry_child_run_record_paths": [],
            "failure_classification": None,
        }
    )
    sandbox_record.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    runtime_dir = repo_root / ".runtime/runs"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "latest_m18_retry_smoke_run_record.txt").write_text(f"{sandbox_record}\n")

    # This helper intentionally mutates only a copied run record so the original
    # submission remains available for normal lifecycle inspection.
    print(
        json.dumps(
            {
                "source_run_record_path": str(source_record),
                "sandbox_run_record_path": str(sandbox_record),
                "synthetic_exit_code": exit_code,
                "synthetic_scheduler_state": state,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
