"""Shared runtime helpers and Flyte task environments for FLyteTest.

This module centralizes workflow names, result-bundle prefixes, and local or
containerized subprocess execution helpers used across pipeline stages.
"""

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
PASA_UPDATE_WORKFLOW_NAME = "annotation_refinement_pasa"
PASA_UPDATE_RESULTS_PREFIX = "pasa_update_results"
pasa_update_env = flyte.TaskEnvironment(name=PASA_UPDATE_WORKFLOW_NAME)
TRANSDECODER_WORKFLOW_NAME = "transdecoder_from_pasa"
TRANSDECODER_RESULTS_PREFIX = "transdecoder_results"
transdecoder_env = flyte.TaskEnvironment(name=TRANSDECODER_WORKFLOW_NAME)
PROTEIN_EVIDENCE_WORKFLOW_NAME = "protein_evidence_alignment"
PROTEIN_EVIDENCE_RESULTS_PREFIX = "protein_evidence_results"
protein_evidence_env = flyte.TaskEnvironment(name=PROTEIN_EVIDENCE_WORKFLOW_NAME)
ANNOTATION_WORKFLOW_NAME = "ab_initio_annotation_braker3"
ANNOTATION_RESULTS_PREFIX = "braker3_results"
annotation_env = flyte.TaskEnvironment(name=ANNOTATION_WORKFLOW_NAME)
CONSENSUS_PREP_WORKFLOW_NAME = "consensus_annotation_evm_prep"
CONSENSUS_PREP_RESULTS_PREFIX = "evm_prep_results"
consensus_prep_env = flyte.TaskEnvironment(name=CONSENSUS_PREP_WORKFLOW_NAME)
CONSENSUS_WORKFLOW_NAME = CONSENSUS_PREP_WORKFLOW_NAME
CONSENSUS_RESULTS_PREFIX = CONSENSUS_PREP_RESULTS_PREFIX
consensus_env = consensus_prep_env
CONSENSUS_EVM_WORKFLOW_NAME = "consensus_annotation_evm"
CONSENSUS_EVM_RESULTS_PREFIX = "evm_results"
consensus_evm_env = flyte.TaskEnvironment(name=CONSENSUS_EVM_WORKFLOW_NAME)
REPEAT_FILTER_WORKFLOW_NAME = "annotation_repeat_filtering"
REPEAT_FILTER_RESULTS_PREFIX = "repeat_filter_results"
repeat_filter_env = flyte.TaskEnvironment(name=REPEAT_FILTER_WORKFLOW_NAME)
FUNCTIONAL_QC_WORKFLOW_NAME = "annotation_qc_busco"
FUNCTIONAL_QC_RESULTS_PREFIX = "busco_qc_results"
functional_qc_env = flyte.TaskEnvironment(name=FUNCTIONAL_QC_WORKFLOW_NAME)


def run(
    cmd: list[str],
    cwd: Path | None = None,
    stdout_path: Path | None = None,
) -> None:
    """Run a subprocess, optionally writing stdout into a stable output file."""
    if stdout_path is None:
        subprocess.run(cmd, check=True, cwd=cwd)
        return

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w") as handle:
        subprocess.run(cmd, check=True, cwd=cwd, stdout=handle)


def require_path(path: Path, description: str) -> Path:
    """Return an existing path or raise a descriptive `FileNotFoundError`."""
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")
    return path


def container_runtime() -> str:
    """Resolve the first available Apptainer-compatible runtime."""
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
    """Run a tool natively or inside a bound Singularity or Apptainer image."""
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
