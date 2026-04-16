"""Shared runtime helpers and Flyte task environments for FLyteTest.

This module centralizes task-environment names, result-bundle prefixes, and
local or containerized subprocess execution helpers used across pipeline
stages.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import flyte


DEFAULT_TASK_ENV_VARS = {"PYTHONUNBUFFERED": "1"}
DEFAULT_TASK_RESOURCES = flyte.Resources(cpu="1", memory="1Gi")


@dataclass(frozen=True, slots=True)
class TaskEnvironmentConfig:
    """Declarative construction data for one task-family environment.

    Attributes:
        name: Flyte task-environment name registered for the stage family.
        kwargs: Additional constructor arguments merged with shared defaults.
    """

    name: str
    kwargs: Mapping[str, object] = field(default_factory=dict)


def make_task_environment(config: TaskEnvironmentConfig | str, **kwargs: object) -> flyte.TaskEnvironment:
    """Create one Flyte `TaskEnvironment` with shared task defaults.

    Args:
        config: Environment name or declarative config for the stage family.
        kwargs: Overrides merged after the shared defaults and config values.

    Returns:
        A `flyte.TaskEnvironment` with the repo's common task defaults applied.
    """
    if isinstance(config, str):
        config = TaskEnvironmentConfig(name=config)

    merged_kwargs: dict[str, object] = {
        "env_vars": dict(DEFAULT_TASK_ENV_VARS),
        "resources": DEFAULT_TASK_RESOURCES,
    }
    merged_kwargs.update(dict(config.kwargs))
    merged_kwargs.update(kwargs)
    return flyte.TaskEnvironment(name=config.name, **merged_kwargs)


TASK_ENV_NAME = "rnaseq_qc_quant"
# Keep the legacy name as a compatibility alias for older imports and manifests.
WORKFLOW_NAME = TASK_ENV_NAME
RESULTS_ROOT = "results"
PROJECT_TMP_ENV_VAR = "FLYTETEST_TMPDIR"
RESULTS_PREFIX = "rnaseq_results"
TRANSCRIPT_EVIDENCE_WORKFLOW_NAME = "transcript_evidence_generation"
TRANSCRIPT_EVIDENCE_RESULTS_PREFIX = "transcript_evidence_results"
PASA_WORKFLOW_NAME = "pasa_transcript_alignment"
PASA_RESULTS_PREFIX = "pasa_results"
PASA_UPDATE_WORKFLOW_NAME = "annotation_refinement_pasa"
PASA_UPDATE_RESULTS_PREFIX = "pasa_update_results"
TRANSDECODER_WORKFLOW_NAME = "transdecoder_from_pasa"
TRANSDECODER_RESULTS_PREFIX = "transdecoder_results"
PROTEIN_EVIDENCE_WORKFLOW_NAME = "protein_evidence_alignment"
PROTEIN_EVIDENCE_RESULTS_PREFIX = "protein_evidence_results"
ANNOTATION_WORKFLOW_NAME = "ab_initio_annotation_braker3"
ANNOTATION_RESULTS_PREFIX = "braker3_results"
CONSENSUS_PREP_WORKFLOW_NAME = "consensus_annotation_evm_prep"
CONSENSUS_PREP_RESULTS_PREFIX = "evm_prep_results"
CONSENSUS_WORKFLOW_NAME = CONSENSUS_PREP_WORKFLOW_NAME
CONSENSUS_RESULTS_PREFIX = CONSENSUS_PREP_RESULTS_PREFIX
CONSENSUS_EVM_WORKFLOW_NAME = "consensus_annotation_evm"
CONSENSUS_EVM_RESULTS_PREFIX = "evm_results"
REPEAT_FILTER_WORKFLOW_NAME = "annotation_repeat_filtering"
REPEAT_FILTER_RESULTS_PREFIX = "repeat_filter_results"
FUNCTIONAL_QC_WORKFLOW_NAME = "annotation_qc_busco"
FUNCTIONAL_QC_RESULTS_PREFIX = "busco_qc_results"
EGGNOG_WORKFLOW_NAME = "annotation_functional_eggnog"
EGGNOG_RESULTS_PREFIX = "eggnog_results"
AGAT_WORKFLOW_NAME = "annotation_postprocess_agat"
AGAT_RESULTS_PREFIX = "agat_results"
AGAT_CONVERSION_WORKFLOW_NAME = "annotation_postprocess_agat_conversion"
AGAT_CONVERSION_RESULTS_PREFIX = "agat_conversion_results"
AGAT_CLEANUP_WORKFLOW_NAME = "annotation_postprocess_agat_cleanup"
AGAT_CLEANUP_RESULTS_PREFIX = "agat_cleanup_results"
TABLE2ASN_WORKFLOW_NAME = "annotation_postprocess_table2asn"
TABLE2ASN_RESULTS_PREFIX = "table2asn_results"

TASK_ENVIRONMENT_CONFIGS: tuple[TaskEnvironmentConfig, ...] = (
    TaskEnvironmentConfig(name=TASK_ENV_NAME),
    TaskEnvironmentConfig(name=TRANSCRIPT_EVIDENCE_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=PASA_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=PASA_UPDATE_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=TRANSDECODER_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=PROTEIN_EVIDENCE_WORKFLOW_NAME),
    TaskEnvironmentConfig(
        name=ANNOTATION_WORKFLOW_NAME,
        kwargs={
            "resources": flyte.Resources(cpu="16", memory="64Gi"),
            "description": "BRAKER3 ab initio annotation stage.",
        },
    ),
    TaskEnvironmentConfig(name=CONSENSUS_PREP_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=CONSENSUS_EVM_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=REPEAT_FILTER_WORKFLOW_NAME),
    TaskEnvironmentConfig(
        name=FUNCTIONAL_QC_WORKFLOW_NAME,
        kwargs={
            "resources": flyte.Resources(cpu="4", memory="8Gi"),
            "description": "BUSCO functional QC stage.",
        },
    ),
    TaskEnvironmentConfig(name=EGGNOG_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=AGAT_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=AGAT_CONVERSION_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=AGAT_CLEANUP_WORKFLOW_NAME),
    TaskEnvironmentConfig(name=TABLE2ASN_WORKFLOW_NAME),
)

TASK_ENVIRONMENT_NAMES = tuple(config.name for config in TASK_ENVIRONMENT_CONFIGS)
TASK_ENVIRONMENTS_BY_NAME = {
    config.name: make_task_environment(config)
    for config in TASK_ENVIRONMENT_CONFIGS
}

rnaseq_qc_quant_env = TASK_ENVIRONMENTS_BY_NAME[TASK_ENV_NAME]
env = rnaseq_qc_quant_env
transcript_evidence_env = TASK_ENVIRONMENTS_BY_NAME[TRANSCRIPT_EVIDENCE_WORKFLOW_NAME]
pasa_env = TASK_ENVIRONMENTS_BY_NAME[PASA_WORKFLOW_NAME]
pasa_update_env = TASK_ENVIRONMENTS_BY_NAME[PASA_UPDATE_WORKFLOW_NAME]
transdecoder_env = TASK_ENVIRONMENTS_BY_NAME[TRANSDECODER_WORKFLOW_NAME]
protein_evidence_env = TASK_ENVIRONMENTS_BY_NAME[PROTEIN_EVIDENCE_WORKFLOW_NAME]
annotation_env = TASK_ENVIRONMENTS_BY_NAME[ANNOTATION_WORKFLOW_NAME]
consensus_prep_env = TASK_ENVIRONMENTS_BY_NAME[CONSENSUS_PREP_WORKFLOW_NAME]
consensus_env = consensus_prep_env
consensus_evm_env = TASK_ENVIRONMENTS_BY_NAME[CONSENSUS_EVM_WORKFLOW_NAME]
repeat_filter_env = TASK_ENVIRONMENTS_BY_NAME[REPEAT_FILTER_WORKFLOW_NAME]
functional_qc_env = TASK_ENVIRONMENTS_BY_NAME[FUNCTIONAL_QC_WORKFLOW_NAME]
eggnog_env = TASK_ENVIRONMENTS_BY_NAME[EGGNOG_WORKFLOW_NAME]
agat_env = TASK_ENVIRONMENTS_BY_NAME[AGAT_WORKFLOW_NAME]
agat_conversion_env = TASK_ENVIRONMENTS_BY_NAME[AGAT_CONVERSION_WORKFLOW_NAME]
agat_cleanup_env = TASK_ENVIRONMENTS_BY_NAME[AGAT_CLEANUP_WORKFLOW_NAME]
table2asn_env = TASK_ENVIRONMENTS_BY_NAME[TABLE2ASN_WORKFLOW_NAME]
DEFAULT_SLURM_ACCOUNT = os.environ.get("FLYTETEST_SLURM_ACCOUNT", "rcc-staff")


def project_tmp_root() -> Path:
    """Return the project-local scratch root used by task work directories."""
    configured = os.environ.get(PROJECT_TMP_ENV_VAR)
    root = Path(configured) if configured else Path.cwd() / RESULTS_ROOT / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_mkdtemp(prefix: str) -> Path:
    """Create one temporary work directory under the project-local results tree.

    Args:
        prefix: Prefix for the generated scratch directory name.

    Returns:
        Path to the newly created temporary work directory.
    """
    return Path(tempfile.mkdtemp(prefix=prefix, dir=project_tmp_root()))


def configure_project_tmpdir() -> Path:
    """Point Python's default temp directory at the project-local scratch root."""
    root = project_tmp_root()
    os.environ["TMPDIR"] = str(root)
    tempfile.tempdir = str(root)
    return root


configure_project_tmpdir()


def run(
    cmd: list[str],
    cwd: Path | None = None,
    stdout_path: Path | None = None,
) -> None:
    """Run a subprocess, optionally writing stdout into a stable output file.

    Args:
        cmd: Command arguments passed to `subprocess.run()`.
        cwd: Working directory for the subprocess, if any.
        stdout_path: Optional file that receives captured stdout.
    """
    if stdout_path is None:
        subprocess.run(cmd, check=True, cwd=cwd)
        return

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w") as handle:
        subprocess.run(cmd, check=True, cwd=cwd, stdout=handle)


def require_path(path: Path, description: str) -> Path:
    """Return an existing path or raise a descriptive `FileNotFoundError`.

    Args:
        path: File or directory the caller expects to exist.
        description: Human-readable label used in the error message.

    Returns:
        The same path, after confirming it already exists.
    """
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
    """Run a tool natively or inside a bound Singularity or Apptainer image.

    Args:
        cmd: Command arguments passed to the native or containerized runner.
        sif: Optional container image path; empty string means native execution.
        bind_paths: Paths to bind into the container before execution.
        cwd: Working directory for the subprocess, if any.
        stdout_path: Optional file that receives captured stdout.
    """
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
