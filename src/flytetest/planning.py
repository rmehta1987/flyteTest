"""Deterministic prompt planning for the narrow FLyteTest MCP showcase.

This module reads a natural-language request, looks for explicit local files
and resource hints in the text, and matches the request against the small set
of supported showcase entries:

* `ab_initio_annotation_braker3`
* `protein_evidence_alignment`
* `exonerate_align_chunk`

The planner does not invent new workflow behavior. Instead, it decides whether
the request maps cleanly to one of the supported entries, what inputs can be
frozen from the prompt, what still needs to be resolved from manifests or result
bundles, and whether a metadata-only generated spec preview should be produced
for the typed-planning path.
"""

from __future__ import annotations

import ast
import argparse
import inspect
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from importlib import import_module
from pathlib import Path
from typing import Any, Literal

from flytetest.config import DEFAULT_SLURM_ACCOUNT
from flytetest.composition import compose_workflow_path
from flytetest.mcp_contract import (
    SHOWCASE_LIMITATIONS,
    SHOWCASE_TARGETS_BY_NAME,
    SUPPORTED_BUSCO_FIXTURE_TASK_NAME,
    SUPPORTED_PROTEIN_WORKFLOW_NAME,
    SUPPORTED_TASK_NAME,
    SUPPORTED_WORKFLOW_NAME,
)
from flytetest.registry import InterfaceField, RegistryEntry, get_entry
from flytetest.resolver import AssetResolver, LocalManifestAssetResolver, ResolutionResult
from flytetest.specs import (
    BindingPlan,
    GeneratedEntityRecord,
    ResourceSpec,
    RuntimeImageSpec,
    TypedFieldSpec,
    WorkflowEdgeSpec,
    WorkflowNodeSpec,
    WorkflowOutputBinding,
    WorkflowSpec,
)


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PATH_RE = re.compile(r"(?P<path>(?:\.{1,2}/|/|[A-Za-z0-9_-]+/)[A-Za-z0-9_./-]+)")
_FASTA_SUFFIXES = (".fa", ".faa", ".fasta", ".fna", ".fas")
TypedPlanningOutcome = Literal[
    "registered_task",
    "registered_workflow",
    "registered_stage_composition",
    "generated_workflow_spec",
    "declined",
]


@dataclass(frozen=True, slots=True)
class PlannedInput:
    """One planner-facing input field for a supported entry.

    It preserves the user-visible input name, the declared type, and the short
    registry description that explains what the field means in planning terms.
"""

    name: str
    type: str
    description: str


@dataclass(frozen=True, slots=True)
class EntryParameter:
    """One parameter from a supported task or workflow signature.

    It records whether the parameter is required so the planner can separate
    mandatory inputs from optional ones when building a prompt summary.
"""

    name: str
    required: bool


@dataclass(frozen=True, slots=True)
class PromptPath:
    """One explicit local path mention extracted from the prompt text.

    It keeps both the literal path text and the prompt context that surrounded
    it so later heuristics can tell whether a path was likely a genome, protein,
    BAM, or tool-image reference.
"""

    value: str
    context: str


@dataclass(frozen=True, slots=True)
class TypedPlanningGoal:
    """One biology-level target selected before resolver and registry matching.

    It captures the planner's decision about what the prompt is trying to do,
    which registry entries can satisfy that goal, which planner types should be
    resolved, and which assumptions or runtime bindings should travel with the
    frozen recipe.
"""

    name: str
    outcome: TypedPlanningOutcome
    target_entry_names: tuple[str, ...]
    required_planner_types: tuple[str, ...]
    produced_planner_types: tuple[str, ...]
    rationale: tuple[str, ...]
    analysis_goal: str
    generated_entity_id: str | None = None
    unresolved_runtime_requirements: tuple[str, ...] = field(default_factory=tuple)
    runtime_bindings: dict[str, object] = field(default_factory=dict)
    execution_profile: str | None = None
    resource_spec: ResourceSpec | None = None
    runtime_image: RuntimeImageSpec | None = None


def _normalize(text: str) -> str:
    """Normalize free text into lowercase alphanumeric tokens.

    Args:
        text: Prompt text or other free text being tokenized for matching.

    Returns:
        A space-separated lowercase token string that is easier to match
        against the planner's keyword heuristics.
"""
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _supported_entry(name: str) -> RegistryEntry:
    """Resolve one supported registry entry by name.

    Args:
        name: The registry entry name to look up in the showcase catalog.

    Returns:
        The registry entry metadata for the requested supported target.
"""
    if name not in SHOWCASE_TARGETS_BY_NAME:
        raise KeyError(f"Unsupported showcase entry: {name}")
    return get_entry(name)


def _parameters_from_source(name: str) -> tuple[EntryParameter, ...]:
    """Parse the checked-in source file when import-time reflection is unavailable.

    Args:
        name: The supported entry whose signature should be reconstructed.

    Returns:
        The ordered parameter list reconstructed from the checked-in source.
"""
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
    """Return supported entry parameters from imports or source fallback.

    Args:
        name: The supported entry whose callable signature should be inspected.

    Returns:
        The ordered parameters for the supported task or workflow.
"""
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
    """Split registry-defined entry inputs into required and optional groups.

    Args:
        name: The supported entry whose registry inputs should be grouped.

    Returns:
        A pair of tuples containing required and optional planner inputs.
"""
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
    """Strip trailing punctuation from one path-like prompt token.

    Args:
        raw_path: Path-like prompt text that may include trailing punctuation.

    Returns:
        The cleaned path text with punctuation removed from the right edge.
"""
    return raw_path.rstrip(".,);:'\"")


def _extract_prompt_paths(request: str) -> tuple[PromptPath, ...]:
    """Return explicit local path mentions with the prefix text that labels them.

    Args:
        request: The natural-language prompt being searched for path mentions.

    Returns:
        The explicit path mentions that appear to be written directly in the prompt.
"""
    matches: list[PromptPath] = []
    for match in _PATH_RE.finditer(request):
        path = _clean_path(match.group("path"))
        if "/" not in path:
            continue
        start = max(0, match.start() - 60)
        matches.append(PromptPath(value=path, context=request[start:match.start()].lower()))
    return tuple(matches)


def _is_bam_path(path: str) -> bool:
    """Return whether a prompt path looks like a BAM file.

    Args:
        path: A filesystem path or prompt mention being classified.

    Returns:
        ``True`` when the path ends with `.bam`.
"""
    return path.lower().endswith(".bam")


def _is_fasta_path(path: str) -> bool:
    """Return whether a prompt path looks like a FASTA file.

    Args:
        path: A filesystem path or prompt mention being classified.

    Returns:
        ``True`` when the path looks like a FASTA file, including gzipped FASTA.
"""
    lowered = path.lower()
    if lowered.endswith(".gz"):
        lowered = lowered[:-3]
    return lowered.endswith(_FASTA_SUFFIXES)


def _last_keyword_index(context: str, keywords: tuple[str, ...]) -> int:
    """Return the nearest keyword position from a short prompt prefix context.

    Args:
        context: Lowercase prompt context captured before the path mention.
        keywords: Keywords whose last position should be compared.

    Returns:
        The rightmost keyword match index, or ``-1`` when no keyword appears.
"""
    return max((context.rfind(keyword) for keyword in keywords), default=-1)


def _extract_braker_workflow_inputs(request: str, prompt_paths: tuple[PromptPath, ...]) -> dict[str, str]:
    """Map prompt-contained explicit paths to BRAKER3 workflow inputs.

    Args:
        request: The natural-language prompt being parsed for BRAKER3 inputs.
        prompt_paths: The explicit path mentions already extracted from the prompt.

    Returns:
        The BRAKER3 input mapping inferred from the prompt text.
"""
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
    """Map prompt-contained explicit paths to protein-evidence workflow inputs.

    Args:
        request: The natural-language prompt being parsed for protein-evidence inputs.
        prompt_paths: The explicit path mentions already extracted from the prompt.

    Returns:
        The protein-evidence input mapping inferred from the prompt text.
"""
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
    """Map prompt-contained explicit paths to the Exonerate chunk task inputs.

    Args:
        request: The natural-language prompt being parsed for Exonerate task inputs.
        prompt_paths: The explicit path mentions already extracted from the prompt.

    Returns:
        The task input mapping inferred from the prompt text.
"""
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


def _extract_busco_fixture_inputs(request: str, prompt_paths: tuple[PromptPath, ...]) -> dict[str, object]:
    """Build default runtime bindings for the M18 BUSCO fixture smoke."""
    extracted: dict[str, object] = {
        "proteins_fasta": "data/busco/test_data/eukaryota/genome.fna",
        "lineage_dataset": "auto-lineage",
        "busco_mode": "geno",
    }

    for mention in prompt_paths:
        path = mention.value
        if path.lower().endswith(".sif") and "busco" in mention.context:
            extracted.setdefault("busco_sif", path)
            continue
        if _is_fasta_path(path) and any(keyword in mention.context for keyword in ("busco", "fixture", "genome")):
            extracted["proteins_fasta"] = path

    cpu_match = re.search(r"\bbusco[_ -]?cpu\s*[:=]?\s*(\d+)\b", request, flags=re.IGNORECASE)
    if cpu_match:
        extracted["busco_cpu"] = int(cpu_match.group(1))

    lineage_match = re.search(r"\b(?:lineage|lineage_dataset)\s*[:=]?\s*([A-Za-z0-9_.-]+)\b", request, flags=re.IGNORECASE)
    if lineage_match:
        extracted["lineage_dataset"] = lineage_match.group(1)

    mode_match = re.search(r"\bbusco[_ -]?mode\s*[:=]?\s*([A-Za-z0-9_.-]+)\b", request, flags=re.IGNORECASE)
    if mode_match:
        extracted["busco_mode"] = mode_match.group(1)
    return extracted


def _coerce_resource_spec(value: Mapping[str, Any] | ResourceSpec | None) -> ResourceSpec | None:
    """Convert caller-supplied resource policy into the typed recipe shape.

    Args:
        value: A mapping, dataclass, or ``None`` describing a resource request.

    Returns:
        A normalized resource spec, or ``None`` when no resource policy exists.
"""
    if value is None:
        return None
    if isinstance(value, ResourceSpec):
        return value

    allowed_fields = {"cpu", "memory", "gpu", "queue", "account", "walltime", "execution_class", "notes"}
    kwargs: dict[str, Any] = {}
    for key in allowed_fields:
        if key not in value or value[key] in (None, ""):
            continue
        if key == "notes":
            notes_value = value[key]
            kwargs[key] = (
                (str(notes_value),)
                if isinstance(notes_value, str) or not isinstance(notes_value, Sequence)
                else tuple(str(note) for note in notes_value)
            )
        else:
            kwargs[key] = str(value[key])
    return ResourceSpec(**kwargs) if kwargs else None


def _coerce_runtime_image_spec(value: Mapping[str, Any] | RuntimeImageSpec | str | None) -> RuntimeImageSpec | None:
    """Convert caller-supplied runtime image policy into the typed recipe shape.

    Args:
        value: A mapping, dataclass, string path, or ``None`` describing an image policy.

    Returns:
        A normalized runtime-image spec, or ``None`` when no image policy exists.
"""
    if value is None or value == "":
        return None
    if isinstance(value, RuntimeImageSpec):
        return value
    if isinstance(value, str):
        if value.endswith((".sif", ".simg")):
            return RuntimeImageSpec(apptainer_image=value)
        return RuntimeImageSpec(container_image=value)

    allowed_fields = {"container_image", "apptainer_image", "runtime_assumptions", "compatibility_notes"}
    kwargs: dict[str, Any] = {}
    for key in allowed_fields:
        if key not in value or value[key] in (None, ""):
            continue
        if key in {"runtime_assumptions", "compatibility_notes"}:
            image_notes = value[key]
            kwargs[key] = (
                (str(image_notes),)
                if isinstance(image_notes, str) or not isinstance(image_notes, Sequence)
                else tuple(str(note) for note in image_notes)
            )
        else:
            kwargs[key] = str(value[key])
    return RuntimeImageSpec(**kwargs) if kwargs else None


def _merge_resource_specs(base: ResourceSpec | None, override: ResourceSpec | None) -> ResourceSpec | None:
    """Overlay explicit resource values on top of registry defaults.

    Args:
        base: The registry default resource spec, if one exists.
        override: The more specific prompt or caller override, if one exists.

    Returns:
        The merged resource spec, or whichever side is present.
"""
    if base is None:
        return override
    if override is None:
        return base
    return ResourceSpec(
        cpu=override.cpu or base.cpu,
        memory=override.memory or base.memory,
        gpu=override.gpu or base.gpu,
        queue=override.queue or base.queue,
        account=override.account or base.account,
        walltime=override.walltime or base.walltime,
        execution_class=override.execution_class or base.execution_class,
        notes=(*base.notes, *override.notes),
    )


def _extract_resource_spec_from_prompt(request: str) -> ResourceSpec | None:
    """Parse conservative resource mentions from prompt text into a ResourceSpec.

    Args:
        request: The natural-language prompt being searched for resource hints.

    Returns:
        A parsed resource spec when the prompt names one clearly enough.
"""
    cpu: str | None = None
    memory: str | None = None
    queue: str | None = None
    account: str | None = None
    walltime: str | None = None

    cpu_match = re.search(r"\b(\d+)\s*(?:cpu|cpus|cores?)\b", request, flags=re.IGNORECASE)
    if cpu_match:
        cpu = cpu_match.group(1)

    memory_match = re.search(
        r"\b(?:memory|mem|ram)\s*[:=]?\s*(\d+\s*(?:gib|gb|gi|mib|mb|mi))\b|\b(\d+\s*(?:gib|gb|gi|mib|mb|mi))\s*(?:memory|mem|ram)\b",
        request,
        flags=re.IGNORECASE,
    )
    if memory_match:
        memory = (memory_match.group(1) or memory_match.group(2)).replace(" ", "")

    queue_match = re.search(r"\b(?:queue|partition)\s*[:=]?\s*([A-Za-z0-9_.-]+)\b", request, flags=re.IGNORECASE)
    if queue_match:
        queue = queue_match.group(1)

    account_match = re.search(r"\baccount\s*[:=]?\s*([A-Za-z0-9_.-]+)\b", request, flags=re.IGNORECASE)
    if account_match:
        account = account_match.group(1)

    walltime_match = re.search(
        r"\b(?:walltime|wall time|time limit)\s*[:=]?\s*([0-9]+(?::[0-9]{2}){1,2}|[0-9]+[hm])\b",
        request,
        flags=re.IGNORECASE,
    )
    if walltime_match:
        walltime = walltime_match.group(1)

    if not any((cpu, memory, queue, account, walltime)):
        return None
    notes = (
        "Scheduler-oriented fields are frozen for review and replay before an executor consumes the recipe.",
    )
    return ResourceSpec(cpu=cpu, memory=memory, queue=queue, account=account, walltime=walltime, notes=notes)


def _slurm_resource_spec_defaults(resource_spec: ResourceSpec | None) -> ResourceSpec | None:
    """Attach cluster-specific Slurm defaults to a selected resource spec.

    Args:
        resource_spec: The resource spec selected from registry, prompt, or caller input.

    Returns:
        A resource spec that carries a default Slurm account when needed.
"""
    if resource_spec is None:
        return ResourceSpec(account=DEFAULT_SLURM_ACCOUNT)
    if resource_spec.execution_class not in (None, "", "slurm"):
        return resource_spec
    if resource_spec.account:
        return resource_spec
    return replace(resource_spec, account=DEFAULT_SLURM_ACCOUNT)


def _extract_execution_profile_from_prompt(request: str) -> str | None:
    """Parse an explicit execution profile name from the prompt when present.

    Args:
        request: The natural-language prompt being searched for a profile name.

    Returns:
        The lowercased execution profile name, or ``None`` when not named clearly.
"""
    profile_match = re.search(
        r"\b(?:execution profile|profile)\s*[:=]?\s*([A-Za-z0-9_.-]+)\b",
        request,
        flags=re.IGNORECASE,
    )
    if profile_match:
        return _clean_path(profile_match.group(1)).lower()
    if re.search(r"\bslurm\b", request, flags=re.IGNORECASE):
        return "slurm"
    return None


def _extract_runtime_image_from_prompt(request: str) -> RuntimeImageSpec | None:
    """Parse a global runtime image request from prompt text when clearly labeled.

    Args:
        request: The natural-language prompt being searched for runtime-image hints.

    Returns:
        A runtime-image spec when the prompt names an image clearly enough.
"""
    image_match = re.search(
        r"\b(?:runtime image|container image|apptainer image)\s*[:=]?\s*([A-Za-z0-9_./:-]+)",
        request,
        flags=re.IGNORECASE,
    )
    if not image_match:
        return None
    return _coerce_runtime_image_spec(_clean_path(image_match.group(1)))


def _registry_default_resource_spec(entry: RegistryEntry) -> ResourceSpec | None:
    """Return the registry's default local resource policy for one entry.

    Args:
        entry: The registry entry whose compatibility defaults should be read.

    Returns:
        The registry's default resource policy, when one is declared.
"""
    resources = entry.compatibility.execution_defaults.get("resources")
    return _coerce_resource_spec(resources) if isinstance(resources, Mapping) else None


def _select_execution_policy(
    goal: TypedPlanningGoal,
    *,
    request: str,
    resource_request: Mapping[str, Any] | ResourceSpec | None,
    execution_profile: str | None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None,
) -> tuple[str, ResourceSpec | None, RuntimeImageSpec | None, tuple[str, ...], tuple[str, ...]]:
    """Resolve profile, resources, and runtime image policy for a typed goal.

    Args:
        goal: The typed planning goal being prepared for freezing.
        request: The natural-language prompt being evaluated.
        resource_request: Caller-supplied compute resource policy or override.
        execution_profile: Caller-supplied execution profile, if any.
        runtime_image: Caller-supplied runtime image policy or override.

    Returns:
        The selected execution profile, resource policy, runtime image policy,
        unresolved resource requirements, and assumptions.
"""
    entries = tuple(get_entry(entry_name) for entry_name in goal.target_entry_names)
    default_profile = str(entries[0].compatibility.execution_defaults.get("profile", "local")) if entries else "local"
    supported_profiles = set(entries[0].compatibility.supported_execution_profiles if entries else ("local",))
    for entry in entries[1:]:
        supported_profiles.intersection_update(entry.compatibility.supported_execution_profiles)
    if not supported_profiles:
        supported_profiles.add("local")

    prompt_profile = _extract_execution_profile_from_prompt(request)
    selected_profile = _clean_path(execution_profile or prompt_profile or default_profile or "local").lower()
    unresolved: list[str] = []
    assumptions: list[str] = []
    if selected_profile not in supported_profiles:
        unresolved.append(
            f"Execution profile `{selected_profile}` is not supported for `{goal.name}`; supported profiles: {', '.join(sorted(supported_profiles))}."
        )

    registry_default = _registry_default_resource_spec(entries[0]) if entries else None
    prompt_resources = _extract_resource_spec_from_prompt(request)
    caller_resources = _coerce_resource_spec(resource_request)
    selected_resources = _merge_resource_specs(_merge_resource_specs(registry_default, prompt_resources), caller_resources)
    if selected_resources is not None and selected_profile != (selected_resources.execution_class or selected_profile):
        selected_resources = replace(selected_resources, execution_class=selected_profile)
    if selected_profile == "slurm":
        selected_resources = _slurm_resource_spec_defaults(selected_resources)

    selected_image = _coerce_runtime_image_spec(runtime_image) or _extract_runtime_image_from_prompt(request)
    if selected_resources is not None:
        assumptions.append(
            "ResourceSpec is frozen into the recipe for review and replay before local or Slurm execution consumes it."
        )
    if selected_image is not None:
        assumptions.append(
            "RuntimeImageSpec is frozen into the recipe as policy metadata; existing workflow inputs still control tool-specific SIF arguments."
        )
    return selected_profile, selected_resources, selected_image, tuple(unresolved), tuple(assumptions)


def _classify_target(request: str) -> tuple[str | None, float, tuple[str, ...]]:
    """Classify the prompt as one supported workflow, task, or unsupported.

    Args:
        request: The natural-language prompt being classified.

    Returns:
        The selected showcase entry name, confidence, and rationale.
"""
    normalized_request = _normalize(_PATH_RE.sub(" ", request))
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
    """Return missing required prompt-derived inputs for one supported entry.

    Args:
        name: The supported entry being checked.
        extracted_inputs: The prompt-derived inputs already recovered for that entry.

    Returns:
        The required inputs that were not found in the prompt.
"""
    def is_missing(value: object) -> bool:
        """Return whether one extracted prompt value should count as absent.

        Args:
            value: One extracted prompt value to evaluate.

        Returns:
            ``True`` when the value is empty or missing.
"""
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


def declined_downstream_stages(_request: str) -> tuple[str, ...]:
    """Return no downstream blocklist hits after the MCP recipe cutover.

    Args:
        _request: Present for interface compatibility with older call sites.

    Returns:
        An empty tuple because this showcase no longer blocks downstream stages here.
"""
    return ()


def showcase_limitations() -> tuple[str, ...]:
    """Return the hard interface limits for the showcase planner.

    Returns:
        The static limitations that define the current showcase surface.
"""
    return SHOWCASE_LIMITATIONS


def _typed_field(name: str, planner_type_name: str, description: str) -> TypedFieldSpec:
    """Build one planner-facing field for a typed workflow spec preview.

    Args:
        name: The input or output field name to expose in the preview.
        planner_type_name: The planner type that should be attached to the field.
        description: Short human-readable text for the planning summary.

    Returns:
        A typed field spec suitable for frozen workflow metadata.
"""
    return TypedFieldSpec(
        name=name,
        type_name=planner_type_name,
        description=description,
        planner_type_names=(planner_type_name,),
    )


def _planning_goal_for_typed_request(request: str) -> TypedPlanningGoal | None:
    """Classify a prompt into one broader typed-planning goal when possible.

    Args:
        request: The natural-language prompt being mapped into a typed goal.

    Returns:
        A typed planning goal, or ``None`` when the prompt does not match one.
"""
    normalized_request = _normalize(request)

    if any(keyword in normalized_request for keyword in ("variant calling", "snv", "snp", "vcf")):
        return None

    if (
        "busco" in normalized_request
        and ("m18" in normalized_request or "milestone 18" in normalized_request or "fixture" in normalized_request)
        and ("genome" in normalized_request or "eukaryota" in normalized_request or "fixture" in normalized_request)
    ):
        return TypedPlanningGoal(
            name=SUPPORTED_BUSCO_FIXTURE_TASK_NAME,
            outcome="registered_task",
            target_entry_names=(SUPPORTED_BUSCO_FIXTURE_TASK_NAME,),
            required_planner_types=(),
            produced_planner_types=("Dir",),
            rationale=(
                "The prompt asks for the Milestone 18 BUSCO eukaryota fixture smoke.",
                "That maps to the registered BUSCO task with explicit fixture-native runtime bindings.",
            ),
            analysis_goal="Run the M18 BUSCO genome-mode fixture smoke from a frozen recipe.",
            runtime_bindings=_extract_busco_fixture_inputs(request, _extract_prompt_paths(request)),
        )

    matched_name, _, _ = _classify_target(request)
    if matched_name is not None:
        prompt_paths = _extract_prompt_paths(request)
        if matched_name == SUPPORTED_WORKFLOW_NAME:
            extracted_inputs = _extract_braker_workflow_inputs(request, prompt_paths)
        elif matched_name == SUPPORTED_PROTEIN_WORKFLOW_NAME:
            extracted_inputs = _extract_protein_workflow_inputs(request, prompt_paths)
        else:
            extracted_inputs = _extract_task_inputs(request, prompt_paths)
        if not _missing_required_inputs(matched_name, extracted_inputs):
            entry = get_entry(matched_name)
            target_kind = "registered_task" if entry.category == "task" else "registered_workflow"
            produced_types = entry.compatibility.produced_planner_types or tuple(field.type for field in entry.outputs)
            return TypedPlanningGoal(
                name=matched_name,
                outcome=target_kind,
                target_entry_names=(matched_name,),
                required_planner_types=(),
                produced_planner_types=produced_types,
                rationale=(
                    f"The prompt maps to the day-one MCP target `{matched_name}`.",
                    "Prompt-contained local paths are frozen as runtime bindings in the saved recipe.",
                ),
                analysis_goal=f"Run the registered {entry.category} `{matched_name}` from a frozen recipe.",
                runtime_bindings=dict(extracted_inputs),
            )

    asks_for_generated_spec = "workflow spec" in normalized_request or "generated spec" in normalized_request
    asks_for_repeat_then_qc = (
        ("repeat" in normalized_request or "repeat filtering" in normalized_request)
        and ("busco" in normalized_request or "quality" in normalized_request or "qc" in normalized_request)
    )
    if asks_for_generated_spec or asks_for_repeat_then_qc:
        # In this repo, QC means quality assessment of the repeat-filtered
        # protein result bundle. BUSCO is the current implementation of that
        # quality-assessment stage, and later reviewable checks can reuse the
        # same planner target shape.
        return TypedPlanningGoal(
            name="repeat_filter_then_busco_qc",
            outcome="generated_workflow_spec",
            target_entry_names=("annotation_repeat_filtering", "annotation_qc_busco"),
            required_planner_types=("ConsensusAnnotation",),
            produced_planner_types=("QualityAssessmentTarget",),
            rationale=(
                "The prompt asks for a multi-stage repeat-filtering and QC bundle that is not a checked-in single workflow.",
                "The planner can describe a saved generated WorkflowSpec preview from existing registered stages.",
            ),
            analysis_goal="Prepare a generated spec preview for repeat filtering followed by BUSCO QC.",
            generated_entity_id="generated::repeat_filter_then_busco_qc::preview",
            unresolved_runtime_requirements=(
                "`repeatmasker_out` must still be supplied before execution.",
                "`busco_lineages_text` must still be supplied before execution.",
                "Milestone 5 creates a metadata-only spec preview and does not persist or execute it yet.",
            ),
        )

    if "consensus" in normalized_request and ("evm" in normalized_request or "annotation" in normalized_request):
        return TypedPlanningGoal(
            name="consensus_annotation_from_registered_stages",
            outcome="registered_stage_composition",
            target_entry_names=("consensus_annotation_evm_prep", "consensus_annotation_evm"),
            required_planner_types=("TranscriptEvidenceSet", "ProteinEvidenceSet", "AnnotationEvidenceSet"),
            produced_planner_types=("ConsensusAnnotation",),
            rationale=(
                "The prompt asks for consensus annotation through the EVM boundary.",
                "The registered pre-EVM preparation and EVM execution workflows form the reviewed composition path.",
            ),
            analysis_goal="Compose reviewed pre-EVM preparation and EVM execution stages.",
            unresolved_runtime_requirements=(
                "EVM script paths and optional weights remain normal runtime bindings.",
            ),
        )

    if "agat" in normalized_request and any(
        keyword in normalized_request
        for keyword in ("cleanup", "clean up", "cleaned", "submission cleanup", "ncbi")
    ):
        return TypedPlanningGoal(
            name="annotation_postprocess_agat_cleanup",
            outcome="registered_workflow",
            target_entry_names=("annotation_postprocess_agat_cleanup",),
            required_planner_types=("QualityAssessmentTarget",),
            produced_planner_types=("QualityAssessmentTarget",),
            rationale=(
                "The prompt asks for AGAT cleanup on the post-conversion GFF3 boundary.",
                "That maps to the registered deterministic cleanup workflow while keeping table2asn deferred.",
            ),
            analysis_goal="Run the registered AGAT cleanup workflow.",
        )

    if "agat" in normalized_request and any(
        keyword in normalized_request
        for keyword in ("convert", "conversion", "normalize", "standardize", "gxf2gxf")
    ):
        return TypedPlanningGoal(
            name="annotation_postprocess_agat_conversion",
            outcome="registered_workflow",
            target_entry_names=("annotation_postprocess_agat_conversion",),
            required_planner_types=("QualityAssessmentTarget",),
            produced_planner_types=("QualityAssessmentTarget",),
            rationale=(
                "The prompt asks for AGAT conversion or normalization on the EggNOG-annotated GFF3 boundary.",
                "That maps to the registered AGAT conversion workflow while keeping cleanup as a separate follow-on slice before table2asn.",
            ),
            analysis_goal="Run the registered AGAT conversion workflow.",
        )

    if "agat" in normalized_request and any(
        keyword in normalized_request for keyword in ("statistics", "statistic", "stats")
    ):
        return TypedPlanningGoal(
            name="annotation_postprocess_agat",
            outcome="registered_workflow",
            target_entry_names=("annotation_postprocess_agat",),
            required_planner_types=("QualityAssessmentTarget",),
            produced_planner_types=("QualityAssessmentTarget",),
            rationale=(
                "The prompt asks for AGAT post-processing on the EggNOG-annotated GFF3 boundary.",
                "That maps to the registered AGAT statistics workflow while keeping conversion and cleanup as explicit separate slices.",
            ),
            analysis_goal="Run the registered AGAT post-processing workflow.",
        )

    if "eggnog" in normalized_request or "functional annotation" in normalized_request:
        # EggNOG is modeled as a downstream quality-assessment style stage
        # because it consumes the cleaned annotation target produced by the
        # prior pipeline slice rather than raw user input. The stage still
        # operates on the repeat-filtered protein boundary.
        return TypedPlanningGoal(
            name="annotation_functional_eggnog",
            outcome="registered_workflow",
            target_entry_names=("annotation_functional_eggnog",),
            required_planner_types=("QualityAssessmentTarget",),
            produced_planner_types=("QualityAssessmentTarget",),
            rationale=(
                "The prompt asks for post-BUSCO functional annotation.",
                "That maps to the registered EggNOG functional-annotation workflow when a reviewable quality target can be resolved.",
            ),
            analysis_goal="Run the registered EggNOG functional-annotation workflow.",
            unresolved_runtime_requirements=(
                "`eggnog_data_dir` must still be supplied before execution.",
                "`eggnog_database` should be selected explicitly for the chosen taxonomic scope.",
            ),
        )

    if "busco" in normalized_request or "quality assessment" in normalized_request:
        # BUSCO is the current canonical quality-assessment stage. It measures
        # completeness of the repeat-filtered protein set before later
        # functional annotation or AGAT post-processing steps.
        return TypedPlanningGoal(
            name="annotation_qc_busco",
            outcome="registered_workflow",
            target_entry_names=("annotation_qc_busco",),
            required_planner_types=("QualityAssessmentTarget",),
            produced_planner_types=("QualityAssessmentTarget",),
            rationale=(
                "The prompt asks for BUSCO annotation quality assessment.",
                "That maps to the registered BUSCO QC workflow when a QC target can be resolved.",
            ),
            analysis_goal="Run the registered BUSCO QC workflow from a repeat-filtered annotation target.",
        )

    if "protein evidence alignment" in normalized_request or (
        "protein evidence" in normalized_request and "alignment" in normalized_request
    ):
        return TypedPlanningGoal(
            name="protein_evidence_alignment",
            outcome="registered_workflow",
            target_entry_names=("protein_evidence_alignment",),
            required_planner_types=("ReferenceGenome", "ProteinEvidenceSet"),
            produced_planner_types=("ProteinEvidenceSet",),
            rationale=(
                "The prompt asks for the protein-evidence alignment stage.",
                "That maps to the registered protein_evidence_alignment workflow.",
            ),
            analysis_goal="Run the registered protein-evidence alignment workflow.",
        )

    if "transcript evidence" in normalized_request:
        return TypedPlanningGoal(
            name="transcript_evidence_generation",
            outcome="registered_workflow",
            target_entry_names=("transcript_evidence_generation",),
            required_planner_types=("ReferenceGenome", "ReadSet"),
            produced_planner_types=("TranscriptEvidenceSet",),
            rationale=(
                "The prompt asks for transcript evidence generation.",
                "That maps to the registered transcript_evidence_generation workflow when reads and genome resolve.",
            ),
            analysis_goal="Run the registered transcript-evidence generation workflow.",
        )

    if matched_name is not None:
        return None

    # Try registry-based composition when the prompt is broader than the direct matches.
    composition_goal = _try_composition_fallback(request, normalized_request)
    if composition_goal is not None:
        return composition_goal

    return None


def _try_composition_fallback(request: str, normalized_request: str) -> TypedPlanningGoal | None:
    """Look for a registry-based composition when direct matches do not fit.

    Args:
        request: The original natural-language prompt.
        normalized_request: The lowercase, punctuation-stripped version of the request.

    Returns:
        A generated `TypedPlanningGoal` when a valid composition path is found,
        or ``None`` if the prompt does not fit this route.
    """
    if not _allows_composition_fallback(normalized_request):
        return None

    from flytetest.registry import REGISTRY_ENTRIES

    # Use entries that are allowed to seed a composed workflow.
    synthesis_eligible = [
        entry for entry in REGISTRY_ENTRIES
        if entry.compatibility.synthesis_eligible
    ]

    if not synthesis_eligible:
        return None

    # Try short paths that end in one of the supported biology targets.
    target_output_types = (
        "QualityAssessmentTarget",
        "ConsensusAnnotation",
        "ProteinEvidenceSet",
        "TranscriptEvidenceSet",
        "AnnotationEvidenceSet",
    )

    for entry in synthesis_eligible:
        for target_type in target_output_types:
            path, decline_reason = compose_workflow_path(
                entry.name,
                target_output_type=target_type,
                max_depth=5,
            )
            if path and decline_reason is None and len(path) >= 1:
                required_types = entry.compatibility.accepted_planner_types or ()
                produced_types = entry.compatibility.produced_planner_types or ()

                return TypedPlanningGoal(
                    name=f"composition_{entry.name}_to_{target_type.lower()}",
                    outcome="generated_workflow_spec",
                    target_entry_names=path,
                    required_planner_types=required_types,
                    produced_planner_types=produced_types,
                    rationale=(
                        f"The prompt asks for annotation workflow processing that was not a hardcoded pattern.",
                        f"The planner found a valid registered-stage path: {' -> '.join(path)}.",
                        "This composition requires explicit user approval before execution (Milestone 19 gating pending).",
                    ),
                    analysis_goal=f"Compose and execute a workflow from {entry.name} toward {target_type} output.",
                    generated_entity_id=f"generated::composition_{entry.name}_{int(len(path))}",
                    unresolved_runtime_requirements=(
                        "This generated composition is metadata-only and requires explicit approval from the user.",
                        "Composition was discovered from registered stages under the Milestone 15 rules.",
                        "Milestone 19 caching and resumability may affect final execution.",
                    ),
                )

    return None


def _allows_composition_fallback(normalized_request: str) -> bool:
    """Return whether a prompt is specific enough for composition fallback.

    Registry traversal is deliberately conservative: it is a preview path for
    broad biology workflow requests, not a way to reinterpret arbitrary prompts
    or known day-one targets that simply missed required path bindings.

    Args:
        normalized_request: The lowercase, tokenized prompt text.

    Returns:
        ``True`` when the prompt includes both a biology signal and a broad
        workflow-composition signal.
    """
    biology_terms = (
        "agat",
        "annotation",
        "braker",
        "busco",
        "eggnog",
        "evidence",
        "evm",
        "genome",
        "pasa",
        "protein",
        "quality",
        "qc",
        "repeat",
        "rna",
        "transcript",
    )
    workflow_terms = (
        "chain",
        "compose",
        "composition",
        "data",
        "downstream",
        "multi stage",
        "multi-stage",
        "pipeline",
        "process",
        "workflow",
    )
    return any(term in normalized_request for term in biology_terms) and any(
        term in normalized_request for term in workflow_terms
    )


def _serialized_resolved_value(result: ResolutionResult) -> object:
    """Return a JSON-compatible representation of one resolved planner value.

    Args:
        result: The resolution result that selected a planner-facing value.

    Returns:
        A JSON-compatible representation of the selected planner value.
"""
    value = result.resolved_value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


def _resolve_typed_goal_inputs(
    goal: TypedPlanningGoal,
    *,
    explicit_bindings: Mapping[str, Any],
    manifest_sources: Sequence[Path | Mapping[str, Any]],
    result_bundles: Sequence[Any],
    resolver: AssetResolver,
) -> tuple[dict[str, object], dict[str, object], tuple[str, ...], tuple[str, ...]]:
    """Resolve the planner-facing inputs required by one typed goal.

    Args:
        goal: The typed planning goal whose planner inputs must be resolved.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        result_bundles: Result bundles that can be adapted back into planner types.
        resolver: The resolver implementation used to discover planner inputs.

    Returns:
        The resolved planner inputs, source labels, missing requirements, and assumptions.
"""
    resolved_inputs: dict[str, object] = {}
    source_labels: dict[str, object] = {}
    unresolved_requirements: list[str] = []
    assumptions: list[str] = []

    for planner_type_name in goal.required_planner_types:
        result = resolver.resolve(
            planner_type_name,
            explicit_bindings=explicit_bindings,
            manifest_sources=manifest_sources,
            result_bundles=result_bundles,
        )
        assumptions.extend(assumption for assumption in result.assumptions if assumption not in assumptions)
        if result.is_resolved:
            resolved_inputs[planner_type_name] = _serialized_resolved_value(result)
            source_labels[planner_type_name] = {
                "kind": result.selected_source.kind,
                "label": result.selected_source.label,
            }
            continue
        unresolved_requirements.extend(result.unresolved_requirements)

    return resolved_inputs, source_labels, tuple(unresolved_requirements), tuple(assumptions)


def _workflow_spec_for_typed_goal(goal: TypedPlanningGoal, *, source_prompt: str) -> WorkflowSpec | None:
    """Build a metadata-only workflow spec preview for one typed planning goal.

    Args:
        goal: The typed planning goal being turned into frozen metadata.
        source_prompt: The original natural-language prompt for provenance.

    Returns:
        A metadata-only workflow spec preview, or ``None`` when the goal is unsupported.
"""
    entries = tuple(get_entry(entry_name) for entry_name in goal.target_entry_names)
    inputs = tuple(
        _typed_field(planner_type_name, planner_type_name, f"Resolved planner input `{planner_type_name}`.")
        for planner_type_name in goal.required_planner_types
    )
    outputs = tuple(
        _typed_field(planner_type_name, planner_type_name, f"Planned output `{planner_type_name}`.")
        for planner_type_name in goal.produced_planner_types
    )

    if goal.outcome in {"registered_task", "registered_workflow"}:
        entry = entries[0]
        selection_mode = "registered_task" if goal.outcome == "registered_task" else "registered_workflow"
        return WorkflowSpec(
            name=f"select_{entry.name}",
            analysis_goal=goal.analysis_goal,
            inputs=inputs,
            outputs=outputs,
            nodes=(
                WorkflowNodeSpec(
                    name=entry.name,
                    kind=entry.category,
                    reference_name=entry.name,
                    description=f"Direct selection of registered {entry.category} `{entry.name}`.",
                    output_names=tuple(field.name for field in entry.outputs),
                ),
            ),
            edges=(),
            reusable_registered_refs=(entry.name,),
            final_output_bindings=(
                WorkflowOutputBinding(
                    output_name=entry.outputs[0].name,
                    source_node=entry.name,
                    source_output=entry.outputs[0].name,
                    description="Pass through the registered workflow output bundle.",
                ),
            ),
            default_execution_profile=entry.compatibility.execution_defaults.get("profile", "local"),
            replay_metadata={"selection_mode": selection_mode},
        )

    if goal.outcome == "registered_stage_composition":
        prep_entry, execute_entry = entries
        return WorkflowSpec(
            name=goal.name,
            analysis_goal=goal.analysis_goal,
            inputs=inputs,
            outputs=outputs,
            nodes=(
                WorkflowNodeSpec(
                    name="prep",
                    kind="workflow",
                    reference_name=prep_entry.name,
                    description=f"Run registered stage `{prep_entry.name}`.",
                    input_bindings={
                        "pasa_results": "inputs.TranscriptEvidenceSet",
                        "protein_evidence_results": "inputs.ProteinEvidenceSet",
                        "transdecoder_results": "inputs.AnnotationEvidenceSet",
                        "braker3_results": "inputs.AnnotationEvidenceSet",
                    },
                    output_names=tuple(field.name for field in prep_entry.outputs),
                ),
                WorkflowNodeSpec(
                    name="execute",
                    kind="workflow",
                    reference_name=execute_entry.name,
                    description=f"Run registered stage `{execute_entry.name}` from the prepared EVM bundle.",
                    input_bindings={"evm_prep_results": "prep.results_dir"},
                    output_names=tuple(field.name for field in execute_entry.outputs),
                ),
            ),
            edges=(
                WorkflowEdgeSpec(
                    source_node="prep",
                    source_output=prep_entry.outputs[0].name,
                    target_node="execute",
                    target_input=execute_entry.inputs[0].name,
                ),
            ),
            ordering_constraints=("prep before execute",),
            reusable_registered_refs=goal.target_entry_names,
            final_output_bindings=(
                WorkflowOutputBinding(
                    output_name=execute_entry.outputs[0].name,
                    source_node="execute",
                    source_output=execute_entry.outputs[0].name,
                    description="Final consensus annotation result bundle.",
                ),
            ),
            default_execution_profile="local",
            replay_metadata={"selection_mode": "registered_stage_composition"},
        )

    if goal.outcome == "generated_workflow_spec":
        generated_record = GeneratedEntityRecord(
            generated_entity_id=goal.generated_entity_id or f"generated::{goal.name}",
            source_prompt=source_prompt,
            assumptions=(
                "This is a metadata-only generated spec preview in Milestone 5.",
                "The preview references registered stages and does not generate new task code.",
            ),
            selected_execution_profile="local",
            referenced_registered_building_blocks=goal.target_entry_names,
            created_at="not_persisted_in_milestone_5",
            replay_metadata={"workflow_spec_version": "preview-v1"},
        )

        # Handle both hardcoded repeat+BUSCO and composition-generated multi-stage workflows
        if len(entries) == 2 and goal.name == "repeat_filter_then_busco_qc":
            # Legacy hardcoded repeat_filter_then_busco_qc spec
            repeat_entry, qc_entry = entries
            return WorkflowSpec(
                name=goal.name,
                analysis_goal=goal.analysis_goal,
                inputs=inputs,
                outputs=outputs,
                nodes=(
                    WorkflowNodeSpec(
                        name="repeat_filtering",
                        kind="workflow",
                        reference_name=repeat_entry.name,
                        description=f"Run registered stage `{repeat_entry.name}`.",
                        input_bindings={"pasa_update_results": "inputs.ConsensusAnnotation"},
                        output_names=tuple(field.name for field in repeat_entry.outputs),
                    ),
                    WorkflowNodeSpec(
                        name="busco_qc",
                        kind="workflow",
                        reference_name=qc_entry.name,
                        description=f"Run registered stage `{qc_entry.name}` from repeat-filtered outputs.",
                        input_bindings={"repeat_filter_results": "repeat_filtering.results_dir"},
                        output_names=tuple(field.name for field in qc_entry.outputs),
                    ),
                ),
                edges=(
                    WorkflowEdgeSpec(
                        source_node="repeat_filtering",
                        source_output=repeat_entry.outputs[0].name,
                        target_node="busco_qc",
                        target_input=qc_entry.inputs[0].name,
                    ),
                ),
                ordering_constraints=("repeat_filtering before busco_qc",),
                reusable_registered_refs=goal.target_entry_names,
                final_output_bindings=(
                    WorkflowOutputBinding(
                        output_name=qc_entry.outputs[0].name,
                        source_node="busco_qc",
                        source_output=qc_entry.outputs[0].name,
                        description="BUSCO QC result bundle from the generated spec preview.",
                    ),
                ),
                default_execution_profile="local",
                replay_metadata={"selection_mode": "generated_workflow_spec_preview"},
                generated_entity_record=generated_record,
            )
        else:
            # Generic composition-generated multi-stage workflow
            nodes = []
            edges = []
            ordering_constraints = []

            for i, entry in enumerate(entries):
                node_name = f"stage_{i}_{entry.name}"
                input_bindings = {}

                # First stage gets inputs from workflow inputs
                if i == 0:
                    for input_field in entry.inputs:
                        # Try to find matching planner types in goal inputs
                        for planner_type in goal.required_planner_types:
                            if planner_type.lower() in input_field.type.lower() or input_field.type.lower() in planner_type.lower():
                                input_bindings[input_field.name] = f"inputs.{planner_type}"
                                break
                else:
                    # Subsequent stages get outputs from previous stage
                    prev_entry = entries[i - 1]
                    prev_node_name = f"stage_{i-1}_{prev_entry.name}"
                    if prev_entry.outputs:
                        input_bindings[entry.inputs[0].name if entry.inputs else "target"] = \
                            f"{prev_node_name}.{prev_entry.outputs[0].name}"

                nodes.append(WorkflowNodeSpec(
                    name=node_name,
                    kind="workflow",
                    reference_name=entry.name,
                    description=f"Run registered stage `{entry.name}`.",
                    input_bindings=input_bindings,
                    output_names=tuple(field.name for field in entry.outputs),
                ))

                # Create edge from previous stage
                if i > 0:
                    prev_entry = entries[i - 1]
                    prev_node_name = f"stage_{i-1}_{prev_entry.name}"
                    if prev_entry.outputs and entry.inputs:
                        edges.append(WorkflowEdgeSpec(
                            source_node=prev_node_name,
                            source_output=prev_entry.outputs[0].name,
                            target_node=node_name,
                            target_input=entry.inputs[0].name,
                        ))
                        ordering_constraints.append(f"{prev_node_name} before {node_name}")

            # Final output comes from last stage
            last_entry = entries[-1]
            last_node_name = f"stage_{len(entries)-1}_{last_entry.name}"
            final_output_name = last_entry.outputs[0].name if last_entry.outputs else "results"

            return WorkflowSpec(
                name=goal.name,
                analysis_goal=goal.analysis_goal,
                inputs=inputs,
                outputs=outputs,
                nodes=tuple(nodes),
                edges=tuple(edges),
                ordering_constraints=tuple(ordering_constraints),
                reusable_registered_refs=goal.target_entry_names,
                final_output_bindings=(
                    WorkflowOutputBinding(
                        output_name=final_output_name,
                        source_node=last_node_name,
                        source_output=final_output_name,
                        description="Final workflow output bundle from composed stages.",
                    ),
                ),
                default_execution_profile="local",
                replay_metadata={"selection_mode": "registry_constrained_composition"},
                generated_entity_record=generated_record,
            )

    return None



def _binding_plan_for_typed_goal(
    goal: TypedPlanningGoal,
    *,
    resolved_inputs: Mapping[str, object],
    source_labels: Mapping[str, object],
    unresolved_requirements: tuple[str, ...],
    assumptions: tuple[str, ...],
) -> BindingPlan:
    """Build the metadata-only binding record for a typed planning result.

    Args:
        goal: The typed planning goal being frozen into a binding plan.
        resolved_inputs: Typed planner values resolved before recipe freezing.
        source_labels: Source metadata describing where each resolved value came from.
        unresolved_requirements: Planner or runtime requirements that still need attention.
        assumptions: Assumptions that should travel with the frozen plan.

    Returns:
        A metadata-only binding plan for the selected typed goal.
"""
    if goal.outcome == "generated_workflow_spec":
        target_kind = "generated_workflow"
    elif goal.outcome == "registered_task":
        target_kind = "task"
    else:
        target_kind = "workflow"
    return BindingPlan(
        target_name=goal.name,
        target_kind=target_kind,
        explicit_user_bindings=dict(resolved_inputs),
        resolved_prior_assets=dict(source_labels),
        manifest_derived_paths={
            planner_type_name: source
            for planner_type_name, source in source_labels.items()
            if isinstance(source, Mapping) and source.get("kind") == "manifest"
        },
        execution_profile=goal.execution_profile or "local",
        resource_spec=goal.resource_spec,
        runtime_image=goal.runtime_image,
        runtime_bindings=dict(goal.runtime_bindings),
        unresolved_requirements=unresolved_requirements,
        assumptions=assumptions,
    )


def _unsupported_typed_plan(request: str, reason: str, rationale: tuple[str, ...]) -> dict[str, object]:
    """Build an honest typed-planning decline without falling back to guessing.

    Args:
        request: The natural-language prompt that could not be typed-planned.
        reason: Short explanation for the decline.
        rationale: Supporting reasoning that should be returned to the caller.

    Returns:
        A metadata-only decline payload for the typed planner path.
"""
    return {
        "supported": False,
        "original_request": request,
        "planning_outcome": "declined",
        "biological_goal": None,
        "matched_entry_names": [],
        "required_planner_types": [],
        "produced_planner_types": [],
        "resolved_inputs": {},
        "missing_requirements": [reason],
        "runtime_requirements": [],
        "assumptions": [
            "Typed planning is additive in Milestone 5 and does not replace the narrow showcase planner yet.",
        ],
        "rationale": list(rationale),
        "candidate_outcome": None,
        "workflow_spec": None,
        "binding_plan": None,
        "metadata_only": True,
    }


def _unsupported_day_one_typed_plan(request: str) -> dict[str, object] | None:
    """Build a decline for recognized day-one targets missing prompt paths.

    Args:
        request: The natural-language prompt that may be missing explicit paths.

    Returns:
        A decline payload when a known target is missing required prompt inputs.
"""
    normalized_request = _normalize(request)
    matched_name, _, rationale = _classify_target(normalized_request)
    if matched_name is None:
        return None
    prompt_paths = _extract_prompt_paths(request)
    if matched_name == SUPPORTED_WORKFLOW_NAME:
        extracted_inputs = _extract_braker_workflow_inputs(request, prompt_paths)
    elif matched_name == SUPPORTED_PROTEIN_WORKFLOW_NAME:
        extracted_inputs = _extract_protein_workflow_inputs(request, prompt_paths)
    else:
        extracted_inputs = _extract_task_inputs(request, prompt_paths)
    missing_inputs = _missing_required_inputs(matched_name, extracted_inputs)
    if not missing_inputs:
        return None
    entry = get_entry(matched_name)
    candidate_outcome = "registered_task" if entry.category == "task" else "registered_workflow"
    return {
        "supported": False,
        "original_request": request,
        "planning_outcome": "declined",
        "biological_goal": matched_name,
        "matched_entry_names": [matched_name],
        "required_planner_types": [],
        "produced_planner_types": list(entry.compatibility.produced_planner_types or tuple(field.type for field in entry.outputs)),
        "resolved_inputs": {},
        "missing_requirements": [
            f"The prompt is missing explicit required inputs for `{matched_name}`: {', '.join(missing_inputs)}."
        ],
        "runtime_requirements": [],
        "assumptions": [
            "Day-one MCP recipe execution freezes prompt-contained local paths into runtime bindings.",
        ],
        "rationale": list(rationale),
        "candidate_outcome": candidate_outcome,
        "workflow_spec": None,
        "binding_plan": None,
        "metadata_only": True,
    }


def plan_typed_request(
    request: str,
    *,
    explicit_bindings: Mapping[str, Any] | None = None,
    manifest_sources: Sequence[Path | Mapping[str, Any]] = (),
    result_bundles: Sequence[Any] = (),
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
    resolver: AssetResolver | None = None,
) -> dict[str, object]:
    """Plan a prompt through the Milestone 5 typed resolver and registry path.

    Args:
        request: The natural-language prompt being planned.
        explicit_bindings: Planner values already supplied by the caller.
        manifest_sources: Manifest sources available for resolution.
        result_bundles: Result bundles available for resolution.
        runtime_bindings: Frozen runtime overrides to carry into the recipe.
        resource_request: Caller-supplied compute resource policy or override.
        execution_profile: Caller-supplied execution profile.
        runtime_image: Caller-supplied runtime image policy or override.
        resolver: Optional resolver implementation to use for typed inputs.

    Returns:
        A metadata-only typed planning payload ready for freezing or decline reporting.
"""
    goal = _planning_goal_for_typed_request(request)
    if goal is None:
        if day_one_decline := _unsupported_day_one_typed_plan(request):
            return day_one_decline
        return _unsupported_typed_plan(
            request,
            reason="The request does not map to a supported typed biology goal, so the planner declines instead of inventing steps.",
            rationale=(
                "Milestone 5 only recognizes a small set of registered workflow and registered-stage planning goals.",
            ),
        )

    resolver = resolver or LocalManifestAssetResolver()
    resolved_inputs, source_labels, missing_requirements, assumptions = _resolve_typed_goal_inputs(
        goal,
        explicit_bindings=explicit_bindings or {},
        manifest_sources=manifest_sources,
        result_bundles=result_bundles,
        resolver=resolver,
    )
    selected_profile, selected_resources, selected_image, resource_requirements, resource_assumptions = (
        _select_execution_policy(
            goal,
            request=request,
            resource_request=resource_request,
            execution_profile=execution_profile,
            runtime_image=runtime_image,
        )
    )
    merged_runtime_bindings = dict(goal.runtime_bindings)
    merged_runtime_bindings.update(runtime_bindings or {})
    goal = replace(
        goal,
        runtime_bindings=merged_runtime_bindings,
        execution_profile=selected_profile,
        resource_spec=selected_resources,
        runtime_image=selected_image,
    )
    workflow_spec = _workflow_spec_for_typed_goal(goal, source_prompt=request)
    binding_plan = _binding_plan_for_typed_goal(
        goal,
        resolved_inputs=resolved_inputs,
        source_labels=source_labels,
        unresolved_requirements=missing_requirements + resource_requirements + goal.unresolved_runtime_requirements,
        assumptions=assumptions
        + resource_assumptions
        + (
            "Typed planning uses resolver and registry metadata before any future execution step.",
            "WorkflowSpec and BindingPlan outputs are metadata-only in Milestone 5.",
        ),
    )

    supported = not missing_requirements and not resource_requirements
    requires_composition_approval = goal.outcome == "generated_workflow_spec" and goal.name.startswith("composition_")
    return {
        "supported": supported,
        "original_request": request,
        "planning_outcome": goal.outcome if supported else "declined",
        "candidate_outcome": goal.outcome,
        "biological_goal": goal.name,
        "matched_entry_names": list(goal.target_entry_names),
        "required_planner_types": list(goal.required_planner_types),
        "produced_planner_types": list(goal.produced_planner_types),
        "resolved_inputs": resolved_inputs,
        "missing_requirements": list(missing_requirements + resource_requirements),
        "runtime_requirements": list(goal.unresolved_runtime_requirements),
        "execution_profile": selected_profile,
        "resource_spec": selected_resources.to_dict() if selected_resources is not None else None,
        "runtime_image": selected_image.to_dict() if selected_image is not None else None,
        "assumptions": list(binding_plan.assumptions),
        "rationale": list(goal.rationale),
        "workflow_spec": workflow_spec.to_dict() if workflow_spec is not None else None,
        "binding_plan": binding_plan.to_dict(),
        "metadata_only": True,
        "requires_user_approval": requires_composition_approval,
    }


def _assumptions_for_target(name: str) -> tuple[str, ...]:
    """Return assumptions for the matched supported entry.

    Args:
        name: The supported entry name whose assumptions should be returned.

    Returns:
        The assumptions that explain how the planner will interpret the request.
"""
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
    """Build the stable decline payload for unsupported or out-of-scope prompts.

    Args:
        request: The natural-language prompt that could not be mapped.
        reason: Short explanation for the decline.
        rationale: Supporting reasoning returned to the caller.
        declined_stages: Any downstream stages that were intentionally not selected.

    Returns:
        A stable decline payload for the current narrow showcase surface.
"""
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
    """Plan one prompt for the narrow workflow-or-task showcase.

    Args:
        request: The natural-language prompt being mapped to a showcase entry.

    Returns:
        A stable planning payload describing the matched showcase entry or decline.
"""
    matched_name, confidence, rationale = _classify_target(request)
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
    """Run the narrow planner from the command line and print JSON.

    The CLI exists for local inspection and smoke testing of the planner.
"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="Natural-language prompt to evaluate.")
    args = parser.parse_args()
    print(json.dumps(plan_request(args.request), indent=2))


if __name__ == "__main__":
    main()
