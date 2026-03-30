from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import flyte


WORKFLOW_NAME = "rnaseq_qc_quant"
RESULTS_ROOT = "results"
RESULTS_PREFIX = "rnaseq_results"
env = flyte.TaskEnvironment(name=WORKFLOW_NAME)
TRANSCRIPT_EVIDENCE_WORKFLOW_NAME = "transcript_evidence_generation"
TRANSCRIPT_EVIDENCE_RESULTS_PREFIX = "transcript_evidence_results"
transcript_evidence_env = flyte.TaskEnvironment(name=TRANSCRIPT_EVIDENCE_WORKFLOW_NAME)
PASA_WORKFLOW_NAME = "pasa_transcript_alignment"
PASA_RESULTS_PREFIX = "pasa_results"
pasa_env = flyte.TaskEnvironment(name=PASA_WORKFLOW_NAME)
TRANSDECODER_WORKFLOW_NAME = "transdecoder_from_pasa"
TRANSDECODER_RESULTS_PREFIX = "transdecoder_results"
transdecoder_env = flyte.TaskEnvironment(name=TRANSDECODER_WORKFLOW_NAME)


def run(
    cmd: list[str],
    cwd: Path | None = None,
    stdout_path: Path | None = None,
) -> None:
    if stdout_path is None:
        subprocess.run(cmd, check=True, cwd=cwd)
        return

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w") as handle:
        subprocess.run(cmd, check=True, cwd=cwd, stdout=handle)


def require_path(path: Path, description: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")
    return path


def container_runtime() -> str:
    for candidate in ("apptainer", "singularity"):
        if shutil.which(candidate):
            return candidate
    raise RuntimeError(
        "No container runtime found. Install Apptainer/Singularity or leave the *.sif inputs empty."
    )


def run_tool(
    cmd: list[str],
    sif: str,
    bind_paths: list[Path],
    cwd: Path | None = None,
    stdout_path: Path | None = None,
) -> None:
    if not sif:
        run(cmd, cwd=cwd, stdout_path=stdout_path)
        return

    mounts: set[str] = set()
    for path in bind_paths:
        resolved = str(path.resolve())
        mounts.add(f"{resolved}:{resolved}")

    runtime = container_runtime()
    sing_cmd = [runtime, "exec", "--cleanenv"]
    for mount in sorted(mounts):
        sing_cmd.extend(["-B", mount])
    sing_cmd.extend([sif, *cmd])
    run(sing_cmd, cwd=cwd, stdout_path=stdout_path)
