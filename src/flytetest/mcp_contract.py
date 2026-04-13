"""Shared contract data for the FLyteTest MCP recipe surface.

This module centralizes the stdio MCP surface exposed by the recipe-backed
server: explicit runnable targets, tool and resource names, example prompts,
stable prompt-and-run result codes, and typed-planning fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flytetest.config import (
    AGAT_CLEANUP_WORKFLOW_NAME,
    AGAT_CONVERSION_WORKFLOW_NAME,
    AGAT_WORKFLOW_NAME,
    ANNOTATION_WORKFLOW_NAME,
    EGGNOG_WORKFLOW_NAME,
    FUNCTIONAL_QC_WORKFLOW_NAME,
    PROTEIN_EVIDENCE_WORKFLOW_NAME,
)


@dataclass(frozen=True, slots=True)
class ShowcaseTarget:
    """Describe one runnable workflow or task exposed by the MCP showcase.

    Attributes:
        name: Registered workflow or task name exposed through MCP.
        category: Whether the target is a workflow or task.
        module_name: Import path for the implementation module.
        source_path: Filesystem path to the implementation source file.
    """

    name: str
    category: str
    module_name: str
    source_path: Path


SHOWCASE_SERVER_NAME = "FLyteTest"
PRIMARY_TOOL_NAME = "prompt_and_run"
PREPARE_RECIPE_TOOL_NAME = "prepare_run_recipe"
RUN_RECIPE_TOOL_NAME = "run_local_recipe"
RUN_SLURM_RECIPE_TOOL_NAME = "run_slurm_recipe"
LIST_SLURM_RUN_HISTORY_TOOL_NAME = "list_slurm_run_history"
MONITOR_SLURM_JOB_TOOL_NAME = "monitor_slurm_job"
RETRY_SLURM_JOB_TOOL_NAME = "retry_slurm_job"
CANCEL_SLURM_JOB_TOOL_NAME = "cancel_slurm_job"
APPROVE_COMPOSED_RECIPE_TOOL_NAME = "approve_composed_recipe"
MCP_TOOL_NAMES = (
    "list_entries",
    "plan_request",
    PREPARE_RECIPE_TOOL_NAME,
    RUN_RECIPE_TOOL_NAME,
    RUN_SLURM_RECIPE_TOOL_NAME,
    LIST_SLURM_RUN_HISTORY_TOOL_NAME,
    MONITOR_SLURM_JOB_TOOL_NAME,
    RETRY_SLURM_JOB_TOOL_NAME,
    CANCEL_SLURM_JOB_TOOL_NAME,
    APPROVE_COMPOSED_RECIPE_TOOL_NAME,
    PRIMARY_TOOL_NAME,
)
MCP_RESOURCE_URIS = (
    "flytetest://scope",
    "flytetest://supported-targets",
    "flytetest://example-prompts",
    "flytetest://prompt-and-run-contract",
)

SUPPORTED_WORKFLOW_NAME = ANNOTATION_WORKFLOW_NAME
SUPPORTED_PROTEIN_WORKFLOW_NAME = PROTEIN_EVIDENCE_WORKFLOW_NAME
SUPPORTED_TASK_NAME = "exonerate_align_chunk"
SUPPORTED_BUSCO_FIXTURE_TASK_NAME = "busco_assess_proteins"
SUPPORTED_BUSCO_WORKFLOW_NAME = FUNCTIONAL_QC_WORKFLOW_NAME
SUPPORTED_EGGNOG_WORKFLOW_NAME = EGGNOG_WORKFLOW_NAME
SUPPORTED_AGAT_WORKFLOW_NAME = AGAT_WORKFLOW_NAME
SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME = AGAT_CONVERSION_WORKFLOW_NAME
SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME = AGAT_CLEANUP_WORKFLOW_NAME

_PACKAGE_ROOT = Path(__file__).resolve().parent

SHOWCASE_TARGETS = (
    ShowcaseTarget(
        name=SUPPORTED_WORKFLOW_NAME,
        category="workflow",
        module_name="flytetest.workflows.annotation",
        source_path=_PACKAGE_ROOT / "workflows" / "annotation.py",
    ),
    ShowcaseTarget(
        name=SUPPORTED_PROTEIN_WORKFLOW_NAME,
        category="workflow",
        module_name="flytetest.workflows.protein_evidence",
        source_path=_PACKAGE_ROOT / "workflows" / "protein_evidence.py",
    ),
    ShowcaseTarget(
        name=SUPPORTED_TASK_NAME,
        category="task",
        module_name="flytetest.tasks.protein_evidence",
        source_path=_PACKAGE_ROOT / "tasks" / "protein_evidence.py",
    ),
    ShowcaseTarget(
        name=SUPPORTED_BUSCO_FIXTURE_TASK_NAME,
        category="task",
        module_name="flytetest.tasks.functional",
        source_path=_PACKAGE_ROOT / "tasks" / "functional.py",
    ),
    ShowcaseTarget(
        name=SUPPORTED_BUSCO_WORKFLOW_NAME,
        category="workflow",
        module_name="flytetest.workflows.functional",
        source_path=_PACKAGE_ROOT / "workflows" / "functional.py",
    ),
    ShowcaseTarget(
        name=SUPPORTED_EGGNOG_WORKFLOW_NAME,
        category="workflow",
        module_name="flytetest.workflows.eggnog",
        source_path=_PACKAGE_ROOT / "workflows" / "eggnog.py",
    ),
    ShowcaseTarget(
        name=SUPPORTED_AGAT_WORKFLOW_NAME,
        category="workflow",
        module_name="flytetest.workflows.agat",
        source_path=_PACKAGE_ROOT / "workflows" / "agat.py",
    ),
    ShowcaseTarget(
        name=SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME,
        category="workflow",
        module_name="flytetest.workflows.agat",
        source_path=_PACKAGE_ROOT / "workflows" / "agat.py",
    ),
    ShowcaseTarget(
        name=SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME,
        category="workflow",
        module_name="flytetest.workflows.agat",
        source_path=_PACKAGE_ROOT / "workflows" / "agat.py",
    ),
)
SHOWCASE_TARGETS_BY_NAME = {target.name: target for target in SHOWCASE_TARGETS}
SUPPORTED_TARGET_NAMES = tuple(target.name for target in SHOWCASE_TARGETS)
SUPPORTED_WORKFLOW_NAMES = tuple(target.name for target in SHOWCASE_TARGETS if target.category == "workflow")
SUPPORTED_TASK_NAMES = tuple(target.name for target in SHOWCASE_TARGETS if target.category == "task")

RECIPE_INPUT_CONTEXT_FIELDS = (
    "manifest_sources",
    "explicit_bindings",
    "runtime_bindings",
    "resource_request",
    "execution_profile",
    "runtime_image",
)
RECIPE_INPUT_MANIFEST_RULES = (
    "Provide each manifest source as a `run_manifest.json` path or a result directory containing one.",
    "Manifest sources are validated before typed planning runs, and unreadable or missing sources are rejected.",
    "The resolver refuses to guess when multiple manifests could satisfy the requested planner type.",
)
RECIPE_INPUT_BINDING_RULES = (
    "Serialized planner bindings are accepted as JSON mappings keyed by planner type name.",
    "Direct MCP clients must send structured binding arguments as real JSON/object mappings, not stringified pseudo-dicts.",
    "BUSCO, EggNOG, and AGAT use a `QualityAssessmentTarget` binding when the target is supplied directly instead of recovered from a manifest.",
)
RECIPE_INPUT_RUNTIME_RULES = (
    "Runtime bindings are frozen into the saved recipe and are not inferred from prompt text.",
    "Direct MCP clients must send `runtime_bindings`, `resource_request`, and `runtime_image` as real JSON/object mappings.",
    "If an LLM-driven client drops optional tool arguments, encode the execution profile and resource choices in the prompt text and verify the returned frozen profile before Slurm submission.",
    "The M18 BUSCO fixture task uses `proteins_fasta`, `lineage_dataset`, `busco_mode`, optional `busco_sif`, and `busco_cpu` runtime bindings.",
    "BUSCO runtime bindings begin with `busco_lineages_text`, optional `busco_sif`, and `busco_cpu`.",
    "EggNOG runtime bindings are `eggnog_data_dir`, optional `eggnog_sif`, `eggnog_cpu`, and `eggnog_database`.",
    "AGAT runtime bindings are `annotation_fasta_path` and optional `agat_sif` for statistics, and optional `agat_sif` for conversion.",
    "Resource requests use structured `ResourceSpec` fields such as `cpu`, `memory`, `queue`, `account`, and `walltime`.",
    "`local` recipes run through explicit local handlers; `slurm` recipes can be submitted with `run_slurm_recipe` after they are frozen.",
    "`list_slurm_run_history` reads durable `.runtime/runs/` records only, supports optional `workflow_name`, `active_only`, and `terminal_only` filters, and does not require live scheduler access.",
    "Slurm recipe submission and lifecycle tools require FLyteTest to run inside an already-authenticated scheduler-capable environment with the needed Slurm CLI commands on PATH.",
    "`monitor_slurm_job`, `retry_slurm_job`, and `cancel_slurm_job` operate from durable `.runtime/runs/` Slurm run records and return explicit unsupported-environment limitations when that scheduler boundary is unavailable.",
    "`retry_slurm_job` stays Slurm-specific, reuses the frozen saved recipe plus recorded execution profile, and declines when the run record is not terminal, not clearly retryable, or already at its attempt limit.",
    "Runtime image policy can be frozen as `RuntimeImageSpec` metadata, while existing workflow SIF inputs remain explicit runtime bindings.",
)

WORKFLOW_EXAMPLE_PROMPT = (
    "Annotate the genome sequence of a small eukaryote using BRAKER3 "
    "with genome data/braker3/reference/genome.fa, RNA-seq evidence data/braker3/rnaseq/RNAseq.bam, "
    "and protein evidence data/braker3/protein_data/fastas/proteins.fa"
)
PROTEIN_WORKFLOW_EXAMPLE_PROMPT = (
    "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein "
    "evidence data/braker3/protein_data/fastas/proteins.fa"
)
TASK_EXAMPLE_PROMPT = (
    "Experiment with Exonerate protein-to-genome alignment using genome "
    "data/braker3/reference/genome.fa and protein chunk data/braker3/protein_data/fastas/proteins.fa"
)
SHOWCASE_LIMITATIONS = (
    "The MCP recipe surface executes `ab_initio_annotation_braker3`, `protein_evidence_alignment`, `exonerate_align_chunk`, `busco_assess_proteins`, `annotation_qc_busco`, `annotation_functional_eggnog`, `annotation_postprocess_agat`, `annotation_postprocess_agat_conversion`, and `annotation_postprocess_agat_cleanup` through explicit local handlers.",
    "Prompt-contained local file paths and explicit recipe inputs are frozen into saved WorkflowSpec artifacts before execution.",
    "Additional registered workflows require explicit local handlers before they are exposed as runnable MCP targets.",
)
LIST_ENTRIES_LIMITATIONS = (
    "The MCP recipe surface exposes only `ab_initio_annotation_braker3`, `protein_evidence_alignment`, `exonerate_align_chunk`, `busco_assess_proteins`, `annotation_qc_busco`, `annotation_functional_eggnog`, `annotation_postprocess_agat`, `annotation_postprocess_agat_conversion`, and `annotation_postprocess_agat_cleanup` as runnable targets.",
    "The primary MCP flow is `prompt_and_run(prompt)`, which prepares and executes a saved WorkflowSpec artifact.",
)
PROMPT_REQUIREMENTS = (
    "Write explicit local file paths directly in the prompt when you want prompt-derived runtime bindings.",
    "Provide manifest sources, serialized planner bindings, runtime bindings, resource requests, execution profiles, and runtime-image policy explicitly when the prompt text does not already carry them.",
    "When an LLM-driven client does not preserve optional tool arguments reliably, place critical execution policy such as `execution profile slurm` and resource choices directly in the prompt text and verify the returned frozen recipe.",
    "Keep the request to one supported target per prompt.",
)
EXAMPLE_PROMPT_REQUIREMENTS = (
    "Include explicit local file paths in the prompt text.",
    "Use one of the currently runnable MCP recipe targets until additional local handlers are registered.",
)

RESULT_CODE_SUCCEEDED = "succeeded"
RESULT_CODE_DECLINED_MISSING_INPUTS = "declined_missing_inputs"
RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST = "declined_unsupported_request"
RESULT_CODE_FAILED_EXECUTION = "failed_execution"

REASON_CODE_COMPLETED = "completed"
REASON_CODE_MISSING_REQUIRED_INPUTS = "missing_required_inputs"
REASON_CODE_UNSUPPORTED_OR_AMBIGUOUS_REQUEST = "unsupported_or_ambiguous_request"
REASON_CODE_NONZERO_EXIT_STATUS = "nonzero_exit_status"
REASON_CODE_UNSUPPORTED_EXECUTION_TARGET = "unsupported_execution_target"

RESULT_SUMMARY_FIELDS = (
    "status",
    "result_code",
    "reason_code",
    "target_name",
    "target_category",
    "execution_attempted",
    "used_inputs",
    "output_paths",
    "exit_status",
    "decline_reason",
    "supported_targets",
    "typed_planning_available",
    "artifact_path",
    "execution_profile",
    "resource_spec",
    "runtime_image",
    "message",
)
RESULT_CODE_DEFINITIONS = {
    RESULT_CODE_SUCCEEDED: {
        "status": "succeeded",
        "reason_codes": [REASON_CODE_COMPLETED],
    },
    RESULT_CODE_DECLINED_MISSING_INPUTS: {
        "status": "declined",
        "reason_codes": [REASON_CODE_MISSING_REQUIRED_INPUTS],
    },
    RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST: {
        "status": "declined",
        "reason_codes": [REASON_CODE_UNSUPPORTED_OR_AMBIGUOUS_REQUEST],
    },
    RESULT_CODE_FAILED_EXECUTION: {
        "status": "failed",
        "reason_codes": [
            REASON_CODE_NONZERO_EXIT_STATUS,
            REASON_CODE_UNSUPPORTED_EXECUTION_TARGET,
        ],
    },
}
DECLINE_CATEGORY_CODES = {
    "missing_inputs": RESULT_CODE_DECLINED_MISSING_INPUTS,
    "unsupported_or_ambiguous_request": RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST,
}


def supported_runnable_targets_payload() -> list[dict[str, str]]:
    """Return the runnable MCP targets as a stable resource payload."""
    return [{"name": target.name, "category": target.category} for target in SHOWCASE_TARGETS]
