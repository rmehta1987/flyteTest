"""Stdio MCP server for recipe-backed FLyteTest planning and execution.

This module exposes a recipe-first MCP surface: prompts are planned into typed
workflow specs, saved as inspectable artifacts, and then executed locally
through explicit node handlers.
"""

from __future__ import annotations

import difflib
import inspect
from importlib import import_module
import json
import logging
import os
import time
import shlex
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from io import TextIOWrapper
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

import flytetest.planner_types as planner_types_module
from flytetest.errors import (
    BindingPathMissingError,
    BindingTypeMismatchError,
    UnknownOutputNameError,
    UnknownRunIdError,
)
from flytetest.mcp_replies import (
    DryRunReply,
    PlanDecline,
    RunReply,
    SuggestedBundle,
    SuggestedPriorRun,
    ValidateRecipeReply,
)
from flytetest.mcp_contract import (
    ANNOTATION_AGAT_CLEANUP_TOOL_NAME,
    ANNOTATION_AGAT_CONVERT_TOOL_NAME,
    ANNOTATION_AGAT_STATS_TOOL_NAME,
    ANNOTATION_BRAKER3_TOOL_NAME,
    ANNOTATION_BUSCO_ASSESS_TOOL_NAME,
    ANNOTATION_BUSCO_QC_TOOL_NAME,
    ANNOTATION_EGGNOG_TOOL_NAME,
    ANNOTATION_EXONERATE_CHUNK_TOOL_NAME,
    ANNOTATION_GFFREAD_PROTEINS_TOOL_NAME,
    ANNOTATION_PROTEIN_EVIDENCE_TOOL_NAME,
    ANNOTATION_TABLE2ASN_TOOL_NAME,
    APPROVE_COMPOSED_RECIPE_TOOL_NAME,
    CANCEL_SLURM_JOB_TOOL_NAME,
    DECLINE_CATEGORY_CODES,
    EXAMPLE_PROMPT_REQUIREMENTS,
    FETCH_JOB_LOG_TOOL_NAME,
    GET_PIPELINE_STATUS_TOOL_NAME,
    GET_RUN_SUMMARY_TOOL_NAME,
    INSPECT_RUN_RESULT_TOOL_NAME,
    LIST_AVAILABLE_BINDINGS_TOOL_NAME,
    LIST_BUNDLES_TOOL_NAME,
    LIST_ENTRIES_LIMITATIONS,
    LIST_SLURM_RUN_HISTORY_TOOL_NAME,
    LOAD_BUNDLE_TOOL_NAME,
    MCP_RESOURCE_URIS,
    MCP_TOOL_NAMES,
    MONITOR_SLURM_JOB_TOOL_NAME,
    PREPARE_RECIPE_TOOL_NAME,
    PRIMARY_TOOL_NAME,
    PROMPT_REQUIREMENTS,
    PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
    REASON_CODE_COMPLETED,
    REASON_CODE_MISSING_REQUIRED_INPUTS,
    REASON_CODE_NONZERO_EXIT_STATUS,
    REASON_CODE_UNSUPPORTED_EXECUTION_TARGET,
    REASON_CODE_UNSUPPORTED_OR_AMBIGUOUS_REQUEST,
    RECIPE_INPUT_BINDING_RULES,
    RECIPE_INPUT_CONTEXT_FIELDS,
    RECIPE_INPUT_MANIFEST_RULES,
    RECIPE_INPUT_RUNTIME_RULES,
    RESULT_CODE_DECLINED_MISSING_INPUTS,
    RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST,
    RESULT_CODE_DEFINITIONS,
    RESULT_CODE_FAILED_EXECUTION,
    RESULT_CODE_SUCCEEDED,
    RESULT_MANIFEST_RESOURCE_URI_PREFIX,
    RESULT_SUMMARY_FIELDS,
    RETRY_SLURM_JOB_TOOL_NAME,
    RNASEQ_FASTQC_TOOL_NAME,
    RNASEQ_QC_TOOL_NAME,
    RUN_RECIPE_RESOURCE_URI_PREFIX,
    RUN_RECIPE_TOOL_NAME,
    RUN_SLURM_RECIPE_TOOL_NAME,
    RUN_TASK_TOOL_NAME,
    RUN_WORKFLOW_TOOL_NAME,
    SHOWCASE_SERVER_NAME,
    SUPPORTED_PROTEIN_WORKFLOW_NAME,
    SUPPORTED_TARGET_NAMES,
    SUPPORTED_TASK_NAME,
    SUPPORTED_TASK_NAMES,
    SUPPORTED_WORKFLOW_NAME,
    SUPPORTED_WORKFLOW_NAMES,
    TASK_EXAMPLE_PROMPT,
    TOOL_DESCRIPTIONS,
    VALIDATE_RUN_RECIPE_TOOL_NAME,
    VC_ANNOTATE_SNPEFF_TOOL_NAME,
    VC_CUSTOM_FILTER_TOOL_NAME,
    VC_APPLY_CUSTOM_FILTER_TOOL_NAME,
    VC_GERMLINE_DISCOVERY_TOOL_NAME,
    VC_GENOTYPE_REFINEMENT_TOOL_NAME,
    VC_POST_CALL_QC_SUMMARY_TOOL_NAME,
    VC_POST_GENOTYPING_REFINEMENT_TOOL_NAME,
    VC_PRE_CALL_COVERAGE_QC_TOOL_NAME,
    VC_PREPARE_REFERENCE_TOOL_NAME,
    VC_PREPROCESS_SAMPLE_TOOL_NAME,
    VC_SEQUENTIAL_INTERVAL_HC_TOOL_NAME,
    VC_SMALL_COHORT_FILTER_TOOL_NAME,
    WAIT_FOR_SLURM_JOB_TOOL_NAME,
    WORKFLOW_EXAMPLE_PROMPT,
    supported_runnable_targets_payload,
)
from flytetest.pipeline_tracker import (
    get_annotation_pipeline_status,
    get_pipeline_summary,
)
from flytetest.planning import (
    plan_request as preview_plan_request,
    plan_request_reshape,
    plan_typed_request,
    showcase_limitations,
    supported_entry_parameters,
)
from flytetest.registry import RegistryEntry, get_entry
from flytetest.registry import list_entries as registry_list_entries
from flytetest.resolver import _materialize_bindings
from flytetest.spec_artifacts import (
    DEFAULT_DURABLE_ASSET_INDEX_FILENAME,
    artifact_from_typed_plan,
    check_recipe_approval,
    load_durable_asset_index,
    load_workflow_spec_artifact,
    make_recipe_id,
    RecipeApprovalRecord,
    RECIPE_APPROVAL_SCHEMA_VERSION,
    save_recipe_approval,
    save_workflow_spec_artifact,
)
from flytetest.spec_executor import (
    DEFAULT_LOCAL_RUN_RECORD_FILENAME,
    DEFAULT_SLURM_RUN_RECORD_FILENAME,
    LocalNodeExecutionRequest,
    LocalRunRecord,
    LocalSpecExecutionResult,
    SlurmRunRecord,
    SlurmRetryResult,
    LocalWorkflowSpecExecutor,
    SlurmLifecycleResult,
    SlurmSpecExecutionResult,
    SlurmWorkflowSpecExecutor,
    _TERMINAL_SLURM_STATES,
    _command_is_available,
    load_local_run_record,
    load_slurm_run_record,
)
from flytetest.staging import StagingFinding, check_offline_staging, format_finding
from flytetest.specs import ResourceSpec, RuntimeImageSpec


_LOG = logging.getLogger(__name__)


REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "flyte_rnaseq_workflow.py"
DEFAULT_RECIPE_DIR = REPO_ROOT / ".runtime" / "specs"
DEFAULT_RUN_DIR = REPO_ROOT / ".runtime" / "runs"
DEFAULT_LATEST_SLURM_RUN_RECORD_POINTER = "latest_slurm_run_record.txt"
DEFAULT_LATEST_SLURM_ARTIFACT_POINTER = "latest_slurm_artifact.txt"
SERVER_TOOL_NAMES = MCP_TOOL_NAMES
SERVER_RESOURCE_URIS = MCP_RESOURCE_URIS
BUSCO_FIXTURE_TASK_NAME = "busco_assess_proteins"

# Per-task parameter definitions: (name, required) tuples for validation.
TASK_PARAMETERS: dict[str, tuple[tuple[str, bool], ...]] = {
    "exonerate_align_chunk": (
        ("genome", True),
        ("protein_chunk", True),
        ("exonerate_sif", False),
        ("exonerate_model", False),
    ),
    "busco_assess_proteins": (
        ("proteins_fasta", True),
        ("lineage_dataset", True),
        ("busco_sif", False),
        ("busco_cpu", False),
        ("busco_mode", False),
    ),
    "fastqc": (
        ("left", True),
        ("right", True),
        ("fastqc_sif", False),
    ),
    "gffread_proteins": (
        ("annotation_gff3", True),
        ("genome_fasta", True),
        ("protein_output_stem", False),
        ("gffread_binary", False),
        ("repeat_filter_sif", False),
    ),
    "create_sequence_dictionary": (
        ("gatk_sif", False),
    ),
    "index_feature_file": (
        ("gatk_sif", False),
    ),
    "base_recalibrator": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "apply_bqsr": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "haplotype_caller": (
        ("sample_id", True),
        ("intervals", False),
        ("gatk_sif", False),
    ),
    "combine_gvcfs": (
        ("cohort_id", False),
        ("gatk_sif", False),
    ),
    "joint_call_gvcfs": (
        ("sample_ids", True),
        ("intervals", True),
        ("cohort_id", False),
        ("gatk_sif", False),
    ),
    # Milestone I — ported task parameters
    "bwa_mem2_index": (
        ("bwa_sif", False),
    ),
    "bwa_mem2_mem": (
        ("sample_id", True),
        ("threads", False),
        ("library_id", False),
        ("platform", False),
        ("bwa_sif", False),
    ),
    "sort_sam": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "mark_duplicates": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "merge_bam_alignment": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "gather_vcfs": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "variant_recalibrator": (
        ("mode", True),
        ("cohort_id", True),
        ("sample_count", True),
        ("gatk_sif", False),
    ),
    "apply_vqsr": (
        ("mode", True),
        ("cohort_id", True),
        ("truth_sensitivity_filter_level", False),
        ("gatk_sif", False),
    ),
    "calculate_genotype_posteriors": (
        ("cohort_id", True),
        ("gatk_sif", False),
    ),
    # Milestone I — new task parameters (Steps 04–06)
    "variant_filtration": (
        ("mode", True),
        ("cohort_id", True),
        ("gatk_sif", False),
    ),
    "collect_wgs_metrics": (
        ("sample_id", True),
        ("gatk_sif", False),
    ),
    "bcftools_stats": (
        ("cohort_id", True),
        ("bcftools_sif", False),
    ),
    "multiqc_summarize": (
        ("cohort_id", True),
        ("multiqc_sif", False),
    ),
    "snpeff_annotate": (
        ("cohort_id", True),
        ("snpeff_database", True),
        ("snpeff_data_dir", True),
        ("snpeff_sif", False),
    ),
    "my_custom_filter": (
        ("min_qual", False),
    ),
}


def _resolve_flyte_cli() -> str:
    """Resolve the Flyte CLI, preferring the repo-local virtualenv binary."""
    repo_flyte = REPO_ROOT / ".venv" / "bin" / "flyte"
    if repo_flyte.exists():
        return str(repo_flyte)

    resolved = shutil.which("flyte")
    return resolved if resolved is not None else "flyte"


def _supported_runnable_targets() -> list[dict[str, str]]:
    """Return the showcase target list exposed through MCP resources."""
    return supported_runnable_targets_payload()


def _write_latest_slurm_submission_pointers(
    run_root: Path,
    *,
    artifact_path: Path,
    run_record_path: Path,
) -> None:
    """Persist generic pointer files for the newest successful Slurm submission.

    These pointers are maintained at the shared MCP/server boundary rather than
    only inside RCC scenario wrappers. That keeps direct `run_slurm_recipe`
    submissions observable by helper scripts such as
    `scripts/rcc/watch_slurm_run_record.sh`, even when the job was launched
    from a generic client prompt instead of a wrapper-specific submit script.

    Args:
        run_root: Durable Slurm run-record directory where pointer files should
            live alongside the per-run subdirectories.
        artifact_path: Frozen recipe artifact that was just accepted by Slurm.
        run_record_path: Durable run record created for the accepted
            submission.
    """
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / DEFAULT_LATEST_SLURM_RUN_RECORD_POINTER).write_text(
        f"{run_record_path}\n"
    )
    (run_root / DEFAULT_LATEST_SLURM_ARTIFACT_POINTER).write_text(
        f"{artifact_path}\n"
    )


def _read_pointer_value(pointer_path: Path) -> str | None:
    """Return one pointer-file target path when the pointer exists."""
    if not pointer_path.is_file():
        return None
    value = pointer_path.read_text().strip()
    return value or None


def _effective_slurm_history_state(record: SlurmRunRecord) -> str:
    """Return the best available scheduler state for history filtering."""
    return (record.final_scheduler_state or record.scheduler_state or "").upper()


def _serialize_slurm_history_entry(record: SlurmRunRecord) -> dict[str, object]:
    """Serialize one durable Slurm run record for the MCP history tool."""
    effective_state = _effective_slurm_history_state(record)
    return {
        "run_id": record.run_id,
        "workflow_name": record.workflow_name,
        "job_id": record.job_id,
        "run_record_path": str(record.run_record_path),
        "artifact_path": str(record.artifact_path),
        "script_path": str(record.script_path),
        "execution_profile": record.execution_profile,
        "submitted_at": record.submitted_at,
        "scheduler_state": record.scheduler_state,
        "final_scheduler_state": record.final_scheduler_state,
        "effective_scheduler_state": effective_state,
        "is_terminal": effective_state in _TERMINAL_SLURM_STATES,
        "scheduler_state_source": record.scheduler_state_source,
        "scheduler_exit_code": record.scheduler_exit_code,
        "last_reconciled_at": record.last_reconciled_at,
        "cancellation_requested_at": record.cancellation_requested_at,
        "attempt_number": record.attempt_number,
        "lineage_root_run_id": record.lineage_root_run_id,
        "lineage_root_run_record_path": str(record.lineage_root_run_record_path)
        if record.lineage_root_run_record_path is not None
        else None,
        "retry_parent_run_id": record.retry_parent_run_id,
        "retry_parent_run_record_path": str(record.retry_parent_run_record_path)
        if record.retry_parent_run_record_path is not None
        else None,
        "retry_child_run_ids": list(record.retry_child_run_ids),
        "retry_child_run_record_paths": [str(path) for path in record.retry_child_run_record_paths],
    }


def _list_slurm_run_history_impl(
    *,
    run_dir: Path | None = None,
    limit: int = 20,
    workflow_name: str | None = None,
    active_only: bool = False,
    terminal_only: bool = False,
) -> dict[str, object]:
    """List recent durable Slurm run records without querying the scheduler.

    Args:
        run_dir: Root directory that stores per-run Slurm record directories.
        limit: Maximum number of history entries to return, ordered newest
            first by durable submission timestamp.
        workflow_name: Optional exact workflow-name filter applied to the
            durable records after they are loaded from disk.
        active_only: When ``True``, keep only records whose effective state is
            not terminal.
        terminal_only: When ``True``, keep only records whose effective state
            is terminal.
    """
    history_root = run_dir or DEFAULT_RUN_DIR
    filters = {
        "workflow_name": workflow_name,
        "active_only": active_only,
        "terminal_only": terminal_only,
        "limit": limit,
    }
    if limit <= 0 or (active_only and terminal_only):
        validation_errors: list[str] = []
        if limit <= 0:
            validation_errors.append("limit must be >= 1")
        if active_only and terminal_only:
            validation_errors.append("active_only and terminal_only cannot both be true")
        return {
            "supported": False,
            "run_root": str(history_root),
            "filters": filters,
            "latest_run_record_path": _read_pointer_value(
                history_root / DEFAULT_LATEST_SLURM_RUN_RECORD_POINTER
            ),
            "latest_artifact_path": _read_pointer_value(
                history_root / DEFAULT_LATEST_SLURM_ARTIFACT_POINTER
            ),
            "returned_count": 0,
            "matched_count": 0,
            "total_count": 0,
            "entries": [],
            "limitations": validation_errors,
            "assumptions": [],
        }

    records: list[SlurmRunRecord] = []
    limitations: list[str] = []
    if history_root.is_dir():
        for entry in sorted(history_root.iterdir()):
            if not entry.is_dir():
                continue
            record_path = entry / DEFAULT_SLURM_RUN_RECORD_FILENAME
            if not record_path.is_file():
                continue
            try:
                records.append(load_slurm_run_record(entry))
            except Exception as exc:
                limitations.append(f"Skipped unreadable Slurm run record {record_path}: {exc}")

    records.sort(
        key=lambda record: (
            "" if record.submitted_at == "not_recorded" else record.submitted_at,
            record.last_reconciled_at or "",
            record.run_id,
        ),
        reverse=True,
    )
    filtered_records = [
        record
        for record in records
        if (workflow_name is None or record.workflow_name == workflow_name)
        and (not active_only or _effective_slurm_history_state(record) not in _TERMINAL_SLURM_STATES)
        and (not terminal_only or _effective_slurm_history_state(record) in _TERMINAL_SLURM_STATES)
    ]
    entries = [_serialize_slurm_history_entry(record) for record in filtered_records[:limit]]
    return {
        "supported": True,
        "run_root": str(history_root),
        "filters": filters,
        "latest_run_record_path": _read_pointer_value(
            history_root / DEFAULT_LATEST_SLURM_RUN_RECORD_POINTER
        ),
        "latest_artifact_path": _read_pointer_value(
            history_root / DEFAULT_LATEST_SLURM_ARTIFACT_POINTER
        ),
        "returned_count": len(entries),
        "matched_count": len(filtered_records),
        "total_count": len(records),
        "entries": entries,
        "limitations": limitations,
        "assumptions": [
            "History is read from durable .runtime/runs records only; this tool does not query Slurm.",
            "Only accepted Slurm submissions whose run-record directories still exist can appear in this listing.",
            "workflow_name filtering matches the durable run-record workflow_name field rather than higher-level MCP target aliases.",
        ],
    }


def list_slurm_run_history(
    limit: int = 20,
    workflow_name: str | None = None,
    active_only: bool = False,
    terminal_only: bool = False,
) -> dict[str, object]:
    """List recent durable Slurm submissions from `.runtime/runs/`."""
    return _list_slurm_run_history_impl(
        limit=limit,
        workflow_name=workflow_name,
        active_only=active_only,
        terminal_only=terminal_only,
    )


def _get_pipeline_status_impl(
    *,
    runs_dir: Path | None = None,
) -> dict[str, object]:
    """Return per-stage status for the 15-stage annotation pipeline."""
    history_root = runs_dir or DEFAULT_RUN_DIR
    stages = get_annotation_pipeline_status(history_root)
    summary = get_pipeline_summary(stages)
    return {
        "supported": True,
        "run_root": str(history_root),
        "summary": summary,
        "stages": [
            {
                "index": s.stage_index,
                "workflow_name": s.workflow_name,
                "label": s.label,
                "status": s.status,
                "job_id": s.job_id,
                "run_record_path": s.run_record_path,
                "submitted_at": s.submitted_at,
            }
            for s in stages
        ],
    }


def get_pipeline_status() -> dict[str, object]:
    """Return checklist status for all 15 annotation pipeline stages.

    Reads durable Slurm run records from ``.runtime/runs/`` and maps each
    stage to COMPLETED, FAILED, RUNNING, PENDING, or UNKNOWN based on the
    most recent submission for that stage.
    """
    return _get_pipeline_status_impl()


def _entry_payload(entry: RegistryEntry) -> dict[str, object]:
    c = entry.compatibility
    return {
        "name": entry.name,
        "category": entry.category,
        "description": entry.description,
        "pipeline_family": c.pipeline_family,
        "pipeline_stage_order": c.pipeline_stage_order,
        "biological_stage": c.biological_stage,
        "accepted_planner_types": list(c.accepted_planner_types),
        "produced_planner_types": list(c.produced_planner_types),
        "supported_execution_profiles": list(c.supported_execution_profiles),
        "slurm_resource_hints": c.execution_defaults.get("slurm_resource_hints", {}),
        "local_resource_defaults": c.execution_defaults.get("local_resource_defaults", {}),
        "inputs": [asdict(f) for f in entry.inputs],
        "outputs": [asdict(f) for f in entry.outputs],
        "tags": list(entry.tags),
        "execution_defaults": dict(c.execution_defaults),
    }


def _supported_entry_payloads() -> list[dict[str, object]]:
    """Return the serialized showcase targets shared by tools and resources."""
    return [_entry_payload(e) for e in registry_list_entries() if e.showcase_module]


def _normalize_manifest_sources(manifest_sources: Sequence[str | Path] | None) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    """Validate manifest sources before typed planning runs.

    Args:
        manifest_sources: Paths to prior run manifests or result directories used to seed planning.

    Returns:
        Resolved manifest-bearing paths and any validation problems encountered while loading them.
"""
    resolved_sources: list[Path] = []
    limitations: list[str] = []
    for raw_source in manifest_sources or ():
        source_path = Path(raw_source)
        if not source_path.exists():
            limitations.append(f"Manifest source `{source_path}` does not exist.")
            continue
        if source_path.is_dir():
            manifest_path = source_path / "run_manifest.json"
            if not manifest_path.exists():
                limitations.append(f"Manifest source `{source_path}` does not contain `run_manifest.json`.")
                continue
            if not os.access(manifest_path, os.R_OK):
                limitations.append(f"Manifest source `{source_path}` is not readable.")
                continue
            resolved_sources.append(source_path)
            continue
        if source_path.name != "run_manifest.json":
            limitations.append(
                f"Manifest source `{source_path}` must be a `run_manifest.json` file or a result directory."
            )
            continue
        if not os.access(source_path, os.R_OK):
            limitations.append(f"Manifest source `{source_path}` is not readable.")
            continue
        resolved_sources.append(source_path)
    return tuple(resolved_sources), tuple(limitations)


def _recipe_input_context_payload(
    *,
    manifest_sources: Sequence[str | Path] | None = None,
    explicit_bindings: Mapping[str, Any] | None = None,
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
) -> dict[str, object]:
    """Serialize the explicit recipe input context for MCP responses.

    Args:
        manifest_sources: Upstream run records or manifest paths that may supply planner inputs.
        explicit_bindings: User-provided planner inputs that override values inferred from manifests.
        runtime_bindings: Frozen execution-time bindings carried alongside the typed plan.
        resource_request: Explicit CPU, memory, and scheduler requirements from the request.
        execution_profile: Named execution target requested by the caller.
        runtime_image: Container image policy used to bind the recipe's runtime environment.

    Returns:
        A JSON-compatible snapshot of the planning context passed to the MCP client.
"""
    return {
        "manifest_sources": [str(path) for path in (manifest_sources or ())],
        "explicit_bindings": _jsonable(dict(explicit_bindings or {})),
        "runtime_bindings": _jsonable(dict(runtime_bindings or {})),
        "resource_request": _jsonable(resource_request or {}),
        "execution_profile": execution_profile,
        "runtime_image": _jsonable(runtime_image or {}),
    }


def _unsupported_recipe_prep_plan(
    prompt: str,
    *,
    limitations: Sequence[str],
    recipe_input_context: dict[str, object],
) -> dict[str, object]:
    """Build a structured decline payload for invalid recipe inputs.

    Args:
        prompt: Natural-language prompt being planned or frozen into a recipe.
        limitations: Validation failures that explain why recipe preparation cannot continue.
        recipe_input_context: The normalized manifest, binding, and runtime context sent to planning.

    Returns:
        A decline record that preserves the supplied context for client-side review.
"""
    limitation_list = [str(limitation) for limitation in limitations]
    return {
        "supported": False,
        "original_request": prompt,
        "planning_outcome": "declined",
        "candidate_outcome": None,
        "biological_goal": None,
        "matched_entry_names": [],
        "required_planner_types": [],
        "produced_planner_types": [],
        "resolved_inputs": {},
        "missing_requirements": limitation_list,
        "runtime_requirements": [],
        "assumptions": [
            "Recipe preparation validates manifest sources before typed planning runs.",
        ],
        "rationale": limitation_list or ["The supplied recipe inputs could not be validated."],
        "workflow_spec": None,
        "binding_plan": None,
        "metadata_only": True,
        "recipe_input_context": recipe_input_context,
    }


def _workflow_command_flag(name: str) -> str:
    """Return the `flyte run` flag name for one workflow input."""
    return f"--{name}"


def _extract_output_paths(*streams: str) -> list[str]:
    """Collect existing absolute filesystem paths mentioned in command output.

    Args:
        streams: Command stdout and stderr strings to scan for existing absolute paths.

    Returns:
        Deduplicated absolute paths that still exist on disk.
"""
    seen: list[str] = []
    for stream in streams:
        for token in stream.split():
            candidate = token.strip("[](){}<>,;:'\"")
            if not candidate.startswith("/"):
                continue
            path = Path(candidate)
            if path.exists() and str(path) not in seen:
                seen.append(str(path))
    return seen


def _workflow_requires_direct_python(inputs: Mapping[str, object]) -> bool:
    """Return whether a workflow input payload should bypass `flyte run`.

    Args:
        inputs: Workflow inputs that may include nested collections unsupported by the CLI serializer.

    Returns:
        ``True`` when collection-shaped values require a direct Python call.
"""
    return any(isinstance(value, (list, tuple, dict)) for value in inputs.values())


def _is_flyte_file_annotation(annotation: Any) -> bool:
    """Return whether an annotation represents `flyte.io.File`."""
    from flyte.io import File

    return annotation is File or get_origin(annotation) is File


def _is_flyte_dir_annotation(annotation: Any) -> bool:
    """Return whether an annotation represents `flyte.io.Dir`."""
    from flyte.io import Dir

    return annotation is Dir or get_origin(annotation) is Dir


def _coerce_direct_workflow_input(annotation: Any, value: Any) -> Any:
    """Convert local path inputs into the objects expected by direct workflow calls.

    Args:
        annotation: Type annotation for the workflow parameter being adapted.
        value: Local path or collection value that should be wrapped for direct Flyte execution.

    Returns:
        The input converted to Flyte `File` / `Dir` wrappers where needed.
"""
    from flyte.io import Dir, File

    if value in (None, ""):
        return value

    if annotation in (Any, inspect._empty):
        return value

    if _is_flyte_file_annotation(annotation):
        return value if isinstance(value, File) else File(path=str(value))

    if _is_flyte_dir_annotation(annotation):
        return value if isinstance(value, Dir) else Dir(path=str(value))

    origin = get_origin(annotation)
    if origin in (list, tuple):
        inner_type = get_args(annotation)[0] if get_args(annotation) else Any
        converted = [_coerce_direct_workflow_input(inner_type, item) for item in value]
        return converted if origin is list else tuple(converted)

    if origin is dict:
        args = get_args(annotation)
        key_type = args[0] if len(args) > 0 else Any
        value_type = args[1] if len(args) > 1 else Any
        return {
            _coerce_direct_workflow_input(key_type, key): _coerce_direct_workflow_input(value_type, item)
            for key, item in value.items()
        }

    union_args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    if union_args and len(union_args) == 1:
        return _coerce_direct_workflow_input(union_args[0], value)

    return value


def _load_showcase_workflow_callable(workflow_name: str) -> Any:
    """Import one runnable showcase workflow by its registered name."""
    from flytetest.mcp_contract import SHOWCASE_TARGETS_BY_NAME

    target = SHOWCASE_TARGETS_BY_NAME.get(workflow_name)
    if target is None or target.category != "workflow":
        raise ValueError(f"No runnable showcase workflow metadata is supported for `{workflow_name}`.")

    module = import_module(target.module_name)
    workflow = getattr(module, workflow_name, None)
    if workflow is None:
        raise AttributeError(f"Workflow `{workflow_name}` is not exported from `{target.module_name}`.")
    return workflow


def _prepare_direct_workflow_inputs(workflow: Any, inputs: Mapping[str, object]) -> dict[str, object]:
    """Build one direct-call argument payload from plain local path values.

    Args:
        workflow: Workflow object or Flyte workflow metadata being adapted for direct invocation.
        inputs: Plain local paths and scalars collected from the MCP request.

    Returns:
        Direct-call keyword arguments with path values wrapped for the workflow signature.
"""
    target = getattr(workflow, "func", workflow)
    parameters = inspect.signature(target).parameters
    type_hints = get_type_hints(target)
    prepared: dict[str, object] = {}
    for name, value in inputs.items():
        annotation = type_hints.get(
            name,
            parameters.get(name, inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD)).annotation,
        )
        prepared[name] = _coerce_direct_workflow_input(annotation, value)
    return prepared


def _collect_workflow_output_paths(value: Any) -> list[str]:
    """Extract stable output paths from one direct workflow return value.

    Args:
        value: Returned Flyte objects, paths, or nested containers from a direct workflow call.

    Returns:
        Stable path strings discovered in the workflow result.
"""
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        paths: list[str] = []
        for item in value.values():
            paths.extend(_collect_workflow_output_paths(item))
        return list(dict.fromkeys(paths))
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for item in value:
            paths.extend(_collect_workflow_output_paths(item))
        return list(dict.fromkeys(paths))

    if hasattr(value, "download_sync"):
        try:
            downloaded = value.download_sync()
        except Exception:
            downloaded = getattr(value, "path", "")
        if downloaded:
            return [str(downloaded)]

    if hasattr(value, "path") and getattr(value, "path") not in (None, ""):
        return [str(getattr(value, "path"))]

    if isinstance(value, Path):
        return [str(value)]

    return []


def _run_workflow_direct(workflow_name: str, inputs: Mapping[str, object]) -> dict[str, object]:
    """Execute one supported workflow through a direct Python call.

    Args:
        workflow_name: Registered workflow name chosen from the showcase surface.
        inputs: Workflow inputs that the Flyte CLI cannot reliably serialize as nested collections.

    Returns:
        A structured execution record describing the direct-call attempt and any emitted paths.
"""
    try:
        workflow = _load_showcase_workflow_callable(workflow_name)
        prepared_inputs = _prepare_direct_workflow_inputs(workflow, inputs)
        result = workflow(**prepared_inputs)
        return {
            "supported": True,
            "entry_name": workflow_name,
            "entry_category": "workflow",
            "execution_mode": "direct-python-call",
            "command": [],
            "command_text": "",
            "exit_status": 0,
            "stdout": "",
            "stderr": "",
            "output_paths": _collect_workflow_output_paths(result),
            "limitations": [
                (
                    "Direct Python workflow invocation is used for collection-shaped inputs because "
                    "the installed Flyte CLI does not reliably deserialize nested File/Dir values."
                ),
            ],
        }
    except Exception as exc:
        return {
            "supported": True,
            "entry_name": workflow_name,
            "entry_category": "workflow",
            "execution_mode": "direct-python-call",
            "command": [],
            "command_text": "",
            "exit_status": 1,
            "stdout": "",
            "stderr": str(exc),
            "output_paths": [],
            "error_type": type(exc).__name__,
            "limitations": [
                (
                    "The server attempted a direct Python workflow call because the current Flyte CLI "
                    "serialization path does not reliably support collection-shaped workflow inputs."
                ),
            ],
        }


def list_entries(
    category: str | None = None,
    pipeline_family: str | None = None,
) -> dict[str, object]:
    """List showcased MCP recipe targets, optionally filtered by category or pipeline family."""
    entries = registry_list_entries(category)
    if pipeline_family:
        entries = tuple(e for e in entries if e.compatibility.pipeline_family == pipeline_family)
    return {
        "supported": True,
        "entries": [_entry_payload(e) for e in entries if e.showcase_module],
        "limitations": list(LIST_ENTRIES_LIMITATIONS),
    }


def resource_scope() -> dict[str, object]:
    """Describe the recipe-backed MCP contract for client discovery."""
    return {
        "server_name": SHOWCASE_SERVER_NAME,
        "transport": "stdio",
        "primary_tool": PRIMARY_TOOL_NAME,
        "tool_surface": list(SERVER_TOOL_NAMES),
        "supported_runnable_targets": _supported_runnable_targets(),
        "prompt_requirements": list(PROMPT_REQUIREMENTS),
        "recipe_input_context_fields": list(RECIPE_INPUT_CONTEXT_FIELDS),
        "recipe_input_manifest_rules": list(RECIPE_INPUT_MANIFEST_RULES),
        "recipe_input_binding_rules": list(RECIPE_INPUT_BINDING_RULES),
        "recipe_input_runtime_rules": list(RECIPE_INPUT_RUNTIME_RULES),
        "recipe_artifact_directory": str(DEFAULT_RECIPE_DIR),
        "slurm_run_record_directory": str(DEFAULT_RUN_DIR),
        "limitations": list(showcase_limitations()),
    }


def resource_supported_targets() -> dict[str, object]:
    """Expose the registered targets that the server can plan or execute."""
    return {
        "primary_tool": PRIMARY_TOOL_NAME,
        "entries": _supported_entry_payloads(),
        "limitations": list(showcase_limitations()),
    }


def resource_example_prompts() -> dict[str, object]:
    """Provide prompt examples that match the current recipe surface."""
    return {
        "primary_tool": PRIMARY_TOOL_NAME,
        "workflow_prompt": WORKFLOW_EXAMPLE_PROMPT,
        "protein_workflow_prompt": PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
        "task_prompt": TASK_EXAMPLE_PROMPT,
        "prompt_requirements": list(EXAMPLE_PROMPT_REQUIREMENTS),
    }


def resource_prompt_and_run_contract() -> dict[str, object]:
    """Document the `prompt_and_run` response fields and result codes."""
    return {
        "primary_tool": PRIMARY_TOOL_NAME,
        "supported_tools": list(SERVER_TOOL_NAMES),
        "supported_runnable_targets": _supported_runnable_targets(),
        "prompt_requirements": list(PROMPT_REQUIREMENTS),
        "recipe_input_context_fields": list(RECIPE_INPUT_CONTEXT_FIELDS),
        "recipe_input_manifest_rules": list(RECIPE_INPUT_MANIFEST_RULES),
        "recipe_input_binding_rules": list(RECIPE_INPUT_BINDING_RULES),
        "recipe_input_runtime_rules": list(RECIPE_INPUT_RUNTIME_RULES),
        "recipe_artifact_directory": str(DEFAULT_RECIPE_DIR),
        "slurm_run_record_directory": str(DEFAULT_RUN_DIR),
        "result_summary_fields": list(RESULT_SUMMARY_FIELDS),
        "typed_planning_fields": [
            "planning_outcome",
            "candidate_outcome",
            "biological_goal",
            "matched_entry_names",
            "workflow_spec",
            "binding_plan",
        ],
        "result_codes": RESULT_CODE_DEFINITIONS,
        "decline_categories": DECLINE_CATEGORY_CODES,
        "limitations": [
            *showcase_limitations(),
            "Execution uses saved WorkflowSpec artifacts and explicit local node handlers.",
            "`run_slurm_recipe` submits only recipes whose frozen execution profile is `slurm`.",
        ],
    }


def plan_request(prompt: str) -> dict[str, object]:
    """Plan one request through the typed recipe planner.

    Returns the :class:`PlanSuccess` / :class:`PlanDecline` payload serialized
    to a plain dict for the FastMCP wire boundary. Single-entry matches leave
    ``artifact_path`` empty and echo a structured ``suggested_next_call`` so
    the caller commits via ``run_task`` / ``run_workflow``; composed novel DAGs
    freeze a :class:`WorkflowSpec` artifact and point at
    ``approve_composed_recipe``.

    Args:
        prompt: Natural-language request being converted into a typed plan.
"""
    return asdict(plan_request_reshape(prompt))


def _available_bundles_for_target(target: str) -> tuple[SuggestedBundle, ...]:
    """Return available bundles whose ``applies_to`` lists *target* (§10).

    Unavailable bundles are filtered out so declines never point a scientist at
    a broken starter kit.
    """
    from flytetest.bundles import BUNDLES, _check_bundle_availability

    suggestions: list[SuggestedBundle] = []
    for bundle in BUNDLES.values():
        if target not in bundle.applies_to:
            continue
        status = _check_bundle_availability(bundle)
        if not status.available:
            continue
        suggestions.append(
            SuggestedBundle(
                name=bundle.name,
                description=bundle.description,
                applies_to=tuple(bundle.applies_to),
                available=True,
            )
        )
    return tuple(suggestions)


def _scan_durable_prior_runs(
    run_history_root: Path,
    accepted_planner_types: Sequence[str],
) -> tuple[SuggestedPriorRun, ...]:
    """Scan *run_history_root* for durable asset refs matching any accepted type (§10).

    Each returned :class:`SuggestedPriorRun` carries a ``$ref``-shaped ``hint``
    string the scientist can copy straight into a ``bindings`` dict on the next
    ``run_task`` / ``run_workflow`` call.
    """
    accepted = tuple(accepted_planner_types or ())
    if not accepted or not run_history_root.is_dir():
        return ()
    accepted_set = set(accepted)
    suggestions: list[SuggestedPriorRun] = []
    for index_path in sorted(run_history_root.rglob(DEFAULT_DURABLE_ASSET_INDEX_FILENAME)):
        try:
            refs = load_durable_asset_index(index_path.parent)
        except (OSError, ValueError):
            continue
        for ref in refs:
            if not ref.produced_type or ref.produced_type not in accepted_set:
                continue
            hint = (
                f"Use bindings={{'{ref.produced_type}': "
                f"{{'$ref': {{'run_id': '{ref.run_id}', "
                f"'output_name': '{ref.output_name}'}}}}}}"
            )
            suggestions.append(
                SuggestedPriorRun(
                    run_id=ref.run_id,
                    produced_type=ref.produced_type,
                    output_name=ref.output_name,
                    hint=hint,
                )
            )
    return tuple(suggestions)


def _compose_decline_next_steps(
    bundles: Sequence[SuggestedBundle],
    prior_runs: Sequence[SuggestedPriorRun],
    *,
    extra: Sequence[str] = (),
) -> tuple[str, ...]:
    """Combine bundle / prior-run channels with generic recovery strings (§10)."""
    steps: list[str] = []
    for bundle in bundles:
        steps.append(
            f"load_bundle({bundle.name!r}) then re-call run_workflow / run_task."
        )
    if prior_runs:
        steps.append(
            "Reference a prior-run output via the $ref binding form "
            "(see suggested_prior_runs)."
        )
    steps.extend(str(item) for item in extra)
    steps.append("Call list_available_bindings(<target>) to locate unbound workspace files.")
    steps.append("Or reformulate the request with explicit typed bindings.")
    return tuple(steps)


def _limitation_reply(
    target: str,
    limitation: str,
    *,
    pipeline_family: str | None = None,
    extra_next_steps: Sequence[str] = (),
    run_history_root: Path | None = None,
) -> PlanDecline:
    """Build a structured :class:`PlanDecline` for a registered target (§10).

    Populates the three recovery channels whenever *target* names a registered
    entry:

    * ``suggested_bundles`` — available bundles whose ``applies_to`` includes
      the target.
    * ``suggested_prior_runs`` — durable asset index entries whose
      ``produced_type`` overlaps with the target's ``accepted_planner_types``.
    * ``next_steps`` — bundle + prior-run load lines followed by generic
      recovery options.

    Args:
        target: Registered task or workflow name that failed validation.
        limitation: Human-readable reason the request was declined.
        pipeline_family: Pipeline family from the registry entry when known.
            Defaults to the entry's declared family when omitted.
        extra_next_steps: Optional additional strings merged into ``next_steps``
            ahead of the generic recovery options (used by exception-specific
            decline translators).
        run_history_root: Directory scanned for ``durable_asset_index.json``
            sidecars. Defaults to :data:`DEFAULT_RUN_DIR`; tests override it
            with a ``tmp_path``-rooted fixture.
    """
    resolved_family = pipeline_family or ""
    accepted: tuple[str, ...] = ()
    try:
        entry = get_entry(target)
    except KeyError:
        entry = None
    if entry is not None:
        if not resolved_family:
            resolved_family = entry.compatibility.pipeline_family
        accepted = tuple(entry.compatibility.accepted_planner_types)

    bundles = _available_bundles_for_target(target)
    prior_runs = _scan_durable_prior_runs(
        run_history_root or DEFAULT_RUN_DIR,
        accepted_planner_types=accepted,
    )
    next_steps = _compose_decline_next_steps(
        bundles, prior_runs, extra=extra_next_steps
    )
    return PlanDecline(
        supported=False,
        target=target,
        pipeline_family=resolved_family,
        limitations=(limitation,),
        suggested_bundles=bundles,
        suggested_prior_runs=prior_runs,
        next_steps=next_steps,
    )


def _unsupported_target_reply(
    target: str,
    supported_names: Sequence[str],
    *,
    kind: str,
) -> PlanDecline:
    """Build a :class:`PlanDecline` for an unrecognised target name (§10).

    The target is unregistered so neither the pipeline family nor the accepted
    planner types are known; the bundle / prior-run channels stay empty and
    ``next_steps`` points the caller at ``list_entries`` for discovery.
    """
    supported_list = ", ".join(f"`{name}`" for name in supported_names)
    limitation = (
        f"{target!r} is not a supported {kind}. Supported {kind}s: {supported_list}."
    )
    next_steps = (
        f"Call list_entries(category={kind!r}) to browse supported {kind}s.",
        "Or reformulate the request with one of the supported target names.",
    )
    return PlanDecline(
        supported=False,
        target=target,
        pipeline_family="",
        limitations=(limitation,),
        suggested_bundles=(),
        suggested_prior_runs=(),
        next_steps=next_steps,
    )


def _execute_run_tool(
    fn: Callable[[], dict[str, object]],
    *,
    target_name: str,
    pipeline_family: str,
) -> dict[str, object]:
    """Run a reshaped run-tool body and translate typed resolution errors.

    Scientist-addressable :class:`PlannerResolutionError` subclasses become
    :class:`PlanDecline` replies with exception-type-aware ``next_steps``.
    Any other exception propagates after emitting the §3e ERROR log line so
    operator-side observability still captures the failure.

    Args:
        fn: Zero-argument callable that performs the full reshaped run-tool
            body (binding resolution, freeze, dispatch, output collection).
        target_name: Registered task or workflow name being executed, used
            to populate :class:`PlanDecline.target` and the ERROR log.
        pipeline_family: Pipeline family advertised on the registry entry,
            used to populate :class:`PlanDecline.pipeline_family`.

    Returns:
        The value returned by ``fn`` on success, or ``asdict(PlanDecline(...))``
        for a scientist-addressable resolution failure.
    """
    try:
        return fn()
    except UnknownRunIdError as exc:
        return asdict(
            PlanDecline(
                supported=False,
                target=target_name,
                pipeline_family=pipeline_family,
                limitations=(str(exc),),
                next_steps=(
                    "Call list_available_bindings(<target>) to confirm the run_id.",
                    "Re-run the producing workflow to regenerate the output.",
                    "Inspect .runtime/durable_asset_index.json for indexed runs.",
                ),
            )
        )
    except UnknownOutputNameError as exc:
        known = (
            ", ".join(sorted(exc.known_outputs)) if exc.known_outputs else "(none)"
        )
        return asdict(
            PlanDecline(
                supported=False,
                target=target_name,
                pipeline_family=pipeline_family,
                limitations=(str(exc),),
                next_steps=(
                    f"Known outputs for run {exc.run_id!r}: {known}.",
                    "Pick one of those output names, or re-run the producing workflow.",
                ),
            )
        )
    except BindingPathMissingError as exc:
        return asdict(
            PlanDecline(
                supported=False,
                target=target_name,
                pipeline_family=pipeline_family,
                limitations=(str(exc),),
                next_steps=(
                    "Call list_available_bindings(<target>) to locate substitute inputs.",
                    "Verify the path exists and is readable from this machine.",
                ),
            )
        )
    except BindingTypeMismatchError as exc:
        return asdict(
            PlanDecline(
                supported=False,
                target=target_name,
                pipeline_family=pipeline_family,
                limitations=(
                    f"Binding key {exc.binding_key!r} expected a "
                    f"{exc.binding_key} but source {exc.source!r} produces "
                    f"{exc.resolved_type!r}.",
                ),
                next_steps=(
                    f"Pick a $ref / $manifest whose producing entry declares "
                    f"{exc.binding_key!r} in produced_planner_types.",
                    "Call list_available_bindings(<target>) for compatible prior-run outputs.",
                    "Or use the raw-path form if you explicitly want to reinterpret the file.",
                ),
            )
        )
    except Exception:
        _LOG.exception(
            "Uncaught exception in run tool "
            "(recipe_id=pending tool_name=%s pipeline_family=%s)",
            target_name,
            pipeline_family,
        )
        raise


def _execute_workflow_direct(
    workflow_name: str,
    inputs: dict[str, object],
    runner: Any = subprocess.run,
) -> dict[str, object]:
    """Execute one supported workflow through `flyte run` or direct Python.

    This is the low-level workflow dispatcher shared by the reshaped
    :func:`run_workflow` (post-freeze) and the local-executor handler path.
    It accepts flat scalar inputs that the :class:`LocalWorkflowSpecExecutor`
    has already resolved from the frozen :class:`BindingPlan`.

    Args:
        workflow_name: Registered workflow name selected by the caller.
        inputs: Workflow inputs forwarded from the MCP request.
        runner: Command runner injected by tests or the local server adapter.
"""
    if workflow_name not in SUPPORTED_WORKFLOW_NAMES:
        return {
            "supported": False,
            "workflow_name": workflow_name,
            "command": [],
            "command_text": "",
            "exit_status": None,
            "stdout": "",
            "stderr": "",
            "output_paths": [],
            "limitations": [
                (
                    "Only the workflows "
                    + ", ".join(f"`{name}`" for name in SUPPORTED_WORKFLOW_NAMES)
                    + " are executable through this showcase workflow runner."
                ),
            ],
        }

    parameters = supported_entry_parameters(workflow_name)
    allowed_inputs = tuple(parameter.name for parameter in parameters)
    unknown_inputs = sorted(set(inputs) - set(allowed_inputs))
    if unknown_inputs:
        return {
            "supported": False,
            "workflow_name": workflow_name,
            "command": [],
            "command_text": "",
            "exit_status": None,
            "stdout": "",
            "stderr": "",
            "output_paths": [],
            "limitations": [f"Unknown workflow inputs: {', '.join(unknown_inputs)}."],
        }

    missing_required = [
        parameter.name
        for parameter in parameters
        if parameter.required and inputs.get(parameter.name) in (None, "")
    ]
    if missing_required:
        return {
            "supported": False,
            "workflow_name": workflow_name,
            "command": [],
            "command_text": "",
            "exit_status": None,
            "stdout": "",
            "stderr": "",
            "output_paths": [],
            "limitations": [f"Missing required workflow inputs: {', '.join(missing_required)}."],
        }

    if workflow_name == SUPPORTED_WORKFLOW_NAME and inputs.get("rnaseq_bam_path") in (None, "") and inputs.get(
        "protein_fasta_path"
    ) in (None, ""):
        return {
            "supported": False,
            "workflow_name": workflow_name,
            "command": [],
            "command_text": "",
            "exit_status": None,
            "stdout": "",
            "stderr": "",
            "output_paths": [],
            "limitations": [
                "BRAKER3 requires at least one evidence input in practice: `rnaseq_bam_path`, `protein_fasta_path`, or both.",
            ],
        }

    if _workflow_requires_direct_python(inputs):
        return _run_workflow_direct(workflow_name, inputs)

    cmd = [_resolve_flyte_cli(), "run", "--local", ENTRYPOINT.name, workflow_name]
    for name in allowed_inputs:
        value = inputs.get(name)
        if value in (None, ""):
            continue
        flag = _workflow_command_flag(name)
        if isinstance(value, list):
            for item in value:
                cmd.extend([flag, str(item)])
            continue
        cmd.extend([flag, str(value)])

    result = runner(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return {
        "supported": True,
        "entry_name": workflow_name,
        "entry_category": "workflow",
        "execution_mode": "flyte-run-local",
        "command": cmd,
        "command_text": shlex.join(cmd),
        "exit_status": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "output_paths": _extract_output_paths(stdout, stderr),
        "limitations": [
            (
                "Execution stays limited to the selected prebuilt workflow and does not imply "
                "additional downstream stages."
            ),
        ],
    }


def _execute_task_direct(task_name: str, inputs: dict[str, object]) -> dict[str, object]:
    """Execute one supported direct task through a Python call.

    This is the low-level task dispatcher shared by the reshaped
    :func:`run_task` (post-freeze) and the local-executor handler path. It
    accepts flat scalar inputs that the :class:`LocalWorkflowSpecExecutor`
    has already resolved from the frozen :class:`BindingPlan`.

    Supported task names: ``exonerate_align_chunk``, ``busco_assess_proteins``,
    ``fastqc``, and ``gffread_proteins``.
    """
    if task_name not in set(SUPPORTED_TASK_NAMES):
        return {
            "supported": False,
            "task_name": task_name,
            "exit_status": None,
            "output_paths": [],
            "limitations": [
                "Only "
                + ", ".join(f"`{n}`" for n in SUPPORTED_TASK_NAMES)
                + " are executable through this showcase task runner."
            ],
        }

    parameters = TASK_PARAMETERS[task_name]
    allowed_inputs = tuple(parameter_name for parameter_name, _ in parameters)
    unknown_inputs = sorted(set(inputs) - set(allowed_inputs))
    if unknown_inputs:
        return {
            "supported": False,
            "task_name": task_name,
            "exit_status": None,
            "output_paths": [],
            "limitations": [f"Unknown task inputs: {', '.join(unknown_inputs)}."],
        }

    missing_required = [
        parameter_name
        for parameter_name, required in parameters
        if required and inputs.get(parameter_name) in (None, "")
    ]
    if missing_required:
        return {
            "supported": False,
            "task_name": task_name,
            "exit_status": None,
            "output_paths": [],
            "limitations": [f"Missing required task inputs: {', '.join(missing_required)}."],
        }

    if task_name == "busco_assess_proteins":
        try:
            from flyte.io import File
            from flytetest.tasks.functional import busco_assess_proteins

            result = busco_assess_proteins(
                proteins_fasta=File(path=str(inputs["proteins_fasta"])),
                lineage_dataset=str(inputs["lineage_dataset"]),
                busco_sif=str(inputs.get("busco_sif") or ""),
                busco_cpu=int(inputs.get("busco_cpu") or 2),
                busco_mode=str(inputs.get("busco_mode") or "geno"),
            )
            result_path = result.download_sync() if hasattr(result, "download_sync") else getattr(result, "path", "")
            output_paths = [result_path] if result_path else []
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "direct-python-call",
                "exit_status": 0,
                "stdout": "",
                "stderr": "",
                "output_paths": output_paths,
                "limitations": [
                    "This direct BUSCO task call is used by the Milestone 18 fixture smoke recipe.",
                ],
            }
        except Exception as exc:
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "direct-python-call",
                "exit_status": 1,
                "stdout": "",
                "stderr": str(exc),
                "output_paths": [],
                "error_type": type(exc).__name__,
                "limitations": [
                    "The server attempted the BUSCO fixture task call, but runtime dependencies or BUSCO assets may be missing.",
                ],
            }

    if task_name == "fastqc":
        try:
            from flyte.io import File
            from flytetest.tasks.qc import fastqc

            result = fastqc(
                left=File(path=str(inputs["left"])),
                right=File(path=str(inputs["right"])),
                fastqc_sif=str(inputs.get("fastqc_sif") or ""),
            )
            result_path = result.download_sync() if hasattr(result, "download_sync") else getattr(result, "path", "")
            output_paths = [result_path] if result_path else []
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "direct-python-call",
                "exit_status": 0,
                "stdout": "",
                "stderr": "",
                "output_paths": output_paths,
                "limitations": [
                    "This task execution runs FastQC on paired-end FASTQ files as an ad hoc quality check.",
                ],
            }
        except Exception as exc:
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "direct-python-call",
                "exit_status": 1,
                "stdout": "",
                "stderr": str(exc),
                "output_paths": [],
                "error_type": type(exc).__name__,
                "limitations": [
                    "The server attempted the fastqc task call, but runtime dependencies or the FastQC binary may be missing.",
                ],
            }

    if task_name == "gffread_proteins":
        try:
            from flyte.io import File
            from flytetest.tasks.filtering import gffread_proteins

            result = gffread_proteins(
                annotation_gff3=File(path=str(inputs["annotation_gff3"])),
                genome_fasta=File(path=str(inputs["genome_fasta"])),
                protein_output_stem=str(inputs.get("protein_output_stem") or "annotation"),
                gffread_binary=str(inputs.get("gffread_binary") or "gffread"),
                repeat_filter_sif=str(inputs.get("repeat_filter_sif") or ""),
            )
            result_path = result.download_sync() if hasattr(result, "download_sync") else getattr(result, "path", "")
            output_paths = [result_path] if result_path else []
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "direct-python-call",
                "exit_status": 0,
                "stdout": "",
                "stderr": "",
                "output_paths": output_paths,
                "limitations": [
                    "This task extracts protein sequences from a GFF3 annotation and reference genome for ad hoc use.",
                ],
            }
        except Exception as exc:
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "direct-python-call",
                "exit_status": 1,
                "stdout": "",
                "stderr": str(exc),
                "output_paths": [],
                "error_type": type(exc).__name__,
                "limitations": [
                    "The server attempted the gffread_proteins task call, but runtime dependencies or gffread may be missing.",
                ],
            }

    if task_name in (
        "create_sequence_dictionary",
        "index_feature_file",
        "base_recalibrator",
        "apply_bqsr",
        "haplotype_caller",
        "combine_gvcfs",
        "joint_call_gvcfs",
    ):
        try:
            from flyte.io import File
            import flytetest.tasks.variant_calling as _vc

            fn = getattr(_vc, task_name)
            file_inputs = {
                k: File(path=str(v))
                for k, v in inputs.items()
                if isinstance(v, str) and k not in ("sample_id", "cohort_id", "gatk_sif", "bwa_sif", "bcftools_sif", "multiqc_sif", "snpeff_sif", "intervals")
            }
            scalar_inputs = {
                k: v for k, v in inputs.items()
                if k not in file_inputs
            }
            result = fn(**file_inputs, **scalar_inputs)
            result_path = (
                result.download_sync() if hasattr(result, "download_sync")
                else getattr(result, "path", "")
                if not isinstance(result, dict) else ""
            )
            output_paths = [result_path] if result_path else []
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "direct-python-call",
                "exit_status": 0,
                "stdout": "",
                "stderr": "",
                "output_paths": output_paths,
                "limitations": [],
            }
        except Exception as exc:
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "direct-python-call",
                "exit_status": 1,
                "stdout": "",
                "stderr": str(exc),
                "output_paths": [],
                "error_type": type(exc).__name__,
                "limitations": [
                    "The server attempted the GATK task call, but runtime dependencies or GATK binaries may be missing.",
                ],
            }

    # exonerate_align_chunk
    try:
        from flyte.io import File
        from flytetest.tasks.protein_evidence import exonerate_align_chunk

        result = exonerate_align_chunk(
            genome=File(path=str(inputs["genome"])),
            protein_chunk=File(path=str(inputs["protein_chunk"])),
            exonerate_sif=str(inputs.get("exonerate_sif", "")),
            exonerate_model=str(inputs.get("exonerate_model", "protein2genome")),
        )
        result_path = result.download_sync() if hasattr(result, "download_sync") else getattr(result, "path", "")
        output_paths = [result_path] if result_path else []
        return {
            "supported": True,
            "entry_name": task_name,
            "entry_category": "task",
            "execution_mode": "direct-python-call",
            "exit_status": 0,
            "stdout": "",
            "stderr": "",
            "output_paths": output_paths,
            "limitations": [
                "This task execution is ad hoc experimentation and not a substitute for the full protein-evidence workflow.",
            ],
        }
    except Exception as exc:
        return {
            "supported": True,
            "entry_name": task_name,
            "entry_category": "task",
            "execution_mode": "direct-python-call",
            "exit_status": 1,
            "stdout": "",
            "stderr": str(exc),
            "output_paths": [],
            "error_type": type(exc).__name__,
            "limitations": [
                "The server attempted the direct task call, but runtime dependencies or tool binaries may be missing in this environment.",
            ],
        }


# ---------------------------------------------------------------------------
# Reshaped run_task (Step 21 — MCP reshape plan §2 / §3b / §3g / §3i)
# ---------------------------------------------------------------------------


_EMPTY_PROMPT_ADVISORY = (
    "No source_prompt was supplied; replay metadata will not preserve original "
    "natural-language provenance."
)


def _scalar_params_for_task(
    task_name: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> list[tuple[str, bool]]:
    """Return ``TASK_PARAMETERS`` entries not already covered by typed bindings."""
    bound_field_names: set[str] = set()
    for field_dict in bindings.values():
        if isinstance(field_dict, Mapping):
            bound_field_names.update(field_dict.keys())
    return [
        (name, required)
        for (name, required) in TASK_PARAMETERS[task_name]
        if name not in bound_field_names
    ]


def _load_json(path: Path) -> dict[str, Any] | None:
    """Return the JSON payload at *path*, or ``None`` when unreadable."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _collect_named_outputs(
    entry: RegistryEntry,
    run_record_path: Path | None,
) -> tuple[dict[str, str], list[str]]:
    """Project node manifest outputs onto ``entry.outputs[*].name`` keys (§3b).

    Missing outputs surface as empty-string values with a prominent advisory
    for required fields and a softer advisory for optional ones. Undeclared
    manifest keys remain on disk in the manifest but do not surface here so
    the registry stays the public contract for outputs.
    """
    outputs: dict[str, str] = {}
    limitations: list[str] = []
    produced: dict[str, Any] = {}
    final_outputs: dict[str, Any] = {}

    if run_record_path is not None and run_record_path.exists():
        record_payload = _load_json(run_record_path) or {}
        final_outputs = dict(record_payload.get("final_outputs") or {})
        manifest_payload: dict[str, Any] | None = None
        for node_result in record_payload.get("node_results") or ():
            if not isinstance(node_result, Mapping):
                continue
            manifest_paths = node_result.get("manifest_paths") or {}
            if not isinstance(manifest_paths, Mapping):
                continue
            for manifest_str in manifest_paths.values():
                candidate = _load_json(Path(str(manifest_str)))
                if candidate is not None:
                    manifest_payload = candidate
                    break
            if manifest_payload is not None:
                break
        if isinstance(manifest_payload, Mapping):
            raw_outputs = manifest_payload.get("outputs") or {}
            if isinstance(raw_outputs, Mapping):
                produced = dict(raw_outputs)

    for field in entry.outputs:
        value = produced.get(field.name)
        if value in (None, ""):
            value = final_outputs.get(field.name)
        if value in (None, ""):
            outputs[field.name] = ""
            if getattr(field, "required", True):
                limitations.append(
                    f"Required output {field.name!r} was not produced by "
                    f"{entry.name}; the task may not have completed successfully."
                )
            else:
                limitations.append(
                    f"Optional output {field.name!r} was not produced by "
                    f"{entry.name}; this may be expected depending on inputs."
                )
        else:
            outputs[field.name] = str(value)
    return outputs, limitations


def _resolved_bindings_projection(
    bindings: Mapping[str, Mapping[str, Any]],
    materialized: Mapping[str, Any],
) -> dict[str, dict[str, str]]:
    """Project materialized planner objects onto a ``{type: {field: str}}`` dict."""
    projection: dict[str, dict[str, str]] = {}
    for type_name, raw in bindings.items():
        instance = materialized.get(type_name)
        inner: dict[str, str] = {}
        if instance is not None and hasattr(instance, "to_dict"):
            data = instance.to_dict()
            if isinstance(data, Mapping):
                inner = {
                    key: str(value)
                    for key, value in data.items()
                    if not isinstance(value, (dict, list))
                }
        if not inner and isinstance(raw, Mapping):
            inner = {
                str(key): str(value)
                for key, value in raw.items()
                if key not in ("$ref", "$manifest") and not isinstance(value, (dict, list))
            }
        projection[type_name] = inner
    return projection


def run_task(
    task_name: str,
    bindings: Mapping[str, Mapping[str, Any]] | None = None,
    inputs: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | None = None,
    execution_profile: str = "local",
    runtime_images: Mapping[str, str] | None = None,
    tool_databases: Mapping[str, str] | None = None,
    source_prompt: str = "",
    dry_run: bool = False,
) -> dict[str, object]:
    """Run one registered task against typed biological bindings.

    Use this for stage-scoped experimentation (e.g. running a single
    haplotype_caller on a pre-aligned BAM).  The run is frozen into an
    auditable WorkflowSpec artifact before execution.  When dry_run=True
    the artifact is written but dispatch is skipped; chain
    run_slurm_recipe(artifact_path=...) to submit.

    HOW TO CALL THIS TOOL
    ----------------------
    bindings  -- typed planner objects identifying biological roles.
                 Each key is a planner type name; each value is a dict of
                 field names and string paths.  Only pass types the task
                 accepts (check list_entries output).
                 Example for haplotype_caller:
                   bindings={
                     "ReferenceGenome": {"fasta_path": "/abs/path/chr20.fa"}
                   }

    inputs    -- flat dict using EXACT task parameter names from the function
                 signature.  Pass all required parameters here including
                 File-typed ones — string paths are coerced automatically.
                 Example for haplotype_caller:
                   inputs={
                     "reference_fasta": "/abs/path/chr20.fa",
                     "aligned_bam": "/abs/path/sample.bam",
                     "sample_id": "NA12878_chr20"
                   }

    runtime_images -- {"tool_sif": "/abs/path/tool.sif"} or {"tool_sif": ""}
                 to use a cluster module instead of a container.

    resource_request -- {"partition": "caslake", "account": "rcc-staff",
                          "cpu": "8", "memory": "32Gi", "walltime": "02:00:00",
                          "shared_fs_roots": ["/scratch/midway3"]}

    All paths must be absolute on the shared filesystem.
    """
    if task_name not in set(SUPPORTED_TASK_NAMES):
        return asdict(
            _unsupported_target_reply(task_name, SUPPORTED_TASK_NAMES, kind="task")
        )
    entry = get_entry(task_name)
    pipeline_family = entry.compatibility.pipeline_family
    bindings_in: dict[str, dict[str, Any]] = {
        str(key): dict(value) if isinstance(value, Mapping) else {}
        for key, value in (bindings or {}).items()
    }
    inputs_in: dict[str, Any] = dict(inputs or {})

    accepted = set(entry.compatibility.accepted_planner_types)
    unknown_types = sorted(set(bindings_in) - accepted)
    if unknown_types:
        accepted_list = (
            ", ".join(sorted(accepted)) if accepted else "(none declared)"
        )
        return asdict(
            _limitation_reply(
                task_name,
                f"Unknown binding types: {unknown_types}. Accepted: {accepted_list}.",
                pipeline_family=pipeline_family,
            )
        )

    scalar_params = _scalar_params_for_task(task_name, bindings_in)
    allowed_scalars = {name for name, _ in scalar_params}
    unknown_scalars = sorted(set(inputs_in) - allowed_scalars)
    if unknown_scalars:
        return asdict(
            _limitation_reply(
                task_name,
                f"Unknown scalar inputs: {unknown_scalars}.",
                pipeline_family=pipeline_family,
            )
        )
    missing_required = [
        name
        for name, required in scalar_params
        if required and inputs_in.get(name) in (None, "")
    ]
    if missing_required:
        return asdict(
            _limitation_reply(
                task_name,
                f"Missing required inputs: {missing_required}.",
                pipeline_family=pipeline_family,
            )
        )

    def _body() -> dict[str, object]:
        try:
            durable_refs = load_durable_asset_index(DEFAULT_RUN_DIR)
        except (OSError, ValueError):
            durable_refs = ()
        explicit_bindings = _materialize_bindings(
            bindings_in,
            durable_index=durable_refs,
        )

        plan = plan_typed_request(
            biological_goal=entry.compatibility.biological_stage or task_name,
            target_name=task_name,
            source_prompt=source_prompt,
            explicit_bindings=explicit_bindings,
            scalar_inputs=inputs_in,
            resource_request=resource_request,
            execution_profile=execution_profile,
            runtime_images=dict(runtime_images or {}),
            tool_databases=dict(tool_databases or {}),
        )
        if not plan.get("supported"):
            plan.setdefault("target", task_name)
            plan.setdefault("pipeline_family", pipeline_family)
            return plan

        artifact = artifact_from_typed_plan(plan, created_at=_created_at())
        artifact_path = save_workflow_spec_artifact(
            artifact,
            _recipe_artifact_destination(task_name, recipe_dir=DEFAULT_RECIPE_DIR),
        )

        plan_limitations = tuple(str(item) for item in plan.get("limitations") or ())
        if not source_prompt and _EMPTY_PROMPT_ADVISORY not in plan_limitations:
            plan_limitations = plan_limitations + (_EMPTY_PROMPT_ADVISORY,)

        if dry_run:
            _dry_findings = check_offline_staging(
                artifact.workflow_spec,
                tuple(Path(r) for r in ((resource_request or {}).get("shared_fs_roots") or [])),
                execution_profile=execution_profile if execution_profile == "slurm" else "local",
            )
            return asdict(
                DryRunReply(
                    supported=True,
                    recipe_id=Path(artifact_path).stem,
                    artifact_path=str(artifact_path),
                    execution_profile=(
                        "slurm" if execution_profile == "slurm" else "local"
                    ),
                    resolved_bindings=_resolved_bindings_projection(
                        bindings_in, explicit_bindings
                    ),
                    resolved_environment=dict(plan.get("resolved_environment") or {}),
                    staging_findings=tuple(
                        {"kind": sf.kind, "key": sf.key, "path": sf.path, "reason": sf.reason}
                        for sf in _dry_findings
                    ),
                    limitations=plan_limitations,
                    task_name=task_name,
                )
            )

        profile_value = (
            "slurm" if execution_profile == "slurm" else "local"
        )
        if profile_value == "slurm":
            _shared_fs = tuple(
                Path(r) for r in ((resource_request or {}).get("shared_fs_roots") or [])
            )
            slurm_result = SlurmWorkflowSpecExecutor(
                run_root=DEFAULT_RUN_DIR,
                repo_root=REPO_ROOT,
            ).submit(Path(artifact_path), shared_fs_roots=_shared_fs)
            run_record_path_str = (
                str(slurm_result.run_record.run_record_path)
                if slurm_result.run_record is not None
                else ""
            )
            if slurm_result.run_record is not None:
                _write_latest_slurm_submission_pointers(
                    DEFAULT_RUN_DIR,
                    artifact_path=Path(artifact_path),
                    run_record_path=slurm_result.run_record.run_record_path,
                )
            combined_limits = (
                plan_limitations
                + tuple(str(item) for item in slurm_result.limitations)
            )
            return asdict(
                RunReply(
                    supported=True,
                    recipe_id=Path(artifact_path).stem,
                    run_record_path=run_record_path_str,
                    artifact_path=str(artifact_path),
                    execution_profile="slurm",
                    execution_status="success" if slurm_result.supported else "failed",
                    exit_status=None,
                    outputs={},
                    limitations=combined_limits,
                    task_name=task_name,
                )
            )

        local_executor = LocalWorkflowSpecExecutor(
            _local_node_handlers(),
            run_root=DEFAULT_RUN_DIR,
        )
        failure_reason: str | None = None
        try:
            local_result = local_executor.execute(Path(artifact_path))
        except RuntimeError as exc:
            local_result = None  # type: ignore[assignment]
            failure_reason = str(exc)
        run_record_path: Path | None = None
        exit_status: int | None = None
        if local_result is not None and local_result.supported and local_result.node_results:
            # Derive the durable run-record path by scanning the run_root for
            # the most recently written local record that matches this workflow.
            candidates = sorted(
                DEFAULT_RUN_DIR.rglob(DEFAULT_LOCAL_RUN_RECORD_FILENAME),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                run_record_path = candidates[0]
            exit_status = 0
        if local_result is None or not local_result.supported:
            exit_status = 1
            execution_status: str = "failed"
            executor_limits: tuple[str, ...]
            if failure_reason is not None:
                executor_limits = (failure_reason,)
            else:
                executor_limits = tuple(
                    str(item) for item in local_result.limitations  # type: ignore[union-attr]
                )
        else:
            execution_status = "success"
            executor_limits = tuple(str(item) for item in local_result.limitations)
        outputs_map, output_limits = _collect_named_outputs(entry, run_record_path)
        combined_limits = plan_limitations + executor_limits + tuple(output_limits)
        return asdict(
            RunReply(
                supported=True,
                recipe_id=Path(artifact_path).stem,
                run_record_path=str(run_record_path) if run_record_path else "",
                artifact_path=str(artifact_path),
                execution_profile="local",
                execution_status=execution_status,  # type: ignore[arg-type]
                exit_status=exit_status,
                outputs=outputs_map,
                limitations=combined_limits,
                task_name=task_name,
            )
        )

    return _execute_run_tool(_body, target_name=task_name, pipeline_family=pipeline_family)


def _scalar_params_for_workflow(
    workflow_name: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> list[tuple[str, bool]]:
    """Return workflow scalar parameters not already covered by typed bindings."""
    bound_field_names: set[str] = set()
    for field_dict in bindings.values():
        if isinstance(field_dict, Mapping):
            bound_field_names.update(field_dict.keys())
    return [
        (parameter.name, parameter.required)
        for parameter in supported_entry_parameters(workflow_name)
        if parameter.name not in bound_field_names
    ]


def _braker_has_evidence(
    bindings: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
) -> bool:
    """Return True when a BRAKER3 call has at least one evidence source.

    BRAKER3 requires RNA-seq BAM or protein FASTA evidence in practice. This
    guard accepts satisfaction from either the legacy scalar form
    (``inputs.rnaseq_bam_path`` / ``inputs.protein_fasta_path``) or the typed
    binding form (``bindings.ProteinEvidenceSet`` / ``bindings.ReadSet``) so a
    bundle that fills either shape keeps working after the Step 22 reshape.
    """
    if inputs.get("rnaseq_bam_path") not in (None, ""):
        return True
    if inputs.get("protein_fasta_path") not in (None, ""):
        return True
    if bindings.get("ProteinEvidenceSet"):
        return True
    if bindings.get("ReadSet"):
        return True
    return False


def run_workflow(
    workflow_name: str,
    bindings: Mapping[str, Mapping[str, Any]] | None = None,
    inputs: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | None = None,
    execution_profile: str = "local",
    runtime_images: Mapping[str, str] | None = None,
    tool_databases: Mapping[str, str] | None = None,
    source_prompt: str = "",
    dry_run: bool = False,
) -> dict[str, object]:
    """Run one registered workflow against typed biological bindings.

    The run is frozen into an auditable WorkflowSpec artifact before execution.
    When dry_run=True the artifact is written but Slurm submission is skipped,
    letting you inspect staging_findings and artifact_path before committing
    cluster time.  Chain run_slurm_recipe(artifact_path=...) to submit.

    HOW TO CALL THIS TOOL
    ----------------------
    Two separate parameters carry the workflow's inputs:

    bindings  -- typed planner objects that identify biological roles.
                 Each key is a planner type name; each value is a dict of
                 field names and string paths.  Pass only the types the
                 workflow accepts (check list_entries output).
                 Example for germline_short_variant_discovery:
                   bindings={
                     "ReferenceGenome": {
                       "fasta_path": "/abs/path/to/chr20.fa"
                     },
                     "ReadPair": {
                       "sample_id": "NA12878_chr20",
                       "r1_path": "/abs/path/to/R1.fastq.gz",
                       "r2_path": "/abs/path/to/R2.fastq.gz"
                     }
                   }

    inputs    -- flat dict of workflow scalar parameters, using the EXACT
                 parameter names from the workflow function signature.
                 Pass ALL required scalar parameters here including File-typed
                 ones — string paths are accepted for File parameters and are
                 coerced automatically.
                 Example for germline_short_variant_discovery:
                   inputs={
                     "reference_fasta": "/abs/path/to/chr20.fa",
                     "sample_ids": ["NA12878_chr20"],
                     "r1_paths": ["/abs/path/to/R1.fastq.gz"],
                     "r2_paths": ["/abs/path/to/R2.fastq.gz"],
                     "known_sites": ["/abs/path/to/dbsnp.vcf.gz",
                                     "/abs/path/to/mills.vcf.gz"],
                     "intervals": ["chr20"],
                     "cohort_id": "NA12878_chr20"
                   }

    runtime_images -- dict of tool-key to absolute SIF path.
                 Set a key to "" (empty string) to use the cluster module
                 instead of a container.
                 Example: {"gatk_sif": "", "bwa_sif": "/abs/path/bwa_mem2.sif"}

    resource_request -- Slurm scheduler parameters.  Valid keys: partition,
                 account, cpu, memory, walltime, module_loads, shared_fs_roots.
                 shared_fs_roots is a list of filesystem prefixes visible to
                 compute nodes; used by the dry-run staging check.
                 Example: {"partition": "caslake", "account": "rcc-staff",
                            "cpu": "16", "memory": "64Gi", "walltime": "04:00:00",
                            "shared_fs_roots": ["/scratch/midway3", "/project/rcc"]}

    All paths must be absolute on the shared filesystem.
    """
    if workflow_name not in set(SUPPORTED_WORKFLOW_NAMES):
        return asdict(
            _unsupported_target_reply(
                workflow_name, SUPPORTED_WORKFLOW_NAMES, kind="workflow"
            )
        )
    entry = get_entry(workflow_name)
    pipeline_family = entry.compatibility.pipeline_family
    bindings_in: dict[str, dict[str, Any]] = {
        str(key): dict(value) if isinstance(value, Mapping) else {}
        for key, value in (bindings or {}).items()
    }
    inputs_in: dict[str, Any] = dict(inputs or {})

    accepted = set(entry.compatibility.accepted_planner_types)
    unknown_types = sorted(set(bindings_in) - accepted)
    if unknown_types:
        accepted_list = (
            ", ".join(sorted(accepted)) if accepted else "(none declared)"
        )
        return asdict(
            _limitation_reply(
                workflow_name,
                f"Unknown binding types: {unknown_types}. Accepted: {accepted_list}.",
                pipeline_family=pipeline_family,
            )
        )

    scalar_params = _scalar_params_for_workflow(workflow_name, bindings_in)
    allowed_scalars = {name for name, _ in scalar_params}
    unknown_scalars = sorted(set(inputs_in) - allowed_scalars)
    if unknown_scalars:
        return asdict(
            _limitation_reply(
                workflow_name,
                f"Unknown scalar inputs: {unknown_scalars}.",
                pipeline_family=pipeline_family,
            )
        )
    missing_required = [
        name
        for name, required in scalar_params
        if required and inputs_in.get(name) in (None, "")
    ]
    if missing_required:
        return asdict(
            _limitation_reply(
                workflow_name,
                f"Missing required inputs: {missing_required}.",
                pipeline_family=pipeline_family,
            )
        )

    if workflow_name == SUPPORTED_WORKFLOW_NAME and not _braker_has_evidence(
        bindings_in, inputs_in
    ):
        return asdict(
            _limitation_reply(
                workflow_name,
                (
                    "BRAKER3 requires at least one evidence input in practice: "
                    "`rnaseq_bam_path`, `protein_fasta_path`, "
                    "`bindings.ReadSet`, or `bindings.ProteinEvidenceSet`."
                ),
                pipeline_family=pipeline_family,
            )
        )

    def _body() -> dict[str, object]:
        try:
            durable_refs = load_durable_asset_index(DEFAULT_RUN_DIR)
        except (OSError, ValueError):
            durable_refs = ()
        explicit_bindings = _materialize_bindings(
            bindings_in,
            durable_index=durable_refs,
        )

        plan = plan_typed_request(
            biological_goal=entry.compatibility.biological_stage or workflow_name,
            target_name=workflow_name,
            source_prompt=source_prompt,
            explicit_bindings=explicit_bindings,
            scalar_inputs=inputs_in,
            resource_request=resource_request,
            execution_profile=execution_profile,
            runtime_images=dict(runtime_images or {}),
            tool_databases=dict(tool_databases or {}),
        )
        if not plan.get("supported"):
            plan.setdefault("target", workflow_name)
            plan.setdefault("pipeline_family", pipeline_family)
            return plan

        artifact = artifact_from_typed_plan(plan, created_at=_created_at())
        artifact_path = save_workflow_spec_artifact(
            artifact,
            _recipe_artifact_destination(workflow_name, recipe_dir=DEFAULT_RECIPE_DIR),
        )

        plan_limitations = tuple(str(item) for item in plan.get("limitations") or ())
        if not source_prompt and _EMPTY_PROMPT_ADVISORY not in plan_limitations:
            plan_limitations = plan_limitations + (_EMPTY_PROMPT_ADVISORY,)

        if dry_run:
            _dry_findings = check_offline_staging(
                artifact.workflow_spec,
                tuple(Path(r) for r in ((resource_request or {}).get("shared_fs_roots") or [])),
                execution_profile=execution_profile if execution_profile == "slurm" else "local",
            )
            return asdict(
                DryRunReply(
                    supported=True,
                    recipe_id=Path(artifact_path).stem,
                    artifact_path=str(artifact_path),
                    execution_profile=(
                        "slurm" if execution_profile == "slurm" else "local"
                    ),
                    resolved_bindings=_resolved_bindings_projection(
                        bindings_in, explicit_bindings
                    ),
                    resolved_environment=dict(plan.get("resolved_environment") or {}),
                    staging_findings=tuple(
                        {"kind": sf.kind, "key": sf.key, "path": sf.path, "reason": sf.reason}
                        for sf in _dry_findings
                    ),
                    limitations=plan_limitations,
                    workflow_name=workflow_name,
                )
            )

        profile_value = (
            "slurm" if execution_profile == "slurm" else "local"
        )
        if profile_value == "slurm":
            _shared_fs = tuple(
                Path(r) for r in ((resource_request or {}).get("shared_fs_roots") or [])
            )
            slurm_result = SlurmWorkflowSpecExecutor(
                run_root=DEFAULT_RUN_DIR,
                repo_root=REPO_ROOT,
            ).submit(Path(artifact_path), shared_fs_roots=_shared_fs)
            run_record_path_str = (
                str(slurm_result.run_record.run_record_path)
                if slurm_result.run_record is not None
                else ""
            )
            if slurm_result.run_record is not None:
                _write_latest_slurm_submission_pointers(
                    DEFAULT_RUN_DIR,
                    artifact_path=Path(artifact_path),
                    run_record_path=slurm_result.run_record.run_record_path,
                )
            combined_limits = (
                plan_limitations
                + tuple(str(item) for item in slurm_result.limitations)
            )
            return asdict(
                RunReply(
                    supported=True,
                    recipe_id=Path(artifact_path).stem,
                    run_record_path=run_record_path_str,
                    artifact_path=str(artifact_path),
                    execution_profile="slurm",
                    execution_status="success" if slurm_result.supported else "failed",
                    exit_status=None,
                    outputs={},
                    limitations=combined_limits,
                    workflow_name=workflow_name,
                )
            )

        local_executor = LocalWorkflowSpecExecutor(
            _local_node_handlers(),
            run_root=DEFAULT_RUN_DIR,
        )
        failure_reason: str | None = None
        try:
            local_result = local_executor.execute(Path(artifact_path))
        except RuntimeError as exc:
            local_result = None  # type: ignore[assignment]
            failure_reason = str(exc)
        run_record_path: Path | None = None
        exit_status: int | None = None
        if local_result is not None and local_result.supported and local_result.node_results:
            candidates = sorted(
                DEFAULT_RUN_DIR.rglob(DEFAULT_LOCAL_RUN_RECORD_FILENAME),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                run_record_path = candidates[0]
            exit_status = 0
        if local_result is None or not local_result.supported:
            exit_status = 1
            execution_status: str = "failed"
            executor_limits: tuple[str, ...]
            if failure_reason is not None:
                executor_limits = (failure_reason,)
            else:
                executor_limits = tuple(
                    str(item) for item in local_result.limitations  # type: ignore[union-attr]
                )
        else:
            execution_status = "success"
            executor_limits = tuple(str(item) for item in local_result.limitations)
        outputs_map, output_limits = _collect_named_outputs(entry, run_record_path)
        combined_limits = plan_limitations + executor_limits + tuple(output_limits)
        return asdict(
            RunReply(
                supported=True,
                recipe_id=Path(artifact_path).stem,
                run_record_path=str(run_record_path) if run_record_path else "",
                artifact_path=str(artifact_path),
                execution_profile="local",
                execution_status=execution_status,  # type: ignore[arg-type]
                exit_status=exit_status,
                outputs=outputs_map,
                limitations=combined_limits,
                workflow_name=workflow_name,
            )
        )

    return _execute_run_tool(_body, target_name=workflow_name, pipeline_family=pipeline_family)


def _jsonable(value: Any) -> Any:
    """Convert paths and nested containers into JSON-compatible values.

    Args:
        value: Arbitrary path, mapping, or sequence values from execution records.
"""
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _first_output_path(execution_result: dict[str, object]) -> str:
    """Return the first output path from an execution payload when present.

    Args:
        execution_result: Serialized execution record containing `output_paths`.
"""
    output_paths = execution_result.get("output_paths", [])
    if isinstance(output_paths, list) and output_paths:
        return str(output_paths[0])
    return ""


def _local_node_handlers(
    *,
    workflow_runner: Any = _execute_workflow_direct,
    task_runner: Any = _execute_task_direct,
) -> dict[str, Any]:
    """Build explicit node handlers for the supported local execution targets.

    Args:
        workflow_runner: Injected workflow execution function used by the adapter.
        task_runner: Injected task execution function used by the adapter.
"""

    def workflow_handler(request: LocalNodeExecutionRequest) -> dict[str, object]:
        """Run one workflow target through the local execution adapter.

        Args:
            request: Local execution request for a registered workflow node.
        """
        execution_result = workflow_runner(
            workflow_name=request.node.reference_name,
            inputs=dict(request.inputs),
        )
        if not execution_result.get("supported", False) or execution_result.get("exit_status") != 0:
            raise RuntimeError(_summary_failure_reason(execution_result) or "Local workflow execution failed.")
        output_name = get_entry(request.node.reference_name).outputs[0].name
        return {
            output_name: _first_output_path(execution_result),
            "execution_result": execution_result,
        }

    def task_handler(request: LocalNodeExecutionRequest) -> dict[str, object]:
        """Run one task target through the local execution adapter.

        Args:
            request: Local execution request for a registered task node.
        """
        execution_result = task_runner(
            task_name=request.node.reference_name,
            inputs=dict(request.inputs),
        )
        if not execution_result.get("supported", False) or execution_result.get("exit_status") != 0:
            raise RuntimeError(_summary_failure_reason(execution_result) or "Local task execution failed.")
        output_name = get_entry(request.node.reference_name).outputs[0].name
        return {
            output_name: _first_output_path(execution_result),
            "execution_result": execution_result,
        }

    return {
        **{name: workflow_handler for name in SUPPORTED_WORKFLOW_NAMES},
        **{name: task_handler for name in SUPPORTED_TASK_NAMES},
    }


def _created_at() -> str:
    """Return a stable UTC timestamp for saved recipe metadata."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _recipe_target_name(typed_plan: dict) -> str:
    """Derive a self-describing target name from a typed plan for the recipe_id.

    Single-entry plans use the matched registry name.  Composition-fallback
    plans use ``composed-<first>_to_<last>`` so the recipe_id encodes the DAG
    boundaries for both filesystem and Slurm accounting.
    """
    matched = typed_plan.get("matched_entry_names") or []
    if typed_plan.get("planning_outcome") == "generated_workflow_spec":
        if len(matched) >= 2:
            return f"composed-{matched[0]}_to_{matched[-1]}"
        if matched:
            return f"composed-{matched[0]}"
        return "composed"
    return str(matched[0]) if matched else "unknown"


def _recipe_artifact_destination(target_name: str, *, recipe_dir: Path | None = None) -> Path:
    """Build a unique path for one frozen recipe artifact.

    Args:
        target_name: Registry entry name or ``composed-*`` sentinel used in the
            recipe_id; see :func:`_recipe_target_name`.
        recipe_dir: Directory that will hold the frozen recipe artifact.
    """
    return (recipe_dir or DEFAULT_RECIPE_DIR) / f"{make_recipe_id(target_name)}.json"


def _limitations_from_typed_plan(plan: dict[str, object]) -> list[str]:
    """Return concise limitations for unsupported typed-plan payloads.

    Args:
        plan: Typed planning result being summarized.
"""
    limitations = plan.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        return [str(item) for item in limitations]
    missing = plan.get("missing_requirements", [])
    if isinstance(missing, list) and missing:
        return [str(item) for item in missing]
    rationale = plan.get("rationale", [])
    if isinstance(rationale, list) and rationale:
        return [str(item) for item in rationale]
    return ["The request is not supported by the current MCP recipe planner."]


def _result_from_local_spec_execution(result: LocalSpecExecutionResult) -> dict[str, object]:
    """Serialize local spec execution into the MCP execution-result shape.

    Args:
        result: Completed local spec execution returned by the recipe executor.
"""
    node_results = [
        {
            "node_name": node.node_name,
            "reference_name": node.reference_name,
            "outputs": _jsonable(dict(node.outputs)),
            "manifest_paths": _jsonable(dict(node.manifest_paths)),
        }
        for node in result.node_results
    ]
    output_paths = [
        str(value)
        for value in result.final_outputs.values()
        if value not in (None, "")
    ]
    entry_name = result.node_results[-1].reference_name if result.node_results else result.workflow_name
    try:
        entry_category = get_entry(entry_name).category
    except KeyError:
        entry_category = "workflow"
    return {
        "supported": result.supported,
        "entry_name": entry_name,
        "entry_category": entry_category,
        "workflow_name": result.workflow_name,
        "execution_mode": "local-workflow-spec-executor",
        "exit_status": 0 if result.supported else 1,
        "stdout": "",
        "stderr": "",
        "output_paths": output_paths,
        "resolved_planner_inputs": _jsonable(dict(result.resolved_planner_inputs)),
        "execution_profile": result.execution_profile,
        "resource_spec": _jsonable(result.resource_spec),
        "runtime_image": _jsonable(result.runtime_image),
        "node_results": node_results,
        "final_outputs": _jsonable(dict(result.final_outputs)),
        "assumptions": list(result.assumptions),
        "limitations": list(result.limitations),
    }


def _result_from_slurm_spec_execution(result: SlurmSpecExecutionResult) -> dict[str, object]:
    """Serialize Slurm submission into the MCP execution-result shape.

    Args:
        result: Completed Slurm submission returned by the recipe executor.
"""
    run_record = result.run_record
    output_paths = []
    if run_record is not None:
        output_paths = [str(run_record.run_record_path), str(run_record.script_path)]
    return {
        "supported": result.supported,
        "entry_name": result.workflow_name,
        "entry_category": "workflow",
        "workflow_name": result.workflow_name,
        "execution_mode": "slurm-workflow-spec-executor",
        "exit_status": 0 if result.supported else 1,
        "stdout": result.scheduler_stdout,
        "stderr": result.scheduler_stderr,
        "output_paths": output_paths,
        "execution_profile": result.execution_profile,
        "resource_spec": _jsonable(result.resource_spec),
        "runtime_image": _jsonable(result.runtime_image),
        "run_record": _jsonable(run_record),
        "script_text": result.script_text,
        "assumptions": list(result.assumptions),
        "limitations": list(result.limitations),
    }


def _result_from_slurm_lifecycle(result: SlurmLifecycleResult) -> dict[str, object]:
    """Serialize Slurm lifecycle operations for MCP clients.

    Args:
        result: Completed Slurm lifecycle action returned by the executor.
"""
    run_record = result.run_record
    snapshot = result.scheduler_snapshot
    return {
        "supported": result.supported,
        "action": result.action,
        "execution_mode": "slurm-lifecycle",
        "run_record": _jsonable(run_record),
        "scheduler_snapshot": _jsonable(snapshot),
        "scheduler_state": run_record.scheduler_state if run_record is not None else None,
        "final_scheduler_state": run_record.final_scheduler_state if run_record is not None else None,
        "job_id": run_record.job_id if run_record is not None else (snapshot.job_id if snapshot is not None else None),
        "stdout_path": str(run_record.stdout_path) if run_record is not None else None,
        "stderr_path": str(run_record.stderr_path) if run_record is not None else None,
        "exit_code": run_record.scheduler_exit_code if run_record is not None else None,
        "limitations": list(result.limitations),
        "assumptions": list(result.assumptions),
    }


def _result_from_slurm_retry(result: SlurmRetryResult) -> dict[str, object]:
    """Serialize Slurm retry operations for MCP clients.

    Args:
        result: Retry outcome returned by the Slurm executor.
"""
    source_run_record = result.source_run_record
    retry_execution = result.retry_execution
    retry_run_record = retry_execution.run_record if retry_execution is not None else None
    return {
        "supported": result.supported,
        "action": result.action,
        "execution_mode": "slurm-retry",
        "source_run_record": _jsonable(source_run_record),
        "failure_classification": _jsonable(result.failure_classification),
        "retry_policy": _jsonable(result.retry_policy),
        "retry_execution": _result_from_slurm_spec_execution(retry_execution) if retry_execution is not None else None,
        "retry_run_record": _jsonable(retry_run_record),
        "job_id": retry_run_record.job_id if retry_run_record is not None else None,
        "run_record_path": str(retry_run_record.run_record_path) if retry_run_record is not None else None,
        "limitations": list(result.limitations),
        "assumptions": list(result.assumptions),
    }


def _prepare_run_recipe_impl(
    prompt: str,
    *,
    manifest_sources: Sequence[str | Path] | None = None,
    explicit_bindings: Mapping[str, Any] | None = None,
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
    recipe_dir: Path | None = None,
) -> dict[str, object]:
    """Plan and freeze one prompt as a local workflow-spec artifact.

    Args:
        prompt: Natural-language prompt being planned or frozen into a recipe.
        manifest_sources: Prior manifests or run records used to seed typed planning.
        explicit_bindings: User-supplied planner inputs that override discovered values.
        runtime_bindings: Frozen runtime bindings captured in the saved recipe.
        resource_request: Explicit CPU, memory, and scheduler choices from the request.
        execution_profile: Named execution target requested for the recipe.
        runtime_image: Runtime image selection for the frozen recipe.
        recipe_dir: Output directory for the frozen recipe artifact.
"""
    recipe_input_context = _recipe_input_context_payload(
        manifest_sources=manifest_sources,
        explicit_bindings=explicit_bindings,
        runtime_bindings=runtime_bindings,
        resource_request=resource_request,
        execution_profile=execution_profile,
        runtime_image=runtime_image,
    )
    normalized_manifest_sources, limitations = _normalize_manifest_sources(manifest_sources)
    if limitations:
        return {
            "supported": False,
            "original_request": prompt,
            "typed_plan": _unsupported_recipe_prep_plan(
                prompt,
                limitations=limitations,
                recipe_input_context=recipe_input_context,
            ),
            "artifact_path": None,
            "recipe_input_context": recipe_input_context,
            "limitations": list(limitations),
        }

    typed_plan = preview_plan_request(
        prompt,
        explicit_bindings=explicit_bindings or {},
        manifest_sources=normalized_manifest_sources,
        runtime_bindings=runtime_bindings or {},
        resource_request=resource_request,
        execution_profile=execution_profile,
        runtime_image=runtime_image,
    )
    if not typed_plan.get("supported", False):
        return {
            "supported": False,
            "original_request": prompt,
            "typed_plan": typed_plan,
            "artifact_path": None,
            "recipe_input_context": recipe_input_context,
            "limitations": _limitations_from_typed_plan(typed_plan),
        }

    # Require user review before saving a recipe built from registered-stage composition.
    if typed_plan.get("requires_user_approval", False):
        return {
            "supported": True,
            "original_request": prompt,
            "typed_plan": typed_plan,
            "artifact_path": None,
            "recipe_input_context": recipe_input_context,
            "requires_explicit_approval": True,
            "approval_message": (
                f"The planner discovered a composed workflow built from registered stages: "
                f"{' -> '.join(typed_plan.get('matched_entry_names', []))}. "
                f"This workflow requires explicit approval before execution can continue. "
                f"Please review the workflow spec and rationale, then approve or reject it."
            ),
            "limitations": [
                "Composed workflows still require explicit user confirmation before execution while Milestone 19 is pending.",
                "The artifact has not been saved. Approval must be obtained before calling run_local_recipe.",
            ],
        }

    created_at = _created_at()
    artifact = artifact_from_typed_plan(
        typed_plan,
        created_at=created_at,
        replay_metadata={"mcp_tool": "prepare_run_recipe"},
    )
    artifact_path = save_workflow_spec_artifact(
        artifact,
        _recipe_artifact_destination(_recipe_target_name(typed_plan), recipe_dir=recipe_dir),
    )
    return {
        "supported": True,
        "original_request": prompt,
        "typed_plan": typed_plan,
        "artifact_path": str(artifact_path),
        "created_at": created_at,
        "recipe_input_context": recipe_input_context,
        "limitations": [],
    }


def prepare_run_recipe(
    prompt: str,
    *,
    manifest_sources: Sequence[str | Path] | None = None,
    explicit_bindings: Mapping[str, Any] | None = None,
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
) -> dict[str, object]:
    """Plan one natural-language prompt and save a frozen workflow-spec recipe.

    This is a secondary power tool for when you want to plan from a prompt
    before submitting. For most cases prefer run_workflow directly — it accepts
    the same inputs and handles planning internally.

    When this tool declines with "use run_workflow directly", call run_workflow
    with workflow_name, bindings, inputs, runtime_images, tool_databases,
    resource_request, execution_profile, and dry_run=True. Pass File-typed
    workflow parameters as absolute string paths in inputs — they are coerced
    automatically. Do not pass Flyte File objects or dicts with a "path" key.

    Args:
        prompt: Natural-language description of the analysis to run.
        explicit_bindings: Typed planner bindings (e.g. ReferenceGenome,
            ReadPair) that override auto-discovered values. Same shape as the
            bindings parameter in run_workflow.
        runtime_bindings: Flat dict of workflow scalar parameter names to
            values. File-typed parameters accepted as absolute string paths.
            Same shape as the inputs parameter in run_workflow.
        resource_request: Slurm scheduler parameters. Valid keys: partition,
            account, cpu, memory, walltime, module_loads, shared_fs_roots.
        execution_profile: "local" or "slurm".
        manifest_sources: Prior manifests or run records to seed planning.
        runtime_image: Runtime image selection for the frozen recipe.
"""
    return _prepare_run_recipe_impl(
        prompt,
        manifest_sources=manifest_sources,
        explicit_bindings=explicit_bindings,
        runtime_bindings=runtime_bindings,
        resource_request=resource_request,
        execution_profile=execution_profile,
        runtime_image=runtime_image,
    )


def _run_local_recipe_impl(
    artifact_path: str | Path,
    *,
    handlers: dict[str, Any] | None = None,
    resume_from_local_record: str | Path | None = None,
) -> dict[str, object]:
    """Execute one frozen workflow-spec recipe through local node handlers.

    Args:
        artifact_path: Frozen recipe artifact to load and execute locally.
        handlers: Optional node-handler overrides used for test doubles.
"""
    # Check approval for composed recipes before execution.
    try:
        artifact = load_workflow_spec_artifact(Path(artifact_path))
        if artifact.binding_plan.target_kind == "generated_workflow":
            approved, reason = check_recipe_approval(Path(artifact_path))
            if not approved:
                return {
                    "supported": False,
                    "artifact_path": str(artifact_path),
                    "execution_result": {
                        "supported": False,
                        "execution_mode": "local-workflow-spec-executor",
                        "exit_status": 1,
                        "stdout": "",
                        "stderr": reason,
                        "output_paths": [],
                        "limitations": [reason],
                    },
                    "limitations": [reason],
                }
    except Exception:
        pass  # Let the executor handle load errors normally.

    try:
        result = LocalWorkflowSpecExecutor(handlers or _local_node_handlers()).execute(
            Path(artifact_path),
            resume_from=Path(resume_from_local_record) if resume_from_local_record is not None else None,
        )
    except Exception as exc:
        execution_supported = isinstance(exc, RuntimeError)
        return {
            "supported": False,
            "artifact_path": str(artifact_path),
            "execution_result": {
                "supported": execution_supported,
                "execution_mode": "local-workflow-spec-executor",
                "exit_status": 1,
                "stdout": "",
                "stderr": str(exc),
                "output_paths": [],
                "limitations": [str(exc)],
                "error_type": type(exc).__name__,
            },
            "limitations": [str(exc)],
        }

    execution_result = _result_from_local_spec_execution(result)
    return {
        "supported": bool(result.supported),
        "artifact_path": str(artifact_path),
        "execution_result": execution_result,
        "limitations": list(result.limitations),
    }


def run_local_recipe(artifact_path: str) -> dict[str, object]:
    """Run a previously frozen workflow-spec recipe artifact."""
    return _run_local_recipe_impl(artifact_path)


def _run_slurm_recipe_impl(
    artifact_path: str | Path,
    *,
    run_dir: Path | None = None,
    sbatch_runner: Any = subprocess.run,
    command_available: Any = None,
    resume_from_local_record: str | Path | None = None,
    shared_fs_roots: list[str] | None = None,
) -> dict[str, object]:
    """Submit one frozen workflow-spec recipe through `sbatch`.

    Args:
        artifact_path: Frozen recipe artifact to submit to Slurm.
        run_dir: Directory that stores the generated run record and logs.
        sbatch_runner: Injected submission command runner used for Slurm submission.
        command_available: Command probe used to confirm Slurm tooling is available.
        resume_from_local_record: Optional path to a prior local run record whose
            completed node state is carried forward into the Slurm submission so
            already-finished stages are not re-executed on the compute node.
        shared_fs_roots: Filesystem prefixes visible to compute nodes. When
            provided, runs check_offline_staging before sbatch to verify
            containers, tool databases, and input paths are reachable from
            compute nodes. Omit to skip staging preflight.
"""
    # Check approval for composed recipes before submission.
    try:
        artifact = load_workflow_spec_artifact(Path(artifact_path))
        if artifact.binding_plan.target_kind == "generated_workflow":
            approved, reason = check_recipe_approval(Path(artifact_path))
            if not approved:
                return {
                    "supported": False,
                    "artifact_path": str(artifact_path),
                    "execution_result": {
                        "supported": False,
                        "execution_mode": "slurm-workflow-spec-executor",
                        "limitations": [reason],
                    },
                    "limitations": [reason],
                }
    except Exception:
        pass  # Let the executor handle load errors normally.

    result = SlurmWorkflowSpecExecutor(
        run_root=run_dir or DEFAULT_RUN_DIR,
        repo_root=REPO_ROOT,
        sbatch_runner=sbatch_runner,
        command_available=command_available or _command_is_available,
    ).submit(
        Path(artifact_path),
        resume_from_local_record=Path(resume_from_local_record) if resume_from_local_record is not None else None,
        shared_fs_roots=tuple(Path(r) for r in (shared_fs_roots or [])),
    )
    active_run_dir = run_dir or DEFAULT_RUN_DIR
    if result.supported and result.run_record is not None:
        _write_latest_slurm_submission_pointers(
            active_run_dir,
            artifact_path=Path(artifact_path),
            run_record_path=result.run_record.run_record_path,
        )
    execution_result = _result_from_slurm_spec_execution(result)
    return {
        "supported": bool(result.supported),
        "artifact_path": str(artifact_path),
        "execution_result": execution_result,
        "run_record_path": str(result.run_record.run_record_path) if result.run_record is not None else None,
        "job_id": result.run_record.job_id if result.run_record is not None else None,
        "limitations": list(result.limitations),
    }


def run_slurm_recipe(
    artifact_path: str,
    shared_fs_roots: list[str] | None = None,
) -> dict[str, object]:
    """Submit a previously frozen workflow-spec recipe artifact to Slurm.

    Args:
        artifact_path: Path to the frozen recipe artifact to submit.
        shared_fs_roots: Filesystem prefixes visible to compute nodes. When
            provided, runs check_offline_staging before sbatch to verify
            containers, tool databases, and input paths are reachable from
            compute nodes. Omit to skip staging preflight.
    """
    return _run_slurm_recipe_impl(artifact_path, shared_fs_roots=shared_fs_roots)


def validate_run_recipe(
    artifact_path: str,
    execution_profile: str = "local",
    shared_fs_roots: list[str] | None = None,
) -> dict[str, object]:
    """Validate a frozen recipe without executing it.

    Runs the same preflight checks a real execution would: inputs resolve
    through the manifest + durable asset index, containers and tool databases
    exist, and (for slurm) every staged path sits on a compute-visible root.
    Safe to call repeatedly — never submits, never writes, never mutates.

    Args:
        artifact_path: Path to the frozen ``WorkflowSpec`` artifact to validate.
        execution_profile: ``"local"`` or ``"slurm"``.  Determines whether
            shared-FS membership is enforced on staged paths.
        shared_fs_roots: Filesystem prefixes visible to compute nodes (Slurm
            only).  When ``None`` (default), the shared-FS check is skipped.
            When an explicit empty list is provided with ``execution_profile=
            "slurm"``, every staged path that exists locally is flagged as
            ``not_on_shared_fs`` — no false negatives.

    Returns:
        ``asdict(ValidateRecipeReply)`` with ``supported``, ``recipe_id``,
        ``execution_profile``, and ``findings`` (list of finding dicts each
        with ``kind``, ``key``, optional ``path``, and ``reason``).
    """
    artifact = load_workflow_spec_artifact(Path(artifact_path))
    try:
        durable_refs = load_durable_asset_index(DEFAULT_RUN_DIR)
    except (OSError, ValueError):
        durable_refs = ()

    findings: list[dict[str, str]] = []

    # Re-validate each explicit binding to catch paths that have disappeared
    # or $ref bindings that can no longer be satisfied.
    for key, value in artifact.binding_plan.explicit_user_bindings.items():
        if not isinstance(value, Mapping):
            continue
        try:
            _materialize_bindings({key: value}, durable_index=durable_refs)
        except Exception as exc:
            findings.append({"kind": "binding", "key": key, "reason": str(exc)})

    roots = tuple(Path(r) for r in (shared_fs_roots or []))

    if execution_profile == "slurm" and shared_fs_roots is not None and not roots:
        # No shared roots declared for slurm profile: conservatively flag
        # every existing staged path as not_on_shared_fs — no false negatives.
        ws = artifact.workflow_spec
        for attr, kind in (("runtime_images", "container"), ("tool_databases", "tool_database")):
            for key, path in (getattr(ws, attr, {}) or {}).items():
                p = Path(path)
                if p.exists():
                    findings.append({"kind": kind, "key": key, "path": path, "reason": "not_on_shared_fs"})
                else:
                    try:
                        p.lstat()
                        reason = "not_readable"
                    except OSError:
                        reason = "not_found"
                    findings.append({"kind": kind, "key": key, "path": path, "reason": reason})
    else:
        for sf in check_offline_staging(
            artifact.workflow_spec,
            roots,
            execution_profile=execution_profile,
        ):
            findings.append({
                "kind": sf.kind,
                "key": sf.key,
                "path": sf.path,
                "reason": sf.reason,
                "message": format_finding(sf),
            })

    recipe_id = Path(artifact_path).stem
    return asdict(ValidateRecipeReply(
        supported=not findings,
        recipe_id=recipe_id,
        execution_profile=execution_profile,
        findings=tuple(findings),
    ))


# ---------------------------------------------------------------------------
# Slurm log-tail helper
# ---------------------------------------------------------------------------

MAX_MONITOR_TAIL_LINES: int = 500
"""Hard cap on lines returned from scheduler log tails to avoid OOM reads."""


def _read_text_tail(
    path: Path | None,
    *,
    tail_lines: int,
    allowed_root: Path,
) -> str | None:
    """Read a bounded tail from a scheduler log under the run directory.

    The path is resolved and validated against *allowed_root* before any
    file I/O, so a tampered run-record pointing ``stdout_path`` outside the
    run directory cannot read arbitrary files on the host.  The file is read
    using a :class:`collections.deque` with a bounded ``maxlen`` so the whole
    file is never loaded into memory regardless of file size.

    Args:
        path: Absolute path to the scheduler log file, or ``None`` to skip.
        tail_lines: Number of lines to return from the end of the file.
            Must be >= 0.  Clamped to ``MAX_MONITOR_TAIL_LINES``.
        allowed_root: Directory that the resolved *path* must be relative to.
            Returns ``None`` for any path that resolves outside this root.

    Returns:
        The last ``tail_lines`` lines joined into a single string, or
        ``None`` when the file is absent, unreadable, or outside
        *allowed_root*.  Returns ``None`` when *tail_lines* is 0.

    Raises:
        ValueError: If *tail_lines* is negative.
    """
    if tail_lines < 0:
        raise ValueError(f"tail_lines must be >= 0, got {tail_lines}")
    if path is None or tail_lines == 0:
        return None

    line_count = min(tail_lines, MAX_MONITOR_TAIL_LINES)
    try:
        resolved_path = path.resolve()
        resolved_root = allowed_root.resolve()
        if not resolved_path.is_relative_to(resolved_root) or not resolved_path.is_file():
            return None
        with resolved_path.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(deque(handle, maxlen=line_count)).rstrip("\n") or None
    except OSError:
        return None


def _monitor_slurm_job_impl(
    run_record_path: str | Path,
    *,
    run_dir: Path | None = None,
    scheduler_runner: Any = subprocess.run,
    command_available: Any = None,
    tail_lines: int = 50,
) -> dict[str, object]:
    """Reconcile one Slurm job from its durable run record.

    Args:
        run_record_path: Path to the durable Slurm run record created at submission.
        run_dir: Directory that stores run records and scheduler logs.
        scheduler_runner: Injected scheduler command runner used for status and cancellation.
        command_available: Command probe used to confirm scheduler tooling is available.
        tail_lines: Maximum number of lines to read from the scheduler stdout
            and stderr logs when the job has reached a terminal state.  Set to
            0 to disable log reading.  Clamped to ``MAX_MONITOR_TAIL_LINES``.
"""
    result = SlurmWorkflowSpecExecutor(
        run_root=run_dir or DEFAULT_RUN_DIR,
        repo_root=REPO_ROOT,
        scheduler_runner=scheduler_runner,
        command_available=command_available or _command_is_available,
    ).reconcile(Path(run_record_path))
    lifecycle = _result_from_slurm_lifecycle(result)
    record = result.run_record
    if record is not None and record.final_scheduler_state is not None:
        log_root = record.run_record_path.parent
        lifecycle["stdout_tail"] = _read_text_tail(
            record.stdout_path, tail_lines=tail_lines, allowed_root=log_root
        )
        lifecycle["stderr_tail"] = _read_text_tail(
            record.stderr_path, tail_lines=tail_lines, allowed_root=log_root
        )
    else:
        lifecycle["stdout_tail"] = None
        lifecycle["stderr_tail"] = None
    return {
        "supported": bool(result.supported),
        "run_record_path": str(run_record_path),
        "scheduler_state": lifecycle.get("scheduler_state"),
        "final_scheduler_state": lifecycle.get("final_scheduler_state"),
        "stdout_path": lifecycle.get("stdout_path"),
        "stderr_path": lifecycle.get("stderr_path"),
        "lifecycle_result": lifecycle,
        "limitations": list(result.limitations),
    }


def monitor_slurm_job(run_record_path: str, tail_lines: int = 50) -> dict[str, object]:
    """Inspect and reconcile a submitted Slurm job from its run record.

    Args:
        run_record_path: Path to the durable Slurm run record.
        tail_lines: Lines of scheduler stdout/stderr to include in the
            response when the job has reached a terminal state.  Set to 0
            to omit log tails.  Capped at ``MAX_MONITOR_TAIL_LINES`` (500).
    """
    return _monitor_slurm_job_impl(run_record_path, tail_lines=tail_lines)


def _cancel_slurm_job_impl(
    run_record_path: str | Path,
    *,
    run_dir: Path | None = None,
    scheduler_runner: Any = subprocess.run,
    command_available: Any = None,
) -> dict[str, object]:
    """Cancel one Slurm job from its durable run record.

    Args:
        run_record_path: Path to the durable Slurm run record created at submission.
        run_dir: Directory that stores run records and scheduler logs.
        scheduler_runner: Injected scheduler command runner used for status and cancellation.
        command_available: Command probe used to confirm scheduler tooling is available.
"""
    result = SlurmWorkflowSpecExecutor(
        run_root=run_dir or DEFAULT_RUN_DIR,
        repo_root=REPO_ROOT,
        scheduler_runner=scheduler_runner,
        command_available=command_available or _command_is_available,
    ).cancel(Path(run_record_path))
    lifecycle = _result_from_slurm_lifecycle(result)
    limitations = list(result.limitations) + list(result.assumptions)
    return {
        "supported": bool(result.supported),
        "run_record_path": str(run_record_path),
        "scheduler_state": lifecycle.get("scheduler_state"),
        "lifecycle_result": lifecycle,
        "limitations": limitations,
    }


def cancel_slurm_job(run_record_path: str) -> dict[str, object]:
    """Request cancellation for a submitted Slurm job from its run record."""
    return _cancel_slurm_job_impl(run_record_path)


def _retry_slurm_job_impl(
    run_record_path: str | Path,
    *,
    run_dir: Path | None = None,
    sbatch_runner: Any = subprocess.run,
    scheduler_runner: Any = subprocess.run,
    command_available: Any = None,
    resource_overrides: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Retry one failed Slurm job from its durable run record.

    Args:
        run_record_path: Path to the durable Slurm run record that captures the failure.
        run_dir: Directory that stores run records and scheduler logs.
        sbatch_runner: Injected submission command runner used for Slurm submission.
        scheduler_runner: Injected scheduler command runner used for status and cancellation.
        command_available: Command probe used to confirm scheduler tooling is available.
        resource_overrides: Optional resource escalation values for
            ``resource_exhaustion`` retries.  Valid keys are ``cpu``,
            ``memory``, ``walltime``, ``partition``, ``account``, and ``gpu``.
"""
    result = SlurmWorkflowSpecExecutor(
        run_root=run_dir or DEFAULT_RUN_DIR,
        repo_root=REPO_ROOT,
        sbatch_runner=sbatch_runner,
        scheduler_runner=scheduler_runner,
        command_available=command_available or _command_is_available,
    ).retry(Path(run_record_path), resource_overrides=resource_overrides)
    retry_run_record = result.retry_execution.run_record if result.retry_execution is not None else None
    return {
        "supported": bool(result.supported),
        "run_record_path": str(run_record_path),
        "retry_run_record_path": str(retry_run_record.run_record_path) if retry_run_record is not None else None,
        "job_id": retry_run_record.job_id if retry_run_record is not None else None,
        "retry_result": _result_from_slurm_retry(result),
        "limitations": list(result.limitations),
    }


def retry_slurm_job(
    run_record_path: str,
    resource_overrides: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Retry a failed Slurm job from its durable run record.

    For ``resource_exhaustion`` failures (``OUT_OF_MEMORY`` and ``TIMEOUT``)
    you can supply *resource_overrides* to escalate resources without
    preparing a new recipe.  Valid keys are ``cpu``, ``memory``,
    ``walltime``, ``partition``, ``account``, and ``gpu``.  ``DEADLINE``
    failures require a new ``prepare_run_recipe`` call with an updated
    ``walltime``.

    Args:
        run_record_path: Path to the durable Slurm run record.
        resource_overrides: Optional resource escalation values.
    """
    return _retry_slurm_job_impl(run_record_path, resource_overrides=resource_overrides)


def approve_composed_recipe(
    artifact_path: str,
    *,
    approved_by: str = "mcp_client",
    expires_at: str | None = None,
    reason: str = "",
) -> dict[str, object]:
    """Grant or record explicit approval for a composed-recipe artifact.

    Composed recipes cannot be executed by ``run_local_recipe`` or
    ``run_slurm_recipe`` until a valid approval record exists alongside the
    artifact.  This tool writes that record.

    Args:
        artifact_path: Path to the frozen workflow-spec artifact that needs approval.
        approved_by: Human-readable identifier for the approving party.
        expires_at: Optional ISO-8601 timestamp after which approval is no longer valid.
        reason: Optional human-readable note about why approval was granted.

    Returns:
        A JSON-compatible payload with the approval outcome.
    """
    from datetime import datetime, UTC

    path = Path(artifact_path)
    if not path.exists():
        return {
            "supported": False,
            "artifact_path": artifact_path,
            "approved": False,
            "limitations": [f"Artifact not found: {artifact_path}"],
        }

    try:
        artifact = load_workflow_spec_artifact(path)
    except (ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
        return {
            "supported": False,
            "artifact_path": artifact_path,
            "approved": False,
            "limitations": [f"Could not load artifact: {exc}"],
        }

    approved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = RecipeApprovalRecord(
        schema_version=RECIPE_APPROVAL_SCHEMA_VERSION,
        artifact_path=str(path),
        workflow_name=artifact.workflow_spec.name,
        approved=True,
        approved_at=approved_at,
        approved_by=approved_by,
        expires_at=expires_at,
        reason=reason,
    )
    approval_path = save_recipe_approval(record, path)
    return {
        "supported": True,
        "artifact_path": artifact_path,
        "approved": True,
        "approval_path": str(approval_path),
        "approved_at": approved_at,
        "approved_by": approved_by,
        "expires_at": expires_at,
    }


def _supported_target_names() -> list[str]:
    """Return the registered target names exposed through MCP."""
    return list(SUPPORTED_TARGET_NAMES)


def _summary_used_inputs(plan: dict[str, object]) -> dict[str, object]:
    """Return the prompt-derived or frozen runtime inputs used for execution.

    Args:
        plan: Typed planning result being summarized.
"""
    extracted_inputs = plan.get("extracted_inputs", {})
    if not isinstance(extracted_inputs, dict):
        extracted_inputs = {}
    if extracted_inputs:
        return {name: value for name, value in extracted_inputs.items() if value not in (None, "")}

    resolved_inputs = plan.get("resolved_inputs", {})
    if isinstance(resolved_inputs, dict) and "QualityAssessmentTarget" in resolved_inputs:
        # The planner target is a high-level quality-assessment bundle rather
        # than a raw path. Translate it back to the concrete stage input so the
        # MCP summary shows the real runtime dependency.
        target_value = resolved_inputs.get("QualityAssessmentTarget")
        if isinstance(target_value, dict):
            matched_entry_names = plan.get("matched_entry_names", [])
            target_name = matched_entry_names[0] if isinstance(matched_entry_names, list) and matched_entry_names else None
            input_name = {
                "annotation_qc_busco": "repeat_filter_results",
                "annotation_functional_eggnog": "repeat_filter_results",
                "annotation_postprocess_agat": "eggnog_results",
                "annotation_postprocess_agat_conversion": "eggnog_results",
                "annotation_postprocess_agat_cleanup": "agat_conversion_results",
                "annotation_postprocess_table2asn": "agat_cleanup_results",
            }.get(str(target_name), "repeat_filter_results")
            source_dir = target_value.get("source_result_dir")
            if not source_dir and isinstance(target_value.get("source_manifest_path"), str):
                source_dir = str(Path(target_value["source_manifest_path"]).parent)
            if isinstance(source_dir, str) and source_dir:
                context_inputs = {input_name: source_dir}
                runtime_bindings = plan.get("binding_plan", {})
                if isinstance(runtime_bindings, dict):
                    runtime_values = runtime_bindings.get("runtime_bindings", {})
                    if isinstance(runtime_values, dict):
                        context_inputs.update(
                            {name: value for name, value in runtime_values.items() if value not in (None, "")}
                        )
                return context_inputs

    binding_plan = plan.get("binding_plan", {})
    if isinstance(binding_plan, dict):
        runtime_bindings = binding_plan.get("runtime_bindings", {})
        if isinstance(runtime_bindings, dict):
            return {name: value for name, value in runtime_bindings.items() if value not in (None, "")}
    return {}


def _summary_failure_reason(execution_result: dict[str, object] | None) -> str | None:
    """Extract one short failure reason from an execution payload when present.

    Args:
        execution_result: Serialized execution result containing stderr, stdout, or limitations.
"""
    if not execution_result:
        return None
    for key in ("stderr", "stdout"):
        value = execution_result.get(key)
        if not isinstance(value, str):
            continue
        for line in value.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:200]
    limitations = execution_result.get("limitations", [])
    if isinstance(limitations, list):
        for limitation in limitations:
            if isinstance(limitation, str) and limitation:
                return limitation
    return None


def _summary_message(
    status: str,
    target_name: str | None,
    target_category: str | None,
    used_inputs: dict[str, object],
    execution_result: dict[str, object] | None,
    decline_reason: str | None,
    declined_stages: list[str],
) -> str:
    """Build one short client-facing sentence for the prompt-and-run result.

    Args:
        status: Final prompt-and-run outcome to describe.
        target_name: Registered target name selected by the planner, when any.
        target_category: Target category used in the client-facing sentence.
        used_inputs: Prompt-derived inputs that materially affected execution.
        execution_result: Serialized execution result used to extract the failure reason.
        decline_reason: Human-readable reason for a declined request.
        declined_stages: Downstream stages intentionally omitted from the response.
"""
    if status == "declined":
        if decline_reason and "missing explicit required inputs" in decline_reason.lower():
            return (
                f"Declined `{target_name}` because the prompt omitted explicit inputs "
                f"needed to prepare this recipe: {', '.join(used_inputs) or 'required inputs'}."
            )
        if target_name and decline_reason:
            return f"Declined `{target_name}` because {decline_reason.rstrip('.')}."
        if decline_reason:
            return f"Declined the request because {decline_reason.rstrip('.')}."
        return "Declined the request because it falls outside the current MCP recipe surface."

    input_names = list(used_inputs)
    if input_names:
        input_text = ", ".join(f"`{name}`" for name in input_names)
        input_phrase = f" with explicit prompt inputs {input_text}"
    else:
        input_phrase = ""

    exit_status = execution_result.get("exit_status") if execution_result else None
    if status == "succeeded":
        return (
            f"Ran {target_category} `{target_name}`{input_phrase}; "
            f"execution succeeded with exit status {exit_status}."
        )

    failure_reason = _summary_failure_reason(execution_result)
    if failure_reason:
        return (
            f"Attempted {target_category} `{target_name}`{input_phrase}, "
            f"but execution failed with exit status {exit_status}: {failure_reason}"
        )
    return (
        f"Attempted {target_category} `{target_name}`{input_phrase}, "
        f"but execution failed with exit status {exit_status}."
    )


def _summary_codes(
    plan: dict[str, object],
    execution_result: dict[str, object] | None,
) -> tuple[str, str]:
    """Return stable machine-readable result and reason codes for one run.

    Args:
        plan: Typed planning result being summarized.
        execution_result: Serialized execution result used to distinguish success from failure.
"""
    missing_inputs = plan.get("missing_required_inputs", [])
    if isinstance(missing_inputs, list) and missing_inputs:
        return RESULT_CODE_DECLINED_MISSING_INPUTS, REASON_CODE_MISSING_REQUIRED_INPUTS

    if not plan.get("supported", False):
        missing_requirements = plan.get("missing_requirements", [])
        candidate_outcome = plan.get("candidate_outcome")
        if isinstance(missing_requirements, list) and missing_requirements and candidate_outcome:
            return RESULT_CODE_DECLINED_MISSING_INPUTS, REASON_CODE_MISSING_REQUIRED_INPUTS
        return RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST, REASON_CODE_UNSUPPORTED_OR_AMBIGUOUS_REQUEST

    if execution_result and execution_result.get("supported", False) and execution_result.get("exit_status") == 0:
        return RESULT_CODE_SUCCEEDED, REASON_CODE_COMPLETED

    if execution_result and not execution_result.get("supported", False):
        return RESULT_CODE_FAILED_EXECUTION, REASON_CODE_UNSUPPORTED_EXECUTION_TARGET

    return RESULT_CODE_FAILED_EXECUTION, REASON_CODE_NONZERO_EXIT_STATUS


def _build_result_summary(
    plan: dict[str, object],
    execution_attempted: bool,
    execution_result: dict[str, object] | None,
) -> dict[str, object]:
    """Build the compact prompt-and-run summary for MCP client presentation.

    Args:
        plan: Typed planning result being summarized.
        execution_attempted: Whether the server tried to run the selected target.
        execution_result: Serialized execution result used to build the outcome summary.
"""
    target_name = plan.get("matched_entry_name")
    target_category = plan.get("matched_entry_category")
    if not isinstance(target_name, str):
        matched_entry_names = plan.get("matched_entry_names", [])
        if isinstance(matched_entry_names, list) and matched_entry_names:
            target_name = str(matched_entry_names[0])
            target_category = get_entry(target_name).category
    used_inputs = _summary_used_inputs(plan)
    output_paths = execution_result.get("output_paths", []) if execution_result else []
    decline_reason = None
    result_code, reason_code = _summary_codes(plan, execution_result)

    if not plan.get("supported", False):
        status = "declined"
        limitations = plan.get("limitations", [])
        if isinstance(limitations, list) and limitations:
            decline_reason = str(limitations[0])
        else:
            missing_requirements = plan.get("missing_requirements", [])
            if isinstance(missing_requirements, list) and missing_requirements:
                decline_reason = str(missing_requirements[0])
        exit_status = None
    else:
        exit_status = execution_result.get("exit_status") if execution_result else None
        if execution_result and execution_result.get("supported", False) and exit_status == 0:
            status = "succeeded"
        else:
            status = "failed"

    return {
        "status": status,
        "result_code": result_code,
        "reason_code": reason_code,
        "target_name": target_name,
        "target_category": target_category,
        "execution_profile": plan.get("execution_profile"),
        "resource_spec": _jsonable(plan.get("resource_spec")),
        "runtime_image": _jsonable(plan.get("runtime_image")),
        "execution_attempted": execution_attempted,
        "used_inputs": used_inputs,
        "output_paths": output_paths if isinstance(output_paths, list) else [],
        "exit_status": exit_status,
        "decline_reason": decline_reason,
        "supported_targets": _supported_target_names(),
        "typed_planning_available": bool(
            plan.get("workflow_spec")
            or (isinstance(plan.get("typed_planning"), dict) and plan["typed_planning"].get("workflow_spec"))
        ),
        "message": _summary_message(
            status=status,
            target_name=target_name if isinstance(target_name, str) else None,
            target_category=target_category if isinstance(target_category, str) else None,
            used_inputs=used_inputs,
            execution_result=execution_result,
            decline_reason=decline_reason,
            declined_stages=[],
        ),
    }


def _prompt_and_run_impl(
    prompt: str,
    workflow_runner: Any = run_workflow,
    task_runner: Any = run_task,
    *,
    manifest_sources: Sequence[str | Path] | None = None,
    explicit_bindings: Mapping[str, Any] | None = None,
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
    recipe_dir: Path | None = None,
) -> dict[str, object]:
    """Prepare a frozen recipe and execute it through the local spec executor.

    Args:
        prompt: Natural-language prompt being planned or frozen into a recipe.
        workflow_runner: Workflow execution function injected for tests or local execution.
        task_runner: Task execution function injected for tests or local execution.
        manifest_sources: Prior manifests or run records used to seed typed planning.
        explicit_bindings: User-supplied planner inputs that override discovered values.
        runtime_bindings: Frozen runtime bindings captured in the saved recipe.
        resource_request: Explicit CPU, memory, and scheduler choices from the request.
        execution_profile: Named execution target requested for the recipe.
        runtime_image: Runtime image selection for the frozen recipe.
        recipe_dir: Output directory for the frozen recipe artifact.
"""
    recipe = _prepare_run_recipe_impl(
        prompt,
        manifest_sources=manifest_sources,
        explicit_bindings=explicit_bindings,
        runtime_bindings=runtime_bindings,
        resource_request=resource_request,
        execution_profile=execution_profile,
        runtime_image=runtime_image,
        recipe_dir=recipe_dir,
    )
    plan = recipe["typed_plan"]
    if not recipe["supported"]:
        result_summary = _build_result_summary(
            plan=plan,
            execution_attempted=False,
            execution_result=None,
        )
        result_summary["artifact_path"] = None
        return {
            "supported": False,
            "original_request": prompt,
            "plan": plan,
            "execution_attempted": False,
            "execution_result": None,
            "typed_planning": plan,
            "artifact_path": None,
            "result_summary": result_summary,
            "limitations": list(recipe["limitations"]),
        }

    artifact_path = str(recipe["artifact_path"])
    run_result = _run_local_recipe_impl(
        artifact_path,
        handlers=_local_node_handlers(workflow_runner=workflow_runner, task_runner=task_runner),
    )
    execution_result = dict(run_result["execution_result"])
    result_summary = _build_result_summary(
        plan=plan,
        execution_attempted=True,
        execution_result=execution_result,
    )
    result_summary["artifact_path"] = artifact_path

    return {
        "supported": bool(
            recipe["supported"]
            and execution_result["supported"]
            and execution_result.get("exit_status") == 0
        ),
        "original_request": prompt,
        "plan": plan,
        "execution_attempted": True,
        "execution_result": execution_result,
        "typed_planning": plan,
        "artifact_path": artifact_path,
        "result_summary": result_summary,
        "limitations": list(dict.fromkeys([*recipe["limitations"], *execution_result.get("limitations", [])])),
    }


def prompt_and_run(
    prompt: str,
    *,
    manifest_sources: Sequence[str | Path] | None = None,
    explicit_bindings: Mapping[str, Any] | None = None,
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
) -> dict[str, object]:
    """Plan one prompt and run it through the recipe-backed execution flow.

    Args:
        prompt: Natural-language prompt being planned or frozen into a recipe.
        manifest_sources: Prior manifests or run records used to seed typed planning.
        explicit_bindings: User-supplied planner inputs that override discovered values.
        runtime_bindings: Frozen runtime bindings captured in the saved recipe.
        resource_request: Explicit CPU, memory, and scheduler choices from the request.
        execution_profile: Named execution target requested for the recipe.
        runtime_image: Runtime image selection for the frozen recipe.
"""
    return _prompt_and_run_impl(
        prompt,
        manifest_sources=manifest_sources,
        explicit_bindings=explicit_bindings,
        runtime_bindings=runtime_bindings,
        resource_request=resource_request,
        execution_profile=execution_profile,
        runtime_image=runtime_image,
    )


# ---------------------------------------------------------------------------
# Phase 2 — Binding discovery (TODO 16)
# ---------------------------------------------------------------------------

# Mapping from parameter name suffix patterns to the file extensions that
# indicate a file binding candidate for that parameter.
_FASTA_EXTENSIONS = ("*.fasta", "*.fa", "*.fna", "*.faa")
_GFF_EXTENSIONS = ("*.gff3", "*.gff")
_FASTQ_EXTENSIONS = ("*.fastq.gz", "*.fq.gz", "*.fastq", "*.fq")

_PARAM_EXTENSION_MAP: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    # (name_suffixes, file_extensions)
    (("_fasta", "_fa", "genome_fasta", "proteins_fasta", "genome"), _FASTA_EXTENSIONS),
    (("_gff3", "gff3", "annotation_gff3"), _GFF_EXTENSIONS),
    (("_bam",), ("*.bam",)),
    (("_sif",), ("*.sif",)),
    (("left", "right"), _FASTQ_EXTENSIONS),
    (("_dir", "_results"), ()),  # Dir params — special handling below
)

_SCALAR_HINT_TYPES = {
    "str": "provide a string value",
    "int": "provide an integer",
    "float": "provide a float",
    "bool": "provide true or false",
}


def _scan_name_variants(name: str) -> tuple[str, ...]:
    """Return the semantic name variants used for binding discovery scans."""
    variants = [name]
    if name.endswith("_path"):
        stripped = name.removesuffix("_path")
        if stripped:
            variants.append(stripped)
    return tuple(dict.fromkeys(variants))


def _matches_scan_suffix(candidate_name: str, suffix: str) -> bool:
    """Return whether one semantic name matches one scan suffix rule."""
    normalized = suffix.lstrip("_")
    return (
        candidate_name == normalized
        or candidate_name.endswith(suffix)
        or candidate_name.endswith(normalized)
        or candidate_name.startswith(f"{normalized}_")
    )


def _scan_patterns_for_name(name: str) -> tuple[str, ...]:
    """Return file-scan patterns for one parameter or planner Path field name."""
    for candidate_name in _scan_name_variants(name):
        for suffixes, exts in _PARAM_EXTENSION_MAP:
            if any(_matches_scan_suffix(candidate_name, suffix) for suffix in suffixes):
                return exts
    return ()


def _looks_like_run_dir_name(name: str) -> bool:
    """Return whether one semantic name should scan for manifest-bearing run dirs."""
    return any(candidate_name.endswith(("_dir", "_results")) for candidate_name in _scan_name_variants(name))


def _is_path_annotation(annotation: Any) -> bool:
    """Return whether one type annotation is Path or Optional[Path]."""
    if annotation is Path:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    return len(args) == 1 and args[0] is Path


def _path_fields_for(planner_type: type[Any]) -> tuple[str, ...]:
    """Return the Path-bearing field names declared on one planner dataclass."""
    return tuple(
        field_name
        for field_name, annotation in get_type_hints(planner_type).items()
        if _is_path_annotation(annotation)
    )


def _typed_binding_candidates(entry: RegistryEntry, root: Path) -> dict[str, dict[str, list[str]]]:
    """Return typed binding candidates grouped by accepted planner type."""
    typed_bindings: dict[str, dict[str, list[str]]] = {}
    for planner_type_name in entry.compatibility.accepted_planner_types:
        planner_type = getattr(planner_types_module, planner_type_name, None)
        field_candidates: dict[str, list[str]] = {}
        if planner_type is not None:
            for field_name in _path_fields_for(planner_type):
                scan_patterns = _scan_patterns_for_name(field_name)
                if scan_patterns:
                    field_candidates[field_name] = _scan_for_files(root, scan_patterns)
                elif _looks_like_run_dir_name(field_name):
                    field_candidates[field_name] = _scan_for_run_dirs(root)
                else:
                    field_candidates[field_name] = []
        typed_bindings[planner_type_name] = field_candidates
    return typed_bindings


def _task_parameter_scan_patterns(task_name: str) -> dict[str, tuple[str, ...]]:
    """Return per-parameter scan extension lists for one supported task.

    The returned mapping keys are parameter names; values are tuples of glob
    patterns to scan for, or an empty tuple when the parameter is scalar-only.

    Args:
        task_name: A supported task name from ``SUPPORTED_TASK_NAMES``.
"""
    parameters = TASK_PARAMETERS.get(task_name, ())
    result: dict[str, tuple[str, ...]] = {}
    for param_name, required in parameters:
        result[param_name] = _scan_patterns_for_name(param_name)
    return result


def _scan_for_files(
    root: Path,
    patterns: tuple[str, ...],
    *,
    max_depth: int = 3,
) -> list[str]:
    """Recursively scan *root* for files matching any of *patterns* up to *max_depth*.

    Args:
        root: Directory to scan.
        patterns: Glob patterns to match against file names (e.g. ``"*.fasta"``).
        max_depth: Maximum directory depth relative to *root*.
"""
    found: list[str] = []
    if not root.is_dir():
        return found
    _scan_dir_for_files(root, root, patterns, max_depth=max_depth, current_depth=0, found=found)
    return found


def _scan_dir_for_files(
    base: Path,
    current: Path,
    patterns: tuple[str, ...],
    *,
    max_depth: int,
    current_depth: int,
    found: list[str],
) -> None:
    """Recursive helper for :func:`_scan_for_files`.

    Args:
        base: Top-level search root used for relative path computation.
        current: Directory currently being scanned.
        patterns: Glob patterns matched against each file.
        max_depth: Maximum traversal depth from *base*.
        current_depth: Depth of *current* relative to *base*.
        found: List accumulator for matched file paths.
"""
    try:
        entries = list(current.iterdir())
    except PermissionError:
        return
    for entry in entries:
        if entry.is_file():
            for pattern in patterns:
                if entry.match(pattern):
                    found.append(str(entry))
                    break
        elif entry.is_dir() and current_depth < max_depth:
            _scan_dir_for_files(
                base, entry, patterns, max_depth=max_depth, current_depth=current_depth + 1, found=found
            )


def _scan_for_run_dirs(root: Path, *, max_depth: int = 3) -> list[str]:
    """Return subdirectories under *root* that contain a ``run_manifest.json``.

    Args:
        root: Directory to scan for result bundles.
        max_depth: Maximum traversal depth.
"""
    found: list[str] = []
    _scan_for_run_dirs_impl(root, max_depth=max_depth, current_depth=0, found=found)
    return found


def _scan_for_run_dirs_impl(
    current: Path,
    *,
    max_depth: int,
    current_depth: int,
    found: list[str],
) -> None:
    """Recursive helper for :func:`_scan_for_run_dirs`.

    Args:
        current: Directory currently being scanned.
        max_depth: Maximum traversal depth.
        current_depth: Depth of *current* relative to the search root.
        found: List accumulator for matching directory paths.
"""
    if not current.is_dir():
        return
    if (current / "run_manifest.json").is_file():
        found.append(str(current))
        return  # don't descend further into result dirs
    if current_depth >= max_depth:
        return
    try:
        entries = list(current.iterdir())
    except PermissionError:
        return
    for entry in entries:
        if entry.is_dir():
            _scan_for_run_dirs_impl(entry, max_depth=max_depth, current_depth=current_depth + 1, found=found)


def _list_available_bindings_impl(
    task_name: str,
    search_root: str | None = None,
) -> dict[str, object]:
    """Scan *search_root* for files that could satisfy each parameter of *task_name*.

    Args:
        task_name: Supported task whose parameters should be bound.
        search_root: Root directory to scan (defaults to ``Path.cwd()``).
"""
    if task_name not in set(SUPPORTED_TASK_NAMES):
        return {
            "supported": False,
            "task_name": task_name,
            "bindings": {},
            "typed_bindings": {},
            "limitations": [
                "Only "
                + ", ".join(f"`{n}`" for n in SUPPORTED_TASK_NAMES)
                + " are supported for binding discovery."
            ],
        }

    root = Path(search_root) if search_root else Path.cwd()
    entry = get_entry(task_name)
    scan_patterns = _task_parameter_scan_patterns(task_name)
    bindings: dict[str, object] = {}
    for param_name, exts in scan_patterns.items():
        if not exts:
            # Scalar or Dir param
            if _looks_like_run_dir_name(param_name):
                bindings[param_name] = _scan_for_run_dirs(root)
            else:
                # Pure scalar: find its type hint from TASK_PARAMETERS
                params_dict = dict(TASK_PARAMETERS.get(task_name, ()))
                required = params_dict.get(param_name, False)
                hint = f"(scalar — provide a string value{', required' if required else ', optional'})"
                bindings[param_name] = hint
        else:
            bindings[param_name] = _scan_for_files(root, exts)

    return {
        "supported": True,
        "task_name": task_name,
        "search_root": str(root),
        "bindings": bindings,
        "typed_bindings": _typed_binding_candidates(entry, root),
        "limitations": [
            "Search depth capped at 3; pass search_root for a narrower scope.",
            "V1 is best-effort: coverage depends on parameter naming conventions.",
        ],
    }


def list_available_bindings(
    task_name: str,
    search_root: str | None = None,
) -> dict[str, object]:
    """Discover files in the workspace that could satisfy each parameter of a task.

    Scans ``search_root`` (default: current working directory) up to depth 3
    for files whose extensions match per-parameter heuristics for the named
    task.  Scalar parameters return a hint string instead of a file list.

    Supported tasks: ``exonerate_align_chunk``, ``busco_assess_proteins``,
    ``fastqc``, ``gffread_proteins``.

    Args:
        task_name: Supported task name to discover bindings for.
        search_root: Optional root directory to scan (defaults to cwd).
"""
    return _list_available_bindings_impl(task_name, search_root=search_root)


# ---------------------------------------------------------------------------
# Step 25 — Bundle discovery tools
# ---------------------------------------------------------------------------


def list_bundles(pipeline_family: str | None = None) -> list[dict]:
    """Enumerate curated starter bundles, optionally filtered by pipeline family.

    Each entry includes an ``available`` flag and a ``reasons`` list so a
    scientist can see what is missing even for unavailable bundles.

    Args:
        pipeline_family: If given, only bundles whose ``pipeline_family``
            matches this string are returned.  Pass ``None`` (default) to
            list all families.
"""
    from flytetest.bundles import list_bundles as _list_bundles
    return _list_bundles(pipeline_family=pipeline_family)


def load_bundle(name: str) -> dict:
    """Return a bundle's typed bindings, scalar inputs, runtime images, and
    tool databases ready to spread into ``run_task`` / ``run_workflow``.

    On success the dict has ``supported=True`` plus ``bindings``, ``inputs``,
    ``runtime_images``, ``tool_databases``, ``description``, and
    ``pipeline_family``.  If the bundle exists but one or more backing paths
    are missing on disk, ``supported=False`` is returned with a ``reasons``
    list — never a partial payload.  If the name is not registered at all, a
    structured decline is returned instead of propagating a raw ``KeyError``.

    Args:
        name: Bundle name as returned by ``list_bundles()``.
"""
    from flytetest.bundles import load_bundle as _load_bundle
    from flytetest.bundles import BUNDLES
    try:
        return _load_bundle(name)
    except KeyError:
        return {
            "supported": False,
            "name": name,
            "reasons": [f"Unknown bundle {name!r}."],
            "next_steps": ["Call list_bundles() for the set of available names."],
        }


# ---------------------------------------------------------------------------
# Phase 3 — Run dashboard (TODO 12)
# ---------------------------------------------------------------------------


def _get_run_summary_impl(
    limit: int = 20,
    *,
    run_dir: Path | None = None,
) -> dict[str, object]:
    """Scan *run_dir* for durable run records and group them by state.

    Reads persisted ``slurm_run_record.json`` and ``local_run_record.json``
    from run subdirectories without querying the scheduler.

    Args:
        limit: Maximum number of entries to return in ``recent``.
        run_dir: Root directory that stores per-run record directories.
"""
    history_root = run_dir or DEFAULT_RUN_DIR
    if not history_root.is_dir():
        return {
            "supported": True,
            "total_scanned": 0,
            "by_state": {},
            "recent": [],
            "limitations": [],
        }

    # Collect candidate subdirs sorted by modification time descending.
    candidates: list[tuple[float, Path]] = []
    for entry in history_root.iterdir():
        if not entry.is_dir():
            continue
        slurm_rec = entry / DEFAULT_SLURM_RUN_RECORD_FILENAME
        local_rec = entry / DEFAULT_LOCAL_RUN_RECORD_FILENAME
        if slurm_rec.is_file() or local_rec.is_file():
            candidates.append((entry.stat().st_mtime, entry))
    candidates.sort(key=lambda t: t[0], reverse=True)

    max_inspect = limit * 5
    by_state: dict[str, int] = {}
    recent: list[dict[str, object]] = []
    total_scanned = 0

    for _, entry in candidates[:max_inspect]:
        total_scanned += 1
        slurm_rec_path = entry / DEFAULT_SLURM_RUN_RECORD_FILENAME
        local_rec_path = entry / DEFAULT_LOCAL_RUN_RECORD_FILENAME

        if slurm_rec_path.is_file():
            try:
                record = load_slurm_run_record(entry)
            except Exception:
                continue
            state = (record.final_scheduler_state or record.scheduler_state or "UNKNOWN").upper()
            by_state[state] = by_state.get(state, 0) + 1
            if len(recent) < limit:
                recent.append({
                    "kind": "slurm",
                    "job_id": record.job_id,
                    "workflow_name": record.workflow_name,
                    "state": state,
                    "created_at": record.submitted_at,
                    "run_record_path": str(slurm_rec_path),
                })
        elif local_rec_path.is_file():
            try:
                record_local: LocalRunRecord = load_local_run_record(entry)
            except Exception:
                continue
            state = "COMPLETED" if record_local.completed_at is not None else "IN_PROGRESS"
            by_state[state] = by_state.get(state, 0) + 1
            if len(recent) < limit:
                recent.append({
                    "kind": "local",
                    "job_id": None,
                    "workflow_name": record_local.workflow_name,
                    "state": state,
                    "created_at": record_local.created_at,
                    "run_record_path": str(local_rec_path),
                })

    return {
        "supported": True,
        "total_scanned": total_scanned,
        "by_state": by_state,
        "recent": recent,
        "limitations": [],
    }


def get_run_summary(limit: int = 20) -> dict[str, object]:
    """Return a state-grouped summary of recent local and Slurm run records.

    Reads persisted ``.runtime/runs/`` records only — no scheduler calls.
    Groups entries by state and returns the most recent ``limit`` entries.

    Args:
        limit: Maximum number of entries to return in ``recent``.
"""
    return _get_run_summary_impl(limit)


# ---------------------------------------------------------------------------
# Phase 4 — Result inspection (TODO 17)
# ---------------------------------------------------------------------------


def inspect_run_result(run_record_path: str) -> dict[str, object]:
    """Load one run record and return a structured human-readable summary.

    Detects whether *run_record_path* is a Slurm or local run record by
    filename.  Returns workflow name, run ID, state, node results, output
    paths, and the durable asset index path when present.  No scheduler
    calls are made.

    Args:
        run_record_path: Path to a ``slurm_run_record.json`` or
            ``local_run_record.json``, or the directory containing one.
"""
    path = Path(run_record_path)
    # Resolve to the record file if a directory was given.
    slurm_file = path / DEFAULT_SLURM_RUN_RECORD_FILENAME if path.is_dir() else path
    local_file = path / DEFAULT_LOCAL_RUN_RECORD_FILENAME if path.is_dir() else path

    # Detect kind by filename.
    if path.is_dir():
        if (path / DEFAULT_SLURM_RUN_RECORD_FILENAME).is_file():
            slurm_file = path / DEFAULT_SLURM_RUN_RECORD_FILENAME
            kind = "slurm"
        elif (path / DEFAULT_LOCAL_RUN_RECORD_FILENAME).is_file():
            local_file = path / DEFAULT_LOCAL_RUN_RECORD_FILENAME
            kind = "local"
        else:
            return {
                "supported": False,
                "run_record_path": run_record_path,
                "limitations": ["No run record file found in the specified directory."],
            }
    elif path.name == DEFAULT_SLURM_RUN_RECORD_FILENAME:
        kind = "slurm"
    elif path.name == DEFAULT_LOCAL_RUN_RECORD_FILENAME:
        kind = "local"
    else:
        return {
            "supported": False,
            "run_record_path": run_record_path,
            "limitations": [
                f"Cannot determine record type from path '{path.name}'. "
                f"Expected '{DEFAULT_SLURM_RUN_RECORD_FILENAME}' or '{DEFAULT_LOCAL_RUN_RECORD_FILENAME}'."
            ],
        }

    if kind == "slurm":
        try:
            record = load_slurm_run_record(slurm_file.parent if slurm_file != path else path)
        except Exception as exc:
            return {
                "supported": False,
                "run_record_path": run_record_path,
                "limitations": [f"Failed to load Slurm run record: {exc}"],
            }
        state = (record.final_scheduler_state or record.scheduler_state or "UNKNOWN").upper()
        durable_index = slurm_file.parent / "durable_asset_index.json"
        return {
            "supported": True,
            "kind": "slurm",
            "workflow_name": record.workflow_name,
            "run_id": record.run_id,
            "job_id": record.job_id,
            "state": state,
            "submitted_at": record.submitted_at,
            "node_results": [],
            "output_paths": [],
            "durable_asset_index_path": str(durable_index) if durable_index.is_file() else None,
            "run_record_path": str(slurm_file),
        }
    else:
        try:
            record_local: LocalRunRecord = load_local_run_record(
                local_file.parent if local_file != path else path
            )
        except Exception as exc:
            return {
                "supported": False,
                "run_record_path": run_record_path,
                "limitations": [f"Failed to load local run record: {exc}"],
            }
        state = "COMPLETED" if record_local.completed_at is not None else "IN_PROGRESS"
        node_results = [
            {
                "node_name": node_result.node_name,
                "reference_name": node_result.reference_name,
                "outputs": _jsonable(dict(node_result.outputs)),
            }
            for node_result in record_local.node_results
        ]
        output_paths = [
            str(v) for v in record_local.final_outputs.values()
            if v is not None
        ]
        local_rec_file = local_file if not path.is_dir() else path / DEFAULT_LOCAL_RUN_RECORD_FILENAME
        durable_index = local_rec_file.parent / "durable_asset_index.json"
        return {
            "supported": True,
            "kind": "local",
            "workflow_name": record_local.workflow_name,
            "run_id": record_local.run_id,
            "job_id": None,
            "state": state,
            "created_at": record_local.created_at,
            "completed_at": record_local.completed_at,
            "node_results": node_results,
            "output_paths": output_paths,
            "durable_asset_index_path": str(durable_index) if durable_index.is_file() else None,
            "run_record_path": str(local_rec_file),
        }


# ---------------------------------------------------------------------------
# Phase 5 — HPC Observability (M21b): resources, fetch_job_log, wait_for_slurm_job
# ---------------------------------------------------------------------------


def resource_run_recipe(path: str) -> str:
    """Return the raw JSON of a saved run recipe file.

    The *path* argument is resolved and validated against ``REPO_ROOT`` before
    any file I/O.  Returns an error JSON string if the path is outside
    ``REPO_ROOT`` or the file does not exist.

    Args:
        path: Absolute or relative path to a ``*.json`` run-recipe file.
    """
    try:
        resolved = Path(path).resolve()
        root = REPO_ROOT.resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            return '{"error": "path not found or outside allowed root"}'
        return resolved.read_text(encoding="utf-8")
    except OSError:
        return '{"error": "could not read file"}'


def resource_result_manifest(path: str) -> str:
    """Return the raw JSON of a ``run_manifest.json`` inside a result directory.

    The *path* argument is resolved and validated against ``REPO_ROOT`` before
    any file I/O.  Returns an error JSON string if the path is outside
    ``REPO_ROOT`` or the manifest does not exist.

    Args:
        path: Absolute or relative path to a result directory (or directly to
            a ``run_manifest.json`` file).
    """
    try:
        resolved = Path(path).resolve()
        root = REPO_ROOT.resolve()
        if not resolved.is_relative_to(root):
            return '{"error": "path not found or outside allowed root"}'
        if resolved.is_dir():
            manifest = resolved / "run_manifest.json"
        else:
            manifest = resolved
        if not manifest.is_file():
            return '{"error": "run_manifest.json not found"}'
        return manifest.read_text(encoding="utf-8")
    except OSError:
        return '{"error": "could not read file"}'


def _fetch_job_log_impl(
    log_path: str,
    tail_lines: int,
    *,
    run_dir: Path,
) -> dict[str, object]:
    """Return a bounded tail of a Slurm scheduler log file.

    Args:
        log_path: Path to the log file (stdout or stderr) written by Slurm.
        tail_lines: Number of lines to return from the end of the file.
            Clamped to ``MAX_MONITOR_TAIL_LINES``.
        run_dir: Directory that the resolved *log_path* must be under.
    """
    raw = _read_text_tail(
        Path(log_path),
        tail_lines=tail_lines,
        allowed_root=run_dir,
    )
    supported = raw is not None
    return {
        "supported": supported,
        "log_path": log_path,
        "content": raw,
        "tail_lines": min(tail_lines, MAX_MONITOR_TAIL_LINES),
        "limitations": [] if supported else [
            "Log file not found, unreadable, or outside the allowed run directory."
        ],
    }


def fetch_job_log(log_path: str, tail_lines: int = 100) -> dict[str, object]:
    """Return the tail of a Slurm job log (stdout or stderr).

    Reads the last *tail_lines* lines from the scheduler log identified by
    *log_path*.  The path must resolve inside the default run directory
    to prevent path-traversal reads.

    Args:
        log_path: Absolute path to a Slurm stdout or stderr log file.
        tail_lines: Lines to return from the end of the file.  Clamped to
            ``MAX_MONITOR_TAIL_LINES`` (500).
    """
    return _fetch_job_log_impl(log_path, tail_lines, run_dir=DEFAULT_RUN_DIR)


def _wait_for_slurm_job_impl(
    run_record_path: str | Path,
    timeout_s: int,
    poll_interval_s: int,
    *,
    run_dir: Path | None = None,
    scheduler_runner: Any = subprocess.run,
    command_available: Any = None,
    sleep_fn: Any = None,
) -> dict[str, object]:
    """Poll a Slurm job until it reaches a terminal state or the timeout expires.

    Args:
        run_record_path: Path to the durable Slurm run record.
        timeout_s: Maximum seconds to wait before returning ``timed_out=True``.
        poll_interval_s: Seconds between monitor polls.  Floored at 5.
        run_dir: Directory that stores run records (defaults to
            ``DEFAULT_RUN_DIR``).
        scheduler_runner: Injected scheduler command runner.
        command_available: Injected command probe.
        sleep_fn: Callable used between polls (``time.sleep`` by default).
            Inject a no-op in tests to avoid real delays.
    """
    if sleep_fn is None:
        sleep_fn = time.sleep
    interval = max(5, poll_interval_s)
    deadline = time.monotonic() + timeout_s
    last_result: dict[str, object] = {}
    while True:
        last_result = _monitor_slurm_job_impl(
            run_record_path,
            run_dir=run_dir,
            scheduler_runner=scheduler_runner,
            command_available=command_available,
        )
        lifecycle = last_result.get("lifecycle_result", {})
        if isinstance(lifecycle, dict) and lifecycle.get("final_scheduler_state") is not None:
            last_result["timed_out"] = False
            return last_result
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            last_result["timed_out"] = True
            return last_result
        sleep_fn(min(interval, remaining))


def wait_for_slurm_job(
    run_record_path: str,
    timeout_s: int = 300,
    poll_interval_s: int = 15,
) -> dict[str, object]:
    """Block until a Slurm job reaches a terminal state or the timeout expires.

    Polls ``monitor_slurm_job`` at *poll_interval_s* second intervals.  Returns
    the final ``monitor_slurm_job`` payload augmented with a ``timed_out`` key.

    Args:
        run_record_path: Path to the durable Slurm run record.
        timeout_s: Maximum seconds to wait.  Defaults to 300.
        poll_interval_s: Seconds between polls.  Floored at 5 seconds.
            Defaults to 15.
    """
    return _wait_for_slurm_job_impl(
        run_record_path,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    )


def _load_fastmcp() -> Any:
    """Import `FastMCP` lazily so unit tests can run without the SDK installed."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The `mcp` package is required to run the FLyteTest MCP server. "
            "Install it with `python3 -m pip install 'mcp[cli]'`."
        ) from exc
    return FastMCP


def _should_skip_stdio_line(line: str) -> bool:
    """Return whether one stdio input line should be ignored before JSON parsing.

    Args:
        line: One stdin line filtered before JSON-RPC parsing.
"""
    return not line.strip()


@asynccontextmanager
async def _filtered_stdio_server():
    """Wrap stdio transport while ignoring blank client lines that break JSON-RPC parsing."""
    import anyio
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    import mcp.types as types
    from mcp.shared.message import SessionMessage

    stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"))
    stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))

    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    async def stdin_reader() -> None:
        """Read stdio messages, drop blank lines, and forward JSON-RPC payloads."""
        try:
            async with read_stream_writer:
                async for line in stdin:
                    if _should_skip_stdio_line(line):
                        continue
                    try:
                        message = types.JSONRPCMessage.model_validate_json(line)
                    except Exception as exc:
                        await read_stream_writer.send(exc)
                        continue
                    await read_stream_writer.send(SessionMessage(message))
        except anyio.ClosedResourceError:  # pragma: no cover
            await anyio.lowlevel.checkpoint()

    async def stdout_writer() -> None:
        """Serialize MCP session messages back to stdout for the transport."""
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    json = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                    await stdout.write(json + "\n")
                    await stdout.flush()
        except anyio.ClosedResourceError:  # pragma: no cover
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(stdin_reader)
        task_group.start_soon(stdout_writer)
        yield read_stream, write_stream


def create_mcp_server(fastmcp_cls: Any | None = None) -> Any:
    """Build the recipe-backed FastMCP server for stdio execution.

    Args:
        fastmcp_cls: FastMCP class or test double used to construct the server.
"""
    fastmcp = _load_fastmcp() if fastmcp_cls is None else fastmcp_cls
    mcp = fastmcp(SHOWCASE_SERVER_NAME)

    mcp.tool(description=TOOL_DESCRIPTIONS["list_entries"])(list_entries)
    mcp.tool(description=TOOL_DESCRIPTIONS[PREPARE_RECIPE_TOOL_NAME])(prepare_run_recipe)
    mcp.tool(description=TOOL_DESCRIPTIONS[RUN_RECIPE_TOOL_NAME])(run_local_recipe)
    mcp.tool(description=TOOL_DESCRIPTIONS[RUN_SLURM_RECIPE_TOOL_NAME])(run_slurm_recipe)
    mcp.tool(description=TOOL_DESCRIPTIONS[VALIDATE_RUN_RECIPE_TOOL_NAME])(validate_run_recipe)
    mcp.tool(description=TOOL_DESCRIPTIONS[LIST_SLURM_RUN_HISTORY_TOOL_NAME])(list_slurm_run_history)
    mcp.tool(description=TOOL_DESCRIPTIONS[MONITOR_SLURM_JOB_TOOL_NAME])(monitor_slurm_job)
    mcp.tool(description=TOOL_DESCRIPTIONS[RETRY_SLURM_JOB_TOOL_NAME])(retry_slurm_job)
    mcp.tool(description=TOOL_DESCRIPTIONS[CANCEL_SLURM_JOB_TOOL_NAME])(cancel_slurm_job)
    mcp.tool(description=TOOL_DESCRIPTIONS[APPROVE_COMPOSED_RECIPE_TOOL_NAME])(approve_composed_recipe)
    mcp.tool(description=TOOL_DESCRIPTIONS[LIST_AVAILABLE_BINDINGS_TOOL_NAME])(list_available_bindings)
    mcp.tool(description=TOOL_DESCRIPTIONS[LIST_BUNDLES_TOOL_NAME])(list_bundles)
    mcp.tool(description=TOOL_DESCRIPTIONS[LOAD_BUNDLE_TOOL_NAME])(load_bundle)
    mcp.tool(description=TOOL_DESCRIPTIONS[RUN_TASK_TOOL_NAME])(run_task)
    mcp.tool(description=TOOL_DESCRIPTIONS[RUN_WORKFLOW_TOOL_NAME])(run_workflow)
    mcp.tool(description=TOOL_DESCRIPTIONS[GET_RUN_SUMMARY_TOOL_NAME])(get_run_summary)
    mcp.tool(description=TOOL_DESCRIPTIONS[INSPECT_RUN_RESULT_TOOL_NAME])(inspect_run_result)
    mcp.tool(description=TOOL_DESCRIPTIONS[FETCH_JOB_LOG_TOOL_NAME])(fetch_job_log)
    mcp.tool(description=TOOL_DESCRIPTIONS[WAIT_FOR_SLURM_JOB_TOOL_NAME])(wait_for_slurm_job)
    mcp.tool(description=TOOL_DESCRIPTIONS[GET_PIPELINE_STATUS_TOOL_NAME])(get_pipeline_status)
    # Flat-parameter tools: one per showcase target (lazy import to avoid circular dep).
    import flytetest.mcp_tools as _mcp_tools  # noqa: PLC0415
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_GERMLINE_DISCOVERY_TOOL_NAME])(_mcp_tools.vc_germline_discovery)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_PREPARE_REFERENCE_TOOL_NAME])(_mcp_tools.vc_prepare_reference)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_PREPROCESS_SAMPLE_TOOL_NAME])(_mcp_tools.vc_preprocess_sample)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_GENOTYPE_REFINEMENT_TOOL_NAME])(_mcp_tools.vc_genotype_refinement)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_SMALL_COHORT_FILTER_TOOL_NAME])(_mcp_tools.vc_small_cohort_filter)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_POST_GENOTYPING_REFINEMENT_TOOL_NAME])(_mcp_tools.vc_post_genotyping_refinement)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_SEQUENTIAL_INTERVAL_HC_TOOL_NAME])(_mcp_tools.vc_sequential_interval_haplotype_caller)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_PRE_CALL_COVERAGE_QC_TOOL_NAME])(_mcp_tools.vc_pre_call_coverage_qc)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_POST_CALL_QC_SUMMARY_TOOL_NAME])(_mcp_tools.vc_post_call_qc_summary)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_ANNOTATE_SNPEFF_TOOL_NAME])(_mcp_tools.vc_annotate_variants_snpeff)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_CUSTOM_FILTER_TOOL_NAME])(_mcp_tools.vc_custom_filter)
    mcp.tool(description=TOOL_DESCRIPTIONS[VC_APPLY_CUSTOM_FILTER_TOOL_NAME])(_mcp_tools.vc_apply_custom_filter)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_BRAKER3_TOOL_NAME])(_mcp_tools.annotation_braker3)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_PROTEIN_EVIDENCE_TOOL_NAME])(_mcp_tools.annotation_protein_evidence)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_BUSCO_QC_TOOL_NAME])(_mcp_tools.annotation_busco_qc)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_EGGNOG_TOOL_NAME])(_mcp_tools.annotation_eggnog)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_AGAT_STATS_TOOL_NAME])(_mcp_tools.annotation_agat_stats)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_AGAT_CONVERT_TOOL_NAME])(_mcp_tools.annotation_agat_convert)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_AGAT_CLEANUP_TOOL_NAME])(_mcp_tools.annotation_agat_cleanup)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_TABLE2ASN_TOOL_NAME])(_mcp_tools.annotation_table2asn)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_GFFREAD_PROTEINS_TOOL_NAME])(_mcp_tools.annotation_gffread_proteins)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_BUSCO_ASSESS_TOOL_NAME])(_mcp_tools.annotation_busco_assess)
    mcp.tool(description=TOOL_DESCRIPTIONS[ANNOTATION_EXONERATE_CHUNK_TOOL_NAME])(_mcp_tools.annotation_exonerate_chunk)
    mcp.tool(description=TOOL_DESCRIPTIONS[RNASEQ_QC_TOOL_NAME])(_mcp_tools.rnaseq_qc)
    mcp.tool(description=TOOL_DESCRIPTIONS[RNASEQ_FASTQC_TOOL_NAME])(_mcp_tools.rnaseq_fastqc)
    mcp.resource(SERVER_RESOURCE_URIS[0])(resource_scope)
    mcp.resource(SERVER_RESOURCE_URIS[1])(resource_supported_targets)
    mcp.resource(SERVER_RESOURCE_URIS[2])(resource_example_prompts)
    mcp.resource(SERVER_RESOURCE_URIS[3])(resource_prompt_and_run_contract)
    mcp.resource(SERVER_RESOURCE_URIS[4])(resource_run_recipe)
    mcp.resource(SERVER_RESOURCE_URIS[5])(resource_result_manifest)
    return mcp


async def _run_stdio_server_async() -> None:
    """Run the FastMCP server over stdio with blank-line-tolerant input parsing.

    A background Slurm polling task is started alongside the MCP server via an
    anyio task group.  The poll loop reconciles active Slurm run records in
    ``.runtime/runs/`` every ``SlurmPollingConfig.poll_interval_seconds``
    seconds without blocking the event loop.  The task is cancelled
    automatically when the server exits (i.e. when the stdio transport closes).
"""
    import anyio
    from flytetest.slurm_monitor import SlurmPollingConfig, slurm_poll_loop

    server = create_mcp_server()
    config = SlurmPollingConfig()

    async with anyio.create_task_group() as tg:
        tg.start_soon(slurm_poll_loop, DEFAULT_RUN_DIR, config)
        async with _filtered_stdio_server() as (read_stream, write_stream):
            await server._mcp_server.run(  # pyright: ignore[reportPrivateUsage]
                read_stream,
                write_stream,
                server._mcp_server.create_initialization_options(),  # pyright: ignore[reportPrivateUsage]
            )
        # Server transport closed; cancel the background poll task.
        tg.cancel_scope.cancel()


def main() -> None:
    """Run the FastMCP server over stdio."""
    try:
        import anyio

        anyio.run(_run_stdio_server_async)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
