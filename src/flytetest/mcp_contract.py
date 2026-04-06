"""Shared contract data for the narrow FLyteTest MCP showcase.

This module centralizes the exact stdio MCP surface exposed by the current
showcase: runnable targets, tool and resource names, example prompts,
downstream-scope decline labels, and stable prompt-and-run result codes.
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
MCP_TOOL_NAMES = ("list_entries", "plan_request", PRIMARY_TOOL_NAME)
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
DECLINED_PROMPT_EXAMPLE = (
    "Run BRAKER3 with genome data/genome.fa and protein evidence "
    "data/proteins.fa, then continue into EVM and BUSCO."
)

DECLINED_DOWNSTREAM_STAGE_NAMES = (
    "EVM",
    "PASA",
    "repeat filtering",
    "BUSCO",
    "EggNOG",
    "AGAT",
    "table2asn",
)
DOWNSTREAM_STAGE_LABELS = (
    ("agat", "AGAT"),
    ("busco", "BUSCO"),
    ("eggnog", "EggNOG"),
    ("evm", "EVM"),
    ("evidence modeler", "EVM"),
    ("functional annotation", "EggNOG"),
    ("pasa", "PASA"),
    ("repeat filtering", "repeat filtering"),
    ("repeatmasker", "repeat filtering"),
    ("submission", "table2asn"),
    ("table2asn", "table2asn"),
)

SHOWCASE_LIMITATIONS = (
    "This showcase supports only the workflows `ab_initio_annotation_braker3`, `protein_evidence_alignment`, and the task `exonerate_align_chunk`.",
    "The prompt must contain explicit local file paths; the planner does not search the filesystem or auto-discover `data/` files.",
    "It does not imply EVM, PASA refinement, repeat filtering, BUSCO, EggNOG, AGAT, or `table2asn`.",
)
LIST_ENTRIES_LIMITATIONS = (
    "This showcase exposes only `ab_initio_annotation_braker3`, `protein_evidence_alignment`, and `exonerate_align_chunk` as runnable targets.",
    "The primary MCP flow is `prompt_and_run(prompt)`, which plans and executes only prompt-contained explicit local paths.",
)
PROMPT_REQUIREMENTS = (
    "Write explicit local file paths directly in the prompt.",
    "Keep the request to one supported target per prompt.",
)
EXAMPLE_PROMPT_REQUIREMENTS = (
    "Include explicit local file paths in the prompt text.",
    "Do not ask for EVM, PASA, repeat filtering, BUSCO, EggNOG, AGAT, or table2asn.",
)

RESULT_CODE_SUCCEEDED = "succeeded"
RESULT_CODE_DECLINED_DOWNSTREAM_SCOPE = "declined_downstream_scope"
RESULT_CODE_DECLINED_MISSING_INPUTS = "declined_missing_inputs"
RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST = "declined_unsupported_request"
RESULT_CODE_FAILED_EXECUTION = "failed_execution"

REASON_CODE_COMPLETED = "completed"
REASON_CODE_REQUESTED_DOWNSTREAM_STAGE = "requested_downstream_stage"
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
    "declined_downstream_stages",
    "supported_targets",
    "message",
)
RESULT_CODE_DEFINITIONS = {
    RESULT_CODE_SUCCEEDED: {
        "status": "succeeded",
        "reason_codes": [REASON_CODE_COMPLETED],
    },
    RESULT_CODE_DECLINED_DOWNSTREAM_SCOPE: {
        "status": "declined",
        "reason_codes": [REASON_CODE_REQUESTED_DOWNSTREAM_STAGE],
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
    "downstream_scope": RESULT_CODE_DECLINED_DOWNSTREAM_SCOPE,
    "missing_inputs": RESULT_CODE_DECLINED_MISSING_INPUTS,
    "unsupported_or_ambiguous_request": RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST,
}


def supported_runnable_targets_payload() -> list[dict[str, str]]:
    """Return the exact runnable target payload exposed through MCP resources."""
    return [{"name": target.name, "category": target.category} for target in SHOWCASE_TARGETS]
