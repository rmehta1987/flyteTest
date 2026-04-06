"""Deterministic prompt planning for the narrow FLyteTest MCP showcase.

This module intentionally supports only two prebuilt workflows and one task:
`ab_initio_annotation_braker3`, `protein_evidence_alignment`, and
`exonerate_align_chunk`. It classifies a prompt, extracts explicit local file
paths written directly in that prompt, maps those paths onto the supported
entry inputs, and returns a structured plan without inventing broader
orchestration behavior.
"""

from __future__ import annotations

import ast
import argparse
import inspect
import json
import re
from dataclasses import asdict, dataclass
from importlib import import_module

from flytetest.mcp_contract import (
    DOWNSTREAM_STAGE_LABELS,
    SHOWCASE_LIMITATIONS,
    SHOWCASE_TARGETS_BY_NAME,
    SUPPORTED_PROTEIN_WORKFLOW_NAME,
    SUPPORTED_TASK_NAME,
    SUPPORTED_WORKFLOW_NAME,
)
from flytetest.registry import InterfaceField, RegistryEntry, get_entry


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PATH_RE = re.compile(r"(?P<path>(?:\.{1,2}/|/|[A-Za-z0-9_-]+/)[A-Za-z0-9_./-]+)")
_FASTA_SUFFIXES = (".fa", ".faa", ".fasta", ".fna", ".fas")


@dataclass(frozen=True, slots=True)
class PlannedInput:
    """One planner-facing input field for a supported entry."""

    name: str
    type: str
    description: str


@dataclass(frozen=True, slots=True)
class EntryParameter:
    """One parameter from a supported task or workflow signature."""

    name: str
    required: bool


@dataclass(frozen=True, slots=True)
class PromptPath:
    """One explicit local path mention extracted from the prompt text."""

    value: str
    context: str


def _normalize(text: str) -> str:
    """Normalize free text into lowercase alphanumeric tokens."""
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _supported_entry(name: str) -> RegistryEntry:
    """Resolve one supported registry entry by name."""
    if name not in SHOWCASE_TARGETS_BY_NAME:
        raise KeyError(f"Unsupported showcase entry: {name}")
    return get_entry(name)


def _parameters_from_source(name: str) -> tuple[EntryParameter, ...]:
    """Parse the checked-in source file when import-time reflection is unavailable."""
    source_path = SHOWCASE_TARGETS_BY_NAME[name].source_path
    module = ast.parse(source_path.read_text(), filename=str(source_path))
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            arg_names = [argument.arg for argument in node.args.args]
            required_count = len(arg_names) - len(node.args.defaults)
            return tuple(
                EntryParameter(name=argument_name, required=index < required_count)
                for index, argument_name in enumerate(arg_names)
            )
    raise ValueError(f"Could not resolve signature for `{name}` from {source_path}.")


def supported_entry_parameters(name: str) -> tuple[EntryParameter, ...]:
    """Return supported entry parameters from imports or source fallback."""
    target = SHOWCASE_TARGETS_BY_NAME.get(name)
    if target is None:
        raise KeyError(f"Unsupported showcase entry: {name}")
    module_name = target.module_name

    try:
        module = import_module(module_name)
        entry = getattr(module, name)
        signature = inspect.signature(entry)
        if signature.parameters and all(
            parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for parameter in signature.parameters.values()
        ):
            return _parameters_from_source(name)
        return tuple(
            EntryParameter(
                name=parameter_name,
                required=parameter.default is inspect.Parameter.empty,
            )
            for parameter_name, parameter in signature.parameters.items()
        )
    except ModuleNotFoundError as exc:
        if exc.name not in {"flyte", "flyte.io"}:
            raise
        return _parameters_from_source(name)


def split_entry_inputs(name: str) -> tuple[tuple[PlannedInput, ...], tuple[PlannedInput, ...]]:
    """Split registry-defined entry inputs into required and optional groups."""
    entry = _supported_entry(name)
    registry_fields = {field.name: field for field in entry.inputs}

    required: list[PlannedInput] = []
    optional: list[PlannedInput] = []
    for parameter in supported_entry_parameters(name):
        field = registry_fields[parameter.name]
        planned = PlannedInput(name=field.name, type=field.type, description=field.description)
        if parameter.required:
            required.append(planned)
        else:
            optional.append(planned)
    return tuple(required), tuple(optional)


def _clean_path(raw_path: str) -> str:
    """Strip trailing punctuation from one path-like prompt token."""
    return raw_path.rstrip(".,);:'\"")


def _extract_prompt_paths(request: str) -> tuple[PromptPath, ...]:
    """Return explicit local path mentions with the prefix text that labels them."""
    matches: list[PromptPath] = []
    for match in _PATH_RE.finditer(request):
        path = _clean_path(match.group("path"))
        if "/" not in path:
            continue
        start = max(0, match.start() - 60)
        matches.append(PromptPath(value=path, context=request[start:match.start()].lower()))
    return tuple(matches)


def _is_bam_path(path: str) -> bool:
    """Return whether a prompt path looks like a BAM file."""
    return path.lower().endswith(".bam")


def _is_fasta_path(path: str) -> bool:
    """Return whether a prompt path looks like a FASTA file."""
    lowered = path.lower()
    if lowered.endswith(".gz"):
        lowered = lowered[:-3]
    return lowered.endswith(_FASTA_SUFFIXES)


def _last_keyword_index(context: str, keywords: tuple[str, ...]) -> int:
    """Return the nearest keyword position from a short prompt prefix context."""
    return max((context.rfind(keyword) for keyword in keywords), default=-1)


def _extract_braker_workflow_inputs(request: str, prompt_paths: tuple[PromptPath, ...]) -> dict[str, str]:
    """Map prompt-contained explicit paths to BRAKER3 workflow inputs."""
    extracted: dict[str, str] = {}
    unlabeled_fastas: list[str] = []

    for mention in prompt_paths:
        path = mention.value
        if _is_bam_path(path):
            extracted.setdefault("rnaseq_bam_path", path)
            continue
        if path.lower().endswith(".sif") and "braker" in mention.context:
            extracted.setdefault("braker3_sif", path)
            continue
        if not _is_fasta_path(path):
            continue

        protein_index = _last_keyword_index(mention.context, ("protein",))
        genome_index = _last_keyword_index(mention.context, ("genome",))
        if protein_index > genome_index:
            extracted.setdefault("protein_fasta_path", path)
            continue
        if genome_index > protein_index:
            extracted.setdefault("genome", path)
            continue
        unlabeled_fastas.append(path)

    if "genome" not in extracted and len(unlabeled_fastas) == 1 and "protein_fasta_path" not in extracted:
        extracted["genome"] = unlabeled_fastas[0]

    species_match = re.search(r"\bbraker species\b\s*[:=]?\s*([A-Za-z0-9_.-]+)", request, flags=re.IGNORECASE)
    if species_match:
        extracted["braker_species"] = species_match.group(1)

    return extracted


def _extract_protein_workflow_inputs(
    request: str,
    prompt_paths: tuple[PromptPath, ...],
) -> dict[str, object]:
    """Map prompt-contained explicit paths to protein-evidence workflow inputs."""
    extracted: dict[str, object] = {}
    protein_fastas: list[str] = []
    unlabeled_fastas: list[str] = []

    for mention in prompt_paths:
        path = mention.value
        if path.lower().endswith(".sif") and "exonerate" in mention.context:
            extracted.setdefault("exonerate_sif", path)
            continue
        if not _is_fasta_path(path):
            continue

        protein_index = _last_keyword_index(mention.context, ("protein",))
        genome_index = _last_keyword_index(mention.context, ("genome",))
        if protein_index > genome_index:
            if path not in protein_fastas:
                protein_fastas.append(path)
            continue
        if genome_index > protein_index:
            extracted.setdefault("genome", path)
            continue
        unlabeled_fastas.append(path)

    if "genome" in extracted:
        for path in unlabeled_fastas:
            if path != extracted["genome"] and path not in protein_fastas:
                protein_fastas.append(path)
    elif len(unlabeled_fastas) == 1 and not protein_fastas:
        extracted["genome"] = unlabeled_fastas[0]

    proteins_per_chunk_match = re.search(
        r"\bproteins per chunk\b\s*[:=]?\s*(\d+)",
        request,
        flags=re.IGNORECASE,
    )
    if proteins_per_chunk_match:
        extracted["proteins_per_chunk"] = proteins_per_chunk_match.group(1)

    model_match = re.search(r"\bmodel\b\s*[:=]?\s*([A-Za-z0-9_.-]+)", request, flags=re.IGNORECASE)
    if model_match and "exonerate" in request.lower():
        extracted["exonerate_model"] = model_match.group(1)

    if protein_fastas:
        extracted["protein_fastas"] = protein_fastas
    return extracted


def _extract_task_inputs(request: str, prompt_paths: tuple[PromptPath, ...]) -> dict[str, str]:
    """Map prompt-contained explicit paths to the Exonerate chunk task inputs."""
    extracted: dict[str, str] = {}
    unlabeled_fastas: list[str] = []

    for mention in prompt_paths:
        path = mention.value
        if path.lower().endswith(".sif") and "exonerate" in mention.context:
            extracted.setdefault("exonerate_sif", path)
            continue
        if not _is_fasta_path(path):
            continue

        protein_index = _last_keyword_index(mention.context, ("protein", "chunk"))
        genome_index = _last_keyword_index(mention.context, ("genome", "target"))
        if protein_index > genome_index:
            extracted.setdefault("protein_chunk", path)
            continue
        if genome_index > protein_index:
            extracted.setdefault("genome", path)
            continue
        unlabeled_fastas.append(path)

    if len(unlabeled_fastas) == 1 and "genome" not in extracted and "protein_chunk" not in extracted:
        extracted["genome"] = unlabeled_fastas[0]

    model_match = re.search(r"\bmodel\b\s*[:=]?\s*([A-Za-z0-9_.-]+)", request, flags=re.IGNORECASE)
    if model_match and "exonerate" in request.lower():
        extracted["exonerate_model"] = model_match.group(1)

    return extracted


def _classify_target(normalized_request: str) -> tuple[str | None, float, tuple[str, ...]]:
    """Classify the prompt as one supported workflow, task, or unsupported."""
    has_exonerate = "exonerate" in normalized_request
    has_braker = "braker3" in normalized_request or "braker" in normalized_request
    has_annotation_intent = "annotate" in normalized_request and "genome" in normalized_request
    has_chunk = "chunk" in normalized_request
    has_experiment = "experiment" in normalized_request
    has_protein_workflow = (
        "protein_evidence_alignment" in normalized_request
        or "protein evidence alignment" in normalized_request
        or ("protein evidence" in normalized_request and ("workflow" in normalized_request or "alignment" in normalized_request))
    )
    has_task_intent = has_exonerate and (has_chunk or has_experiment)
    has_braker_intent = has_braker or has_annotation_intent

    intent_count = sum((has_braker_intent, has_protein_workflow, has_task_intent))
    if intent_count > 1:
        return (
            None,
            0.0,
            (
                "The prompt mixes multiple supported showcase targets in one request.",
                "This showcase runs exactly one target per prompt and declines ambiguous mixed requests.",
            ),
        )

    if has_task_intent:
        return (
            SUPPORTED_TASK_NAME,
            0.97,
            (
                "The prompt explicitly asks for Exonerate protein-to-genome alignment experimentation.",
                "That maps to the supported task `exonerate_align_chunk`.",
            ),
        )

    if has_braker_intent:
        rationale = [
            "The prompt asks for genome annotation in BRAKER3-style language.",
            "That maps to the supported workflow `ab_initio_annotation_braker3`.",
        ]
        confidence = 0.94
        if has_braker:
            rationale.insert(0, "The prompt explicitly mentions BRAKER3.")
            confidence = 0.98
        return SUPPORTED_WORKFLOW_NAME, confidence, tuple(rationale)

    if has_protein_workflow:
        return (
            SUPPORTED_PROTEIN_WORKFLOW_NAME,
            0.96,
            (
                "The prompt asks for the protein-evidence alignment stage rather than a single Exonerate chunk experiment.",
                "That maps to the supported workflow `protein_evidence_alignment`.",
            ),
        )

    return (
        None,
        0.0,
        (
            "The prompt does not clearly ask for the supported BRAKER3 workflow, protein-evidence workflow, or Exonerate chunk task.",
        ),
    )


def _missing_required_inputs(name: str, extracted_inputs: dict[str, object]) -> list[str]:
    """Return missing required prompt-derived inputs for one supported entry."""
    def is_missing(value: object) -> bool:
        if value in (None, ""):
            return True
        if isinstance(value, list) and not value:
            return True
        return False

    missing = [
        parameter.name
        for parameter in supported_entry_parameters(name)
        if parameter.required and is_missing(extracted_inputs.get(parameter.name))
    ]

    if name == SUPPORTED_WORKFLOW_NAME and not (
        extracted_inputs.get("rnaseq_bam_path") or extracted_inputs.get("protein_fasta_path")
    ):
        missing.append("rnaseq_bam_path or protein_fasta_path")
    return missing


def declined_downstream_stages(request: str) -> tuple[str, ...]:
    """Return the stable declined-stage labels mentioned in one prompt."""
    normalized_request = _normalize(request)
    positions: dict[str, int] = {}
    for keyword, label in DOWNSTREAM_STAGE_LABELS:
        index = normalized_request.find(keyword)
        if index == -1:
            continue
        if label not in positions or index < positions[label]:
            positions[label] = index
    return tuple(label for label, _ in sorted(positions.items(), key=lambda item: item[1]))


def showcase_limitations() -> tuple[str, ...]:
    """Return the hard interface limits for the showcase planner."""
    return SHOWCASE_LIMITATIONS


def _assumptions_for_target(name: str) -> tuple[str, ...]:
    """Return assumptions for the matched supported entry."""
    if name == SUPPORTED_WORKFLOW_NAME:
        return (
            "This prompt maps to the BRAKER3 ab initio stage only, not end-to-end annotation.",
            "BRAKER3 still needs `genome` plus at least one evidence input in practice: `rnaseq_bam_path`, `protein_fasta_path`, or both.",
            "Prompt paths are taken literally from the request text and are not auto-discovered.",
        )
    if name == SUPPORTED_PROTEIN_WORKFLOW_NAME:
        return (
            "This prompt maps to the protein-evidence alignment workflow only, not downstream EVM or later annotation stages.",
            "Protein FASTA inputs must be written explicitly in the prompt and are passed through in the order they appear.",
            "Prompt paths are taken literally from the request text and are not auto-discovered.",
        )
    if name == SUPPORTED_TASK_NAME:
        return (
            "This prompt maps to one Exonerate chunk-alignment task for ad hoc experimentation, not a full protein-evidence workflow.",
            "Prompt paths are taken literally from the request text and are not auto-discovered.",
            "The default Exonerate model remains `protein2genome` unless the prompt provides a different explicit model.",
        )
    raise KeyError(f"Unsupported showcase entry: {name}")


def _unsupported_plan(
    request: str,
    reason: str,
    rationale: tuple[str, ...],
    declined_stages: tuple[str, ...] = (),
) -> dict[str, object]:
    """Build the stable decline payload for unsupported or out-of-scope prompts."""
    return {
        "supported": False,
        "original_request": request,
        "matched_entry_name": None,
        "matched_entry_category": None,
        "matched_entry_description": None,
        "required_inputs": [],
        "optional_inputs": [],
        "extracted_inputs": {},
        "missing_required_inputs": [],
        "declined_downstream_stages": list(declined_stages),
        "assumptions": [
            "Only the showcase workflows and task are exposed through this server-first prompt interface.",
        ],
        "limitations": [reason, *showcase_limitations()],
        "confidence": 0.0,
        "rationale": list(rationale),
    }


def plan_request(request: str) -> dict[str, object]:
    """Plan one prompt for the narrow workflow-or-task showcase."""
    normalized_request = _normalize(request)
    downstream_hits = declined_downstream_stages(request)
    if downstream_hits:
        quoted_hits = ", ".join(f"`{stage}`" for stage in downstream_hits)
        return _unsupported_plan(
            request,
            reason=f"The prompt mentions downstream stages {quoted_hits}, which this showcase must decline explicitly.",
            rationale=(
                "The request goes beyond the supported BRAKER3 workflow, protein-evidence workflow, and Exonerate chunk task boundary.",
            ),
            declined_stages=downstream_hits,
        )

    matched_name, confidence, rationale = _classify_target(normalized_request)
    if matched_name is None:
        return _unsupported_plan(
            request,
            reason="The request does not clearly map to the supported workflow or task, so the showcase declines instead of guessing.",
            rationale=rationale,
        )

    entry = _supported_entry(matched_name)
    required_inputs, optional_inputs = split_entry_inputs(matched_name)
    prompt_paths = _extract_prompt_paths(request)
    if matched_name == SUPPORTED_WORKFLOW_NAME:
        extracted_inputs = _extract_braker_workflow_inputs(request, prompt_paths)
    elif matched_name == SUPPORTED_PROTEIN_WORKFLOW_NAME:
        extracted_inputs = _extract_protein_workflow_inputs(request, prompt_paths)
    else:
        extracted_inputs = _extract_task_inputs(request, prompt_paths)

    missing_inputs = _missing_required_inputs(matched_name, extracted_inputs)
    limitations = list(showcase_limitations())
    if matched_name == SUPPORTED_WORKFLOW_NAME:
        limitations.insert(0, "This match covers only the BRAKER3 ab initio annotation stage.")
    elif matched_name == SUPPORTED_PROTEIN_WORKFLOW_NAME:
        limitations.insert(0, "This match covers only the protein-evidence alignment workflow stage.")
    else:
        limitations.insert(0, "This match covers only one Exonerate chunk-alignment task invocation.")
    if missing_inputs:
        limitations.insert(
            0,
            f"The prompt is missing explicit required inputs for `{matched_name}`: {', '.join(missing_inputs)}.",
        )

    return {
        "supported": not missing_inputs,
        "original_request": request,
        "matched_entry_name": entry.name,
        "matched_entry_category": entry.category,
        "matched_entry_description": entry.description,
        "required_inputs": [asdict(field) for field in required_inputs],
        "optional_inputs": [asdict(field) for field in optional_inputs],
        "extracted_inputs": extracted_inputs,
        "missing_required_inputs": missing_inputs,
        "declined_downstream_stages": [],
        "assumptions": list(_assumptions_for_target(matched_name)),
        "limitations": limitations,
        "confidence": confidence,
        "rationale": list(rationale),
    }


def main() -> None:
    """Run the narrow planner from the command line and print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="Natural-language prompt to evaluate.")
    args = parser.parse_args()
    print(json.dumps(plan_request(args.request), indent=2))


if __name__ == "__main__":
    main()
