#!/usr/bin/env python3
"""Submit a frozen Milestone 18 Slurm recipe and print JSON.

    This module keeps the current repo contract explicit and reviewable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flytetest.server import _run_slurm_recipe_impl


def main(argv: list[str]) -> int:
    """Submit the requested recipe, persist pointer files, and print JSON.

    Args:
        argv: The argument vector forwarded to the helper.

    Returns:
        The returned `int` value used by the caller.
"""
    if len(argv) != 2:
        raise SystemExit("usage: m18_submit_slurm_recipe.py ARTIFACT_PATH")

    repo_root = Path(os.environ["FLYTETEST_REPO_ROOT"])
    artifact_path = Path(argv[1])
    runtime_dir = repo_root / ".runtime/runs"

    submitted = _run_slurm_recipe_impl(
        artifact_path,
        run_dir=runtime_dir,
    )
    if not submitted["supported"]:
        print(json.dumps(submitted, indent=2, sort_keys=True))
        return 1

    run_record_path = Path(submitted["run_record_path"])
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "latest_m18_slurm_run_record.txt").write_text(f"{run_record_path}\n")
    (runtime_dir / "latest_m18_slurm_artifact.txt").write_text(f"{artifact_path}\n")

    # This mirrors the protein-evidence submit helper: keep the user-facing
    # summary small and point to the durable run record for full details.
    print(
        json.dumps(
            {
                "artifact_path": str(artifact_path),
                "job_id": submitted["job_id"],
                "run_record_path": str(run_record_path),
                "stdout": submitted["execution_result"].get("stdout", ""),
                "stderr": submitted["execution_result"].get("stderr", ""),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
