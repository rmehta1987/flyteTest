"""Shared contract data for the FLyteTest MCP recipe surface.

This module centralizes the stdio MCP surface exposed by the recipe-backed
server: day-one runnable targets, tool and resource names, example prompts,
stable prompt-and-run result codes, and typed-planning fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flytetest.config import ANNOTATION_WORKFLOW_NAME, PROTEIN_EVIDENCE_WORKFLOW_NAME


@dataclass(frozen=True, slots=True)
class ShowcaseTarget:
    """Describe one runnable workflow or task exposed by the MCP showcase."""

    name: str
    category: str
    module_name: str
    source_path: Path


SHOWCASE_SERVER_NAME = "FLyteTest"
PRIMARY_TOOL_NAME = "prompt_and_run"
PREPARE_RECIPE_TOOL_NAME = "prepare_run_recipe"
RUN_RECIPE_TOOL_NAME = "run_local_recipe"
MCP_TOOL_NAMES = ("list_entries", "plan_request", PREPARE_RECIPE_TOOL_NAME, RUN_RECIPE_TOOL_NAME, PRIMARY_TOOL_NAME)
MCP_RESOURCE_URIS = (
    "flytetest://scope",
    "flytetest://supported-targets",
    "flytetest://example-prompts",
    "flytetest://prompt-and-run-contract",
)

SUPPORTED_WORKFLOW_NAME = ANNOTATION_WORKFLOW_NAME
SUPPORTED_PROTEIN_WORKFLOW_NAME = PROTEIN_EVIDENCE_WORKFLOW_NAME
SUPPORTED_TASK_NAME = "exonerate_align_chunk"

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
)
SHOWCASE_TARGETS_BY_NAME = {target.name: target for target in SHOWCASE_TARGETS}
SUPPORTED_TARGET_NAMES = tuple(target.name for target in SHOWCASE_TARGETS)
SUPPORTED_WORKFLOW_NAMES = tuple(target.name for target in SHOWCASE_TARGETS if target.category == "workflow")
SUPPORTED_TASK_NAMES = tuple(target.name for target in SHOWCASE_TARGETS if target.category == "task")

WORKFLOW_EXAMPLE_PROMPT = (
    "Annotate the genome sequence of a small eukaryote using BRAKER3 "
    "with genome data/genome.fa, RNA-seq evidence data/RNAseq.bam, "
    "and protein evidence data/proteins.fa"
)
PROTEIN_WORKFLOW_EXAMPLE_PROMPT = (
    "Run protein evidence alignment with genome data/genome.fa and protein "
    "evidence data/proteins.fa"
)
TASK_EXAMPLE_PROMPT = (
    "Experiment with Exonerate protein-to-genome alignment using genome "
    "data/genome.fa and protein chunk data/proteins.fa"
)
SHOWCASE_LIMITATIONS = (
    "The day-one MCP recipe surface executes only `ab_initio_annotation_braker3`, `protein_evidence_alignment`, and `exonerate_align_chunk`.",
    "Prompt-contained local file paths are frozen into saved WorkflowSpec artifacts before execution.",
    "Additional registered workflows require explicit local handlers before they are exposed as runnable MCP targets.",
)
LIST_ENTRIES_LIMITATIONS = (
    "The day-one MCP recipe surface exposes only `ab_initio_annotation_braker3`, `protein_evidence_alignment`, and `exonerate_align_chunk` as runnable targets.",
    "The primary MCP flow is `prompt_and_run(prompt)`, which prepares and executes a saved WorkflowSpec artifact.",
)
PROMPT_REQUIREMENTS = (
    "Write explicit local file paths directly in the prompt.",
    "Keep the request to one supported target per prompt.",
)
EXAMPLE_PROMPT_REQUIREMENTS = (
    "Include explicit local file paths in the prompt text.",
    "Use one of the day-one MCP recipe targets until additional local handlers are registered.",
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
    """Return the exact runnable target payload exposed through MCP resources."""
    return [{"name": target.name, "category": target.category} for target in SHOWCASE_TARGETS]
