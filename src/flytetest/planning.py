"""Deterministic planning for the FLyteTest MCP showcase.

This module keeps two planning entrypoints:

* `plan_request()` remains the free-text preview tool. It performs a
    deterministic structured match against registered entry `biological_stage`
    and `name`, then falls back to reviewed composition discovery.
* `plan_typed_request()` is the structured planner used once the caller has
    selected a concrete target and provided explicit bindings, manifests, runtime
    inputs, and execution policy.

The planner does not invent new workflow behavior. It only freezes registered
entries, reviewed stage compositions, or metadata-only generated specs built
from registered stages.

Boundary with `composition.py`: `planning` is the *entrypoint* layer that
classifies an intent and chooses what to freeze. When no single registered
entry matches, planning *delegates* to `composition.compose_workflow_path()`
to discover a reviewable multi-stage path; composition itself never freezes,
classifies, or accepts free text.
"""

from __future__ import annotations

import ast
import argparse
import difflib
import inspect
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
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
    SUPPORTED_TARGET_NAMES,
    SUPPORTED_TASK_NAME,
    SUPPORTED_WORKFLOW_NAME,
)
from flytetest.mcp_replies import PlanDecline, PlanSuccess, SuggestedBundle
from flytetest.registry import InterfaceField, RegistryEntry, get_entry
from flytetest.resolver import AssetResolver, LocalManifestAssetResolver, ResolutionResult
from flytetest.spec_artifacts import (
    artifact_from_typed_plan,
    make_recipe_id,
    save_workflow_spec_artifact,
)
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


DEFAULT_RECIPE_DIR = Path(__file__).resolve().parents[2] / ".runtime" / "specs"


_TOKEN_RE = re.compile(r"[a-z0-9]+")
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
    runtime_images: dict[str, str] = field(default_factory=dict)
    tool_databases: dict[str, str] = field(default_factory=dict)
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AmbiguousMatch:
    """Multiple registered entries survived deterministic target matching."""

    entries: tuple[RegistryEntry, ...]


@dataclass(frozen=True, slots=True)
class NoMatch:
    """Deterministic target matching found no registered entry."""


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
    except (ImportError, ModuleNotFoundError) as exc:
        if isinstance(exc, ModuleNotFoundError) and exc.name not in {"flyte", "flyte.io"}:
            raise
        if isinstance(exc, ImportError) and not isinstance(exc, ModuleNotFoundError):
            pass  # broken import in showcase module — fall back to source parse
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


def _showcase_registry_entries() -> tuple[RegistryEntry, ...]:
    """Return the currently runnable showcase entries used by MCP planning."""
    return tuple(get_entry(name) for name in SUPPORTED_TARGET_NAMES)


def _pipeline_stage_order(entry: RegistryEntry) -> int:
    """Return one sortable pipeline-stage order for deterministic matching."""
    order = entry.compatibility.pipeline_stage_order
    return order if isinstance(order, int) else 1_000_000


_ACTION_PREFIXES = ("run ", "execute ", "perform ", "start ", "launch ")


def _strip_action_prefix(normalized: str) -> str:
    """Remove a leading action verb so 'run X' matches the same target as 'X'."""
    for prefix in _ACTION_PREFIXES:
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return normalized


def _match_target(
    biological_goal: str,
    registry_entries: Sequence[RegistryEntry],
) -> RegistryEntry | AmbiguousMatch | NoMatch:
    """Deterministically resolve one biological goal to a registered entry."""
    goal = _normalize(biological_goal)
    if not goal:
        return NoMatch()

    stripped = _strip_action_prefix(goal)
    primary = [
        entry
        for entry in registry_entries
        if _normalize(entry.compatibility.biological_stage or "") in (goal, stripped)
    ]
    candidates = primary or [
        entry for entry in registry_entries if _normalize(entry.name) in (goal, stripped)
    ]
    if not candidates:
        return NoMatch()

    workflows = [entry for entry in candidates if entry.category == "workflow"]
    pool = workflows or candidates
    pool = sorted(pool, key=lambda entry: (_pipeline_stage_order(entry), entry.name))
    lowest_order = _pipeline_stage_order(pool[0])
    pool = [entry for entry in pool if _pipeline_stage_order(entry) == lowest_order]
    if len(pool) == 1:
        return pool[0]
    return AmbiguousMatch(entries=tuple(pool))


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

    allowed_fields = {"cpu", "memory", "gpu", "partition", "account", "walltime", "execution_class", "module_loads", "notes"}
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
        elif key == "module_loads":
            mods_value = value[key]
            kwargs[key] = (
                (str(mods_value),)
                if isinstance(mods_value, str) or not isinstance(mods_value, Sequence)
                else tuple(str(m) for m in mods_value)
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
        partition=override.partition or base.partition,
        account=override.account or base.account,
        walltime=override.walltime or base.walltime,
        execution_class=override.execution_class or base.execution_class,
        module_loads=override.module_loads or base.module_loads,
        notes=(*base.notes, *override.notes),
    )


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


def _registry_default_resource_spec(entry: RegistryEntry) -> ResourceSpec | None:
    """Return the registry's default local resource policy for one entry.

    Args:
        entry: The registry entry whose compatibility defaults should be read.

    Returns:
        The registry's default resource policy, when one is declared.
"""
    resources = entry.compatibility.execution_defaults.get("resources")
    return _coerce_resource_spec(resources) if isinstance(resources, Mapping) else None


def _coerce_string_mapping(value: Mapping[str, Any] | None) -> dict[str, str]:
    """Normalize an optional string-keyed mapping used in execution_defaults."""
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if key in (None, "") or item in (None, ""):
            continue
        normalized[str(key)] = str(item)
    return normalized


def _coerce_string_tuple(value: object) -> tuple[str, ...]:
    """Normalize one optional string or sequence of strings into a tuple."""
    if value in (None, ""):
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        return (str(value),)
    return tuple(str(item) for item in value if item not in (None, ""))


def _runtime_image_spec_from_named_images(images: Mapping[str, str]) -> RuntimeImageSpec | None:
    """Derive the legacy single-image policy from a named runtime-images mapping."""
    if not images:
        return None
    _, image_path = sorted(images.items())[0]
    return _coerce_runtime_image_spec(image_path)


def _resolved_environment_payload(
    *,
    runtime_images: Mapping[str, str],
    tool_databases: Mapping[str, str],
    resource_spec: ResourceSpec | None,
    env_vars: Mapping[str, str],
) -> dict[str, object]:
    """Return the resolved environment metadata frozen into the planning output."""
    return {
        "runtime_images": dict(runtime_images),
        "tool_databases": dict(tool_databases),
        "module_loads": list(resource_spec.module_loads) if resource_spec is not None else [],
        "env_vars": dict(env_vars),
    }


def _select_execution_policy(
    goal: TypedPlanningGoal,
    *,
    resource_request: Mapping[str, Any] | ResourceSpec | None,
    execution_profile: str | None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None,
    runtime_images: Mapping[str, Any] | None,
    tool_databases: Mapping[str, Any] | None,
    bundle_overrides: Mapping[str, Any] | None,
) -> tuple[
    str,
    ResourceSpec | None,
    RuntimeImageSpec | None,
    dict[str, str],
    dict[str, str],
    dict[str, str],
    tuple[str, ...],
    tuple[str, ...],
]:
    """Resolve profile, resources, and runtime image policy for a typed goal.

    Args:
        goal: The typed planning goal being prepared for freezing.
        resource_request: Caller-supplied compute resource policy or override.
        execution_profile: Caller-supplied execution profile, if any.
        runtime_image: Caller-supplied runtime image policy or override.
        runtime_images: Caller-supplied named runtime-image overrides.
        tool_databases: Caller-supplied tool-database overrides.
        bundle_overrides: Bundle-level environment overrides layered over the entry defaults.

    Returns:
        The selected execution profile, resource policy, runtime image policy,
        resolved runtime-image map, resolved tool-database map, resolved env vars,
        unresolved resource requirements, and assumptions.
"""
    entries = tuple(get_entry(entry_name) for entry_name in goal.target_entry_names)
    default_profile = str(entries[0].compatibility.execution_defaults.get("profile", "local")) if entries else "local"
    supported_profiles = set(entries[0].compatibility.supported_execution_profiles if entries else ("local",))
    for entry in entries[1:]:
        supported_profiles.intersection_update(entry.compatibility.supported_execution_profiles)
    if not supported_profiles:
        supported_profiles.add("local")

    entry_execution_defaults = dict(entries[0].compatibility.execution_defaults) if entries else {}
    bundle_overrides = dict(bundle_overrides or {})

    selected_runtime_images = {
        **_coerce_string_mapping(entry_execution_defaults.get("runtime_images")),
        **_coerce_string_mapping(bundle_overrides.get("runtime_images")),
        **_coerce_string_mapping(runtime_images),
    }
    selected_tool_databases = {
        **_coerce_string_mapping(entry_execution_defaults.get("tool_databases")),
        **_coerce_string_mapping(bundle_overrides.get("tool_databases")),
        **_coerce_string_mapping(tool_databases),
    }
    selected_env_vars = {
        **_coerce_string_mapping(entry_execution_defaults.get("env_vars")),
        **_coerce_string_mapping(bundle_overrides.get("env_vars")),
    }
    entry_module_loads = _coerce_string_tuple(entry_execution_defaults.get("module_loads"))
    bundle_module_loads = _coerce_string_tuple(bundle_overrides.get("module_loads"))

    selected_profile = _clean_path(execution_profile or default_profile or "local").lower()
    unresolved: list[str] = []
    assumptions: list[str] = []
    if selected_profile not in supported_profiles:
        unresolved.append(
            f"Execution profile `{selected_profile}` is not supported for `{goal.name}`; supported profiles: {', '.join(sorted(supported_profiles))}."
        )

    registry_default = _registry_default_resource_spec(entries[0]) if entries else None
    if entry_module_loads:
        registry_default = _merge_resource_specs(
            registry_default,
            ResourceSpec(module_loads=entry_module_loads),
        )
    bundle_resources = ResourceSpec(module_loads=bundle_module_loads) if bundle_module_loads else None
    caller_resources = _coerce_resource_spec(resource_request)
    selected_resources = _merge_resource_specs(
        _merge_resource_specs(
            registry_default,
            bundle_resources,
        ),
        caller_resources,
    )
    if selected_resources is not None and selected_profile != (selected_resources.execution_class or selected_profile):
        selected_resources = replace(selected_resources, execution_class=selected_profile)
    if selected_profile == "slurm":
        selected_resources = _slurm_resource_spec_defaults(selected_resources)

    selected_image = (
        _coerce_runtime_image_spec(runtime_image)
        or _runtime_image_spec_from_named_images(selected_runtime_images)
    )
    if selected_resources is not None:
        assumptions.append(
            "ResourceSpec is frozen into the recipe for review and replay before local or Slurm execution consumes it."
        )
    if selected_image is not None:
        assumptions.append(
            "RuntimeImageSpec is frozen into the recipe as policy metadata; existing workflow inputs still control tool-specific SIF arguments."
        )
    if selected_tool_databases:
        assumptions.append(
            "Tool-database paths are frozen into WorkflowSpec.tool_databases for deterministic replay."
        )
    if selected_env_vars:
        assumptions.append(
            "Non-secret environment variables are frozen into WorkflowSpec replay metadata for deterministic replay."
        )
    return (
        selected_profile,
        selected_resources,
        selected_image,
        selected_runtime_images,
        selected_tool_databases,
        selected_env_vars,
        tuple(unresolved),
        tuple(assumptions),
    )


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


def showcase_limitations() -> tuple[str, ...]:
    """Return the hard interface limits for the showcase planner."""
    return SHOWCASE_LIMITATIONS


def _repeat_filter_then_busco_goal() -> TypedPlanningGoal:
    """Return the reviewed repeat-filter plus BUSCO generated-spec goal."""
    return TypedPlanningGoal(
        name="repeat_filter_then_busco_qc",
        outcome="generated_workflow_spec",
        target_entry_names=("annotation_repeat_filtering", "annotation_qc_busco"),
        required_planner_types=("ConsensusAnnotation",),
        produced_planner_types=("QualityAssessmentTarget",),
        rationale=(
            "The request asks for a multi-stage repeat-filtering and QC bundle that is not a checked-in single workflow.",
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


def _consensus_annotation_goal() -> TypedPlanningGoal:
    """Return the reviewed EVM composition goal."""
    return TypedPlanningGoal(
        name="consensus_annotation_from_registered_stages",
        outcome="registered_stage_composition",
        target_entry_names=("consensus_annotation_evm_prep", "consensus_annotation_evm"),
        required_planner_types=("TranscriptEvidenceSet", "ProteinEvidenceSet", "AnnotationEvidenceSet"),
        produced_planner_types=("ConsensusAnnotation",),
        rationale=(
            "The request asks for consensus annotation through the EVM boundary.",
            "The registered pre-EVM preparation and EVM execution workflows form the reviewed composition path.",
        ),
        analysis_goal="Compose reviewed pre-EVM preparation and EVM execution stages.",
        unresolved_runtime_requirements=(
            "EVM script paths and optional weights remain normal runtime bindings.",
        ),
    )


def _registered_goal_for_entry(entry: RegistryEntry) -> TypedPlanningGoal:
    """Build one structured planning goal directly from registry metadata."""
    produced_types = entry.compatibility.produced_planner_types or tuple(field.type for field in entry.outputs)
    runtime_requirements_by_name = {
        "annotation_functional_eggnog": (
            "`eggnog_data_dir` must still be supplied before execution.",
            "`eggnog_database` should be selected explicitly for the chosen taxonomic scope.",
        ),
    }
    return TypedPlanningGoal(
        name=entry.name,
        outcome="registered_task" if entry.category == "task" else "registered_workflow",
        target_entry_names=(entry.name,),
        required_planner_types=tuple(entry.compatibility.accepted_planner_types),
        produced_planner_types=tuple(produced_types),
        rationale=(
            f"Structured planning selected the registered {entry.category} `{entry.name}`.",
            f"The request maps to the registry biological stage `{entry.compatibility.biological_stage or entry.name}`.",
        ),
        analysis_goal=f"Run the registered {entry.category} `{entry.name}` from a frozen recipe.",
        unresolved_runtime_requirements=runtime_requirements_by_name.get(entry.name, ()),
    )


def _typed_goal_for_target(biological_goal: str, target_name: str) -> TypedPlanningGoal | None:
    """Resolve one structured target name into a typed planning goal."""
    del biological_goal
    if target_name == "repeat_filter_then_busco_qc":
        return _repeat_filter_then_busco_goal()
    if target_name == "consensus_annotation_from_registered_stages":
        return _consensus_annotation_goal()
    try:
        entry = get_entry(target_name)
    except KeyError:
        return None
    return _registered_goal_for_entry(entry)


def _target_name_advisories(biological_goal: str, target_name: str) -> tuple[str, ...]:
    """Return soft advisories when target_name overrides a different stage label."""
    if target_name in {"repeat_filter_then_busco_qc", "consensus_annotation_from_registered_stages"}:
        return ()
    try:
        entry = get_entry(target_name)
    except KeyError:
        return ()

    normalized_goal = _normalize(biological_goal)
    stage_name = entry.compatibility.biological_stage or entry.name
    if normalized_goal in {"", _normalize(stage_name), _normalize(entry.name)}:
        return ()
    return (
        f"target_name `{entry.name}` overrides biological_goal `{biological_goal}`; the registered stage label is `{stage_name}`.",
    )


_VARIANT_CALLING_KEYWORDS: frozenset[str] = frozenset({
    "variant", "variants", "vcf", "gvcf", "germline",
    "haplotype", "haplotypecaller",
    "genotype", "genotyping", "joint calling", "joint call",
    "vqsr", "bqsr", "recalibration", "recalibrator",
    "dedup", "mark duplicates",
    "bwa", "bwa mem", "bwa mem2",
    "gatk", "gatk4",
    # Milestone I additions (only GATK/variant-specific terms to avoid cross-family matches)
    "hard-filter", "hard filter", "variant filtration",
    "snpeff", "snp eff",
    "multiqc",
    "insert size",
})

_VARIANT_CALLING_TARGET_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("prepare reference", "index reference", "create sequence dictionary", "sequence dictionary"), "prepare_reference"),
    (("preprocess from ubam", "ubam", "unmapped bam"), "preprocess_sample_from_ubam"),
    (("scatter haplotype", "scatter gvcf", "interval scatter", "sequential haplotype", "serial haplotype"), "sequential_interval_haplotype_caller"),
    (("refine genotype", "calculate genotype posterior", "cgp", "population prior"), "post_genotyping_refinement"),
    (("vqsr", "recalibrate variant", "filter cohort", "genotype refinement", "snp indel filter"), "genotype_refinement"),
    (("germline short variant", "end to end", "full pipeline", "germline discovery"), "germline_short_variant_discovery"),
    (("haplotype caller", "per sample gvcf", "haplotypecaller"), "haplotype_caller"),
    (("combine gvcf", "cohort gvcf", "merge gvcf"), "combine_gvcfs"),
    (("joint call", "genomicsdb", "genotypegvcfs", "joint genotyp"), "joint_call_gvcfs"),
    (("apply bqsr", "apply recal"), "apply_bqsr"),
    (("base recalibrat", "bqsr table", "recalibration table", "bqsr recal", "bqsr"), "base_recalibrator"),
    (("preprocess", "align", "sort", "dedup", "recalibrate reads", "bwa mem"), "preprocess_sample"),
    (("index vcf", "index feature file", "index feature"), "index_feature_file"),
    # Milestone I — new target routing
    (("hard filter", "hard-filter", "variant filtration", "small cohort filter", "filtration"), "small_cohort_filter"),
    (("filter snp", "filter indel", "variantfiltration"), "variant_filtration"),
    (("coverage metric", "wgs metric", "insert size", "pre call qc", "pre-call qc"), "pre_call_coverage_qc"),
    (("bcftools stats", "variant stats", "post call qc", "post-call qc", "multiqc"), "post_call_qc_summary"),
    (("annotate variant", "snpeff", "snp eff", "functional effect", "annotation"), "annotate_variants_snpeff"),
)


def _match_variant_calling_target(normalized_request: str) -> str | None:
    """Return a variant_calling target name when the prompt matches GATK keywords.

    Args:
        normalized_request: Normalized (lowercase, alphanumeric) request text.

    Returns:
        A registered variant_calling target name, or ``None`` when no match.
    """
    if not any(kw in normalized_request for kw in _VARIANT_CALLING_KEYWORDS):
        return None
    for phrase_cluster, target in _VARIANT_CALLING_TARGET_MAP:
        if any(phrase in normalized_request for phrase in phrase_cluster):
            return target
    return "germline_short_variant_discovery"


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
    resolved_environment = _resolved_environment_payload(
        runtime_images=goal.runtime_images,
        tool_databases=goal.tool_databases,
        resource_spec=goal.resource_spec,
        env_vars=goal.env_vars,
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
            replay_metadata={
                "selection_mode": selection_mode,
                "resolved_environment": resolved_environment,
            },
            tool_databases=dict(goal.tool_databases),
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
            replay_metadata={
                "selection_mode": "registered_stage_composition",
                "resolved_environment": resolved_environment,
            },
            tool_databases=dict(goal.tool_databases),
        )

    if goal.outcome == "generated_workflow_spec":
        generated_record = GeneratedEntityRecord(
            generated_entity_id=goal.generated_entity_id or f"generated::{goal.name}",
            source_prompt=source_prompt,
            assumptions=(
                "This is a metadata-only generated spec preview in Milestone 5.",
                "The preview references registered stages and does not generate new task code.",
            ),
            selected_execution_profile=goal.execution_profile or "local",
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
                replay_metadata={
                    "selection_mode": "generated_workflow_spec_preview",
                    "resolved_environment": resolved_environment,
                },
                tool_databases=dict(goal.tool_databases),
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
                replay_metadata={
                    "selection_mode": "registry_constrained_composition",
                    "resolved_environment": resolved_environment,
                },
                tool_databases=dict(goal.tool_databases),
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


def _find_close_target_matches(request: str) -> list[str]:
    """Return supported target names that are close matches to any token in *request*.

    Uses :func:`difflib.get_close_matches` with a cutoff of 0.6 against each
    whitespace-delimited token so callers receive actionable suggestions when a
    near-miss target name appears in the prompt.

    Args:
        request: The natural-language prompt to scan for near-miss tokens.

    Returns:
        A deduplicated list of close-matching target names, at most 3 entries.
    """
    seen: dict[str, None] = {}
    for token in request.split():
        # Strip punctuation that commonly trails a word in natural language
        cleaned = token.strip(".,;:!?\"'()[]{}")
        if not cleaned:
            continue
        for match in difflib.get_close_matches(cleaned, SUPPORTED_TARGET_NAMES, n=3, cutoff=0.6):
            seen[match] = None
        if len(seen) >= 3:
            break
    return list(seen.keys())[:3]


def _default_recovery_steps() -> tuple[str, ...]:
    """Return the standard recovery channels for structured planning declines."""
    return (
        "Supply target_name=<name> to disambiguate or bypass free-text matching.",
        "Or restate biological_goal to match one entry's biological_stage exactly.",
        "Or call list_entries(category=..., pipeline_family=...) to browse the candidates.",
    )


def _unsupported_typed_plan(
    request: str,
    reason: str,
    rationale: tuple[str, ...],
    *,
    biological_goal: str | None = None,
    matched_entry_names: Sequence[str] = (),
    candidate_outcome: TypedPlanningOutcome | None = None,
    required_planner_types: Sequence[str] = (),
    produced_planner_types: Sequence[str] = (),
    limitations: Sequence[str] = (),
    next_steps: Sequence[str] = (),
    suggested_bundles: Sequence[SuggestedBundle] = (),
) -> dict[str, object]:
    """Build one honest typed-planning decline without guessing or parsing prose."""
    close_matches = _find_close_target_matches(request)
    suggestions = (
        [f"Did you mean one of: {', '.join(f'`{match}`' for match in close_matches)}?"]
        if close_matches
        else []
    )
    decline_limitations = list(limitations) or [reason, *suggestions]
    return {
        "supported": False,
        "original_request": request,
        "planning_outcome": "declined",
        "candidate_outcome": candidate_outcome,
        "biological_goal": biological_goal,
        "matched_entry_names": list(matched_entry_names),
        "required_planner_types": list(required_planner_types),
        "produced_planner_types": list(produced_planner_types),
        "resolved_inputs": {},
        "missing_requirements": [reason, *suggestions],
        "runtime_requirements": [],
        "execution_profile": None,
        "resource_spec": None,
        "runtime_image": None,
        "runtime_images": {},
        "tool_databases": {},
        "env_vars": {},
        "resolved_environment": {
            "runtime_images": {},
            "tool_databases": {},
            "module_loads": [],
            "env_vars": {},
        },
        "assumptions": [
            "Free-text planning no longer extracts local file paths, execution profiles, or runtime images from prose.",
        ],
        "rationale": list(rationale),
        "workflow_spec": None,
        "binding_plan": None,
        "metadata_only": True,
        "requires_user_approval": False,
        "limitations": decline_limitations,
        "suggested_bundles": [
            {"name": b.name, "description": b.description, "applies_to": list(b.applies_to)}
            for b in suggested_bundles
        ],
        "suggested_prior_runs": [],
        "next_steps": list(next_steps or _default_recovery_steps()),
    }


def _typed_plan_from_goal(
    goal: TypedPlanningGoal,
    *,
    original_request: str,
    source_prompt: str,
    explicit_bindings: Mapping[str, Any] | None,
    manifest_sources: Sequence[Path | Mapping[str, Any]],
    result_bundles: Sequence[Any],
    scalar_inputs: Mapping[str, Any] | None,
    runtime_bindings: Mapping[str, Any] | None,
    resource_request: Mapping[str, Any] | ResourceSpec | None,
    execution_profile: str | None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None,
    runtime_images: Mapping[str, Any] | None,
    tool_databases: Mapping[str, Any] | None,
    bundle_overrides: Mapping[str, Any] | None,
    resolver: AssetResolver | None,
    limitations: Sequence[str] = (),
) -> dict[str, object]:
    """Resolve planner inputs and execution policy for one typed goal."""
    resolver = resolver or LocalManifestAssetResolver()
    resolved_inputs, source_labels, missing_requirements, assumptions = _resolve_typed_goal_inputs(
        goal,
        explicit_bindings=explicit_bindings or {},
        manifest_sources=manifest_sources,
        result_bundles=result_bundles,
        resolver=resolver,
    )
    (
        selected_profile,
        selected_resources,
        selected_image,
        selected_runtime_images,
        selected_tool_databases,
        selected_env_vars,
        resource_requirements,
        resource_assumptions,
    ) = _select_execution_policy(
        goal,
        resource_request=resource_request,
        execution_profile=execution_profile,
        runtime_image=runtime_image,
        runtime_images=runtime_images,
        tool_databases=tool_databases,
        bundle_overrides=bundle_overrides,
    )
    merged_runtime_bindings = dict(goal.runtime_bindings)
    merged_runtime_bindings.update(scalar_inputs or {})
    merged_runtime_bindings.update(runtime_bindings or {})
    caller_images = {
        **_coerce_string_mapping(bundle_overrides.get("runtime_images") if bundle_overrides else None),
        **_coerce_string_mapping(runtime_images),
    }
    for key, value in caller_images.items():
        merged_runtime_bindings.setdefault(key, value)
    goal = replace(
        goal,
        runtime_bindings=merged_runtime_bindings,
        execution_profile=selected_profile,
        resource_spec=selected_resources,
        runtime_image=selected_image,
        runtime_images=selected_runtime_images,
        tool_databases=selected_tool_databases,
        env_vars=selected_env_vars,
    )
    workflow_spec = _workflow_spec_for_typed_goal(goal, source_prompt=source_prompt)
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
    plan_limitations = list(limitations)
    if source_prompt == "":
        plan_limitations.append(
            "No source_prompt was supplied; replay metadata will not preserve original natural-language provenance."
        )

    return {
        "supported": supported,
        "original_request": original_request,
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
        "runtime_images": dict(selected_runtime_images),
        "tool_databases": dict(selected_tool_databases),
        "env_vars": dict(selected_env_vars),
        "resolved_environment": _resolved_environment_payload(
            runtime_images=selected_runtime_images,
            tool_databases=selected_tool_databases,
            resource_spec=selected_resources,
            env_vars=selected_env_vars,
        ),
        "assumptions": list(binding_plan.assumptions),
        "rationale": list(goal.rationale),
        "workflow_spec": workflow_spec.to_dict() if workflow_spec is not None else None,
        "binding_plan": binding_plan.to_dict(),
        "metadata_only": True,
        "requires_user_approval": requires_composition_approval,
        "limitations": plan_limitations,
        "suggested_bundles": [],
        "suggested_prior_runs": [],
        "next_steps": [],
    }


def plan_typed_request(
    *,
    biological_goal: str,
    target_name: str,
    source_prompt: str = "",
    explicit_bindings: Mapping[str, Any] | None = None,
    manifest_sources: Sequence[Path | Mapping[str, Any]] = (),
    result_bundles: Sequence[Any] = (),
    scalar_inputs: Mapping[str, Any] | None = None,
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
    runtime_images: Mapping[str, Any] | None = None,
    tool_databases: Mapping[str, Any] | None = None,
    bundle_overrides: Mapping[str, Any] | None = None,
    resolver: AssetResolver | None = None,
) -> dict[str, object]:
    """Plan one structured biological goal against one explicit target name."""
    goal = _typed_goal_for_target(biological_goal, target_name)
    if goal is None:
        return _unsupported_typed_plan(
            source_prompt,
            reason=f"The structured target `{target_name}` is not a supported typed planning target.",
            rationale=(
                "Structured typed planning requires one explicit registered target name or one reviewed generated-spec target.",
            ),
            biological_goal=biological_goal or None,
        )
    return _typed_plan_from_goal(
        goal,
        original_request=source_prompt,
        source_prompt=source_prompt,
        explicit_bindings=explicit_bindings,
        manifest_sources=manifest_sources,
        result_bundles=result_bundles,
        scalar_inputs=scalar_inputs,
        runtime_bindings=runtime_bindings,
        resource_request=resource_request,
        execution_profile=execution_profile,
        runtime_image=runtime_image,
        runtime_images=runtime_images,
        tool_databases=tool_databases,
        bundle_overrides=bundle_overrides,
        resolver=resolver,
        limitations=_target_name_advisories(biological_goal, target_name),
    )


def plan_request(
    request: str,
    *,
    explicit_bindings: Mapping[str, Any] | None = None,
    manifest_sources: Sequence[Path | Mapping[str, Any]] = (),
    result_bundles: Sequence[Any] = (),
    scalar_inputs: Mapping[str, Any] | None = None,
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
    runtime_images: Mapping[str, Any] | None = None,
    tool_databases: Mapping[str, Any] | None = None,
    bundle_overrides: Mapping[str, Any] | None = None,
    resolver: AssetResolver | None = None,
) -> dict[str, object]:
    """Plan one free-text request through structured matching and composition fallback."""
    matched = _match_target(request, _showcase_registry_entries())
    if isinstance(matched, RegistryEntry):
        return plan_typed_request(
            biological_goal=request,
            target_name=matched.name,
            source_prompt=request,
            explicit_bindings=explicit_bindings,
            manifest_sources=manifest_sources,
            result_bundles=result_bundles,
            scalar_inputs=scalar_inputs,
            runtime_bindings=runtime_bindings,
            resource_request=resource_request,
            execution_profile=execution_profile,
            runtime_image=runtime_image,
            runtime_images=runtime_images,
            tool_databases=tool_databases,
            bundle_overrides=bundle_overrides,
            resolver=resolver,
        )
    if isinstance(matched, AmbiguousMatch):
        names = [entry.name for entry in matched.entries]
        return _unsupported_typed_plan(
            request,
            reason=f"Ambiguous target: biological_goal resolved to {len(names)} entries: {names}.",
            rationale=(
                "Deterministic matching found multiple registered entries even after workflow and stage-order tiebreakers.",
            ),
            biological_goal=request,
            matched_entry_names=names,
            limitations=(f"Ambiguous target: biological_goal resolved to {len(names)} entries: {names}.",),
            next_steps=_default_recovery_steps(),
        )

    normalized_request = _normalize(request)
    variant_target = _match_variant_calling_target(normalized_request)
    if variant_target is not None:
        from flytetest.bundles import BUNDLES
        suggested = [
            SuggestedBundle(
                name=b.name,
                description=b.description,
                applies_to=tuple(b.applies_to),
                available=False,
            )
            for b in BUNDLES.values()
            if b.pipeline_family == "variant_calling" and variant_target in b.applies_to
        ]
        if not suggested:
            suggested = [
                SuggestedBundle(
                    name="variant_calling_germline_minimal",
                    description="Minimal germline variant calling demo bundle.",
                    applies_to=(variant_target,),
                    available=False,
                )
            ]
        return _unsupported_typed_plan(
            request,
            reason=f"Variant-calling prompt matched target `{variant_target}`; use run_workflow or run_task with that target directly.",
            rationale=(
                f"Prompt heuristics map this request to the registered GATK target `{variant_target}`.",
                "Supply explicit scalar inputs and bindings to proceed; bundle load is the recommended path.",
            ),
            biological_goal=request,
            matched_entry_names=[variant_target],
            next_steps=(
                f"Call load_bundle('variant_calling_germline_minimal') to get starter inputs.",
                f"Then call run_workflow('{variant_target}', **bundle) or run_task('{variant_target}', **bundle).",
            ),
            suggested_bundles=suggested,
        )

    composition_goal = _try_composition_fallback(request, normalized_request)
    if composition_goal is not None:
        return _typed_plan_from_goal(
            composition_goal,
            original_request=request,
            source_prompt=request,
            explicit_bindings=explicit_bindings,
            manifest_sources=manifest_sources,
            result_bundles=result_bundles,
            scalar_inputs=scalar_inputs,
            runtime_bindings=runtime_bindings,
            resource_request=resource_request,
            execution_profile=execution_profile,
            runtime_image=runtime_image,
            runtime_images=runtime_images,
            tool_databases=tool_databases,
            bundle_overrides=bundle_overrides,
            resolver=resolver,
        )

    return _unsupported_typed_plan(
        request,
        reason="The request does not map to a supported typed biology goal, so the planner declines instead of inventing steps.",
        rationale=(
            "Free-text planning only supports exact biological_stage or entry-name matches plus reviewed composition fallback.",
        ),
        biological_goal=request,
    )


def _composition_target_name(goal: TypedPlanningGoal) -> str:
    """Return the ``composed-<first>_to_<last>`` target stem for one composed goal."""
    names = goal.target_entry_names
    if len(names) >= 2:
        return f"composed-{names[0]}_to_{names[-1]}"
    if names:
        return f"composed-{names[0]}"
    return "composed"


def _pipeline_family_for_goal(goal: TypedPlanningGoal) -> str:
    """Return the first composed stage's pipeline family so declines can route by family."""
    for name in goal.target_entry_names:
        try:
            return get_entry(name).compatibility.pipeline_family
        except KeyError:
            continue
    return ""


def _current_plan_timestamp() -> str:
    """Return a stable UTC timestamp for composed-recipe artifacts frozen by plan_request."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _suggested_bundles_for_target(entry_name: str | None) -> tuple[SuggestedBundle, ...]:
    """Return §10 `suggested_bundles` filtered to available bundles that apply to the target."""
    from flytetest.bundles import BUNDLES, _check_bundle_availability

    suggestions: list[SuggestedBundle] = []
    for bundle in BUNDLES.values():
        status = _check_bundle_availability(bundle)
        if not status.available:
            continue
        if entry_name is not None and entry_name not in bundle.applies_to:
            continue
        suggestions.append(
            SuggestedBundle(
                name=bundle.name,
                description=bundle.description,
                applies_to=tuple(bundle.applies_to),
                available=status.available,
            )
        )
    return tuple(suggestions)


def _decline_reason_from_typed_plan(typed_plan: Mapping[str, object]) -> str:
    """Return one short decline reason pulled from a typed_plan payload."""
    missing = typed_plan.get("missing_requirements")
    if isinstance(missing, list) and missing:
        return str(missing[0])
    limitations = typed_plan.get("limitations")
    if isinstance(limitations, list) and limitations:
        return str(limitations[0])
    return "The typed plan could not be resolved into a runnable recipe."


def _plan_decline(
    *,
    target: str = "",
    pipeline_family: str = "",
    reason: str,
    extra_limitations: Sequence[str] = (),
    next_steps: Sequence[str] | None = None,
    suggested_for_entry: str | None = None,
) -> PlanDecline:
    """Build one §10-shaped PlanDecline with available-bundle and next-step channels."""
    return PlanDecline(
        supported=False,
        target=target,
        pipeline_family=pipeline_family,
        limitations=(reason, *tuple(str(item) for item in extra_limitations)),
        suggested_bundles=_suggested_bundles_for_target(suggested_for_entry),
        suggested_prior_runs=(),
        next_steps=tuple(next_steps or _default_recovery_steps()),
    )


def _plan_success_single_entry(
    entry: RegistryEntry,
    typed_plan: Mapping[str, object],
    *,
    request: str,
) -> PlanSuccess:
    """Build a no-freeze PlanSuccess that re-issues `run_task`/`run_workflow` with typed kwargs."""
    tool_name = "run_task" if entry.category == "task" else "run_workflow"
    kwarg_name = "task_name" if entry.category == "task" else "workflow_name"
    bindings = dict(typed_plan.get("resolved_inputs") or {})
    binding_plan = typed_plan.get("binding_plan") or {}
    runtime_bindings = (
        dict(binding_plan.get("runtime_bindings") or {})
        if isinstance(binding_plan, Mapping)
        else {}
    )
    kwargs: dict[str, object] = {
        kwarg_name: entry.name,
        "bindings": bindings,
        "inputs": runtime_bindings,
        "source_prompt": request,
    }
    limitations = tuple(str(item) for item in typed_plan.get("limitations") or ())
    return PlanSuccess(
        supported=True,
        target=entry.name,
        pipeline_family=entry.compatibility.pipeline_family,
        biological_goal=str(typed_plan.get("biological_goal") or entry.name),
        requires_user_approval=False,
        bindings=bindings,
        scalar_inputs=runtime_bindings,
        composition_stages=(),
        artifact_path="",
        suggested_next_call={"tool": tool_name, "kwargs": kwargs},
        limitations=limitations,
    )


def _plan_success_composed(
    goal: TypedPlanningGoal,
    typed_plan: Mapping[str, object],
    *,
    artifact_path: Path,
) -> PlanSuccess:
    """Build a freeze-and-approve PlanSuccess for a planner-composed novel DAG."""
    bindings = dict(typed_plan.get("resolved_inputs") or {})
    binding_plan = typed_plan.get("binding_plan") or {}
    runtime_bindings = (
        dict(binding_plan.get("runtime_bindings") or {})
        if isinstance(binding_plan, Mapping)
        else {}
    )
    existing = tuple(str(item) for item in typed_plan.get("limitations") or ())
    advisory = (
        "This is a planner-composed novel DAG; requires_user_approval=True. "
        "Call approve_composed_recipe(artifact_path=...) before run_local_recipe / run_slurm_recipe."
    )
    return PlanSuccess(
        supported=True,
        target=_composition_target_name(goal),
        pipeline_family=_pipeline_family_for_goal(goal),
        biological_goal=str(typed_plan.get("biological_goal") or goal.name),
        requires_user_approval=True,
        bindings=bindings,
        scalar_inputs=runtime_bindings,
        composition_stages=tuple(goal.target_entry_names),
        artifact_path=str(artifact_path),
        suggested_next_call={
            "tool": "approve_composed_recipe",
            "kwargs": {"artifact_path": str(artifact_path)},
        },
        limitations=existing + (advisory,),
    )


def plan_request_reshape(
    request: str,
    *,
    explicit_bindings: Mapping[str, Any] | None = None,
    manifest_sources: Sequence[Path | Mapping[str, Any]] = (),
    result_bundles: Sequence[Any] = (),
    scalar_inputs: Mapping[str, Any] | None = None,
    runtime_bindings: Mapping[str, Any] | None = None,
    resource_request: Mapping[str, Any] | ResourceSpec | None = None,
    execution_profile: str | None = None,
    runtime_image: Mapping[str, Any] | RuntimeImageSpec | str | None = None,
    runtime_images: Mapping[str, Any] | None = None,
    tool_databases: Mapping[str, Any] | None = None,
    bundle_overrides: Mapping[str, Any] | None = None,
    resolver: AssetResolver | None = None,
    recipe_dir: Path | None = None,
    created_at: str | None = None,
) -> PlanSuccess | PlanDecline:
    """Plan one free-text request with asymmetric freeze semantics (§3j).

    Single-entry deterministic matches return a :class:`PlanSuccess` without
    touching the filesystem; ``artifact_path`` is empty and
    ``suggested_next_call`` re-issues the matching ``run_task`` / ``run_workflow``
    call so the freeze happens once, at commit time, with the final inputs.

    Composition fallback freezes a :class:`WorkflowSpec` artifact to
    ``recipe_dir`` because the composed DAG has no single structured call; the
    returned :class:`PlanSuccess` carries the artifact path and points at
    ``approve_composed_recipe`` per the M15 P2 approval gate.

    Declines return a :class:`PlanDecline` with §10 recovery channels populated:
    available bundles, durable prior runs (empty here), and next-step hints.

    Args:
        request: Natural-language biological request from the scientist.
        recipe_dir: Directory for composed-recipe artifacts. Defaults to
            ``.runtime/specs`` under the repository root; tests should pass a
            temporary directory to keep the repo free of leftover previews.
        created_at: Frozen UTC timestamp injected into composed artifacts;
            defaults to the current moment. Tests may set this for
            deterministic diffs.
    """
    matched = _match_target(request, _showcase_registry_entries())

    if isinstance(matched, RegistryEntry):
        typed_plan = plan_typed_request(
            biological_goal=request,
            target_name=matched.name,
            source_prompt=request,
            explicit_bindings=explicit_bindings,
            manifest_sources=manifest_sources,
            result_bundles=result_bundles,
            scalar_inputs=scalar_inputs,
            runtime_bindings=runtime_bindings,
            resource_request=resource_request,
            execution_profile=execution_profile,
            runtime_image=runtime_image,
            runtime_images=runtime_images,
            tool_databases=tool_databases,
            bundle_overrides=bundle_overrides,
            resolver=resolver,
        )
        if not typed_plan.get("supported"):
            return _plan_decline(
                target=matched.name,
                pipeline_family=matched.compatibility.pipeline_family,
                reason=_decline_reason_from_typed_plan(typed_plan),
                suggested_for_entry=matched.name,
            )
        return _plan_success_single_entry(matched, typed_plan, request=request)

    if isinstance(matched, AmbiguousMatch):
        names = [entry.name for entry in matched.entries]
        pipeline_family = (
            matched.entries[0].compatibility.pipeline_family if matched.entries else ""
        )
        return _plan_decline(
            reason=f"Ambiguous target: biological_goal resolved to {len(names)} entries: {names}.",
            pipeline_family=pipeline_family,
        )

    normalized_request = _normalize(request)
    variant_target = _match_variant_calling_target(normalized_request)
    if variant_target is not None:
        return _plan_decline(
            reason=(
                f"Variant-calling prompt matched target `{variant_target}`; "
                f"use run_workflow or run_task with that target directly."
            ),
            pipeline_family="variant_calling",
            next_steps=(
                f"Call load_bundle('variant_calling_germline_minimal') to get starter inputs.",
                f"Then call run_workflow('{variant_target}', **bundle) or run_task('{variant_target}', **bundle).",
                "Or supply explicit bindings and scalar inputs directly to run_workflow/run_task.",
            ),
        )

    composition_goal = _try_composition_fallback(request, normalized_request)
    if composition_goal is None:
        return _plan_decline(
            reason=(
                "The request does not map to a supported typed biology goal, "
                "so the planner declines instead of inventing steps."
            ),
        )

    typed_plan = _typed_plan_from_goal(
        composition_goal,
        original_request=request,
        source_prompt=request,
        explicit_bindings=explicit_bindings,
        manifest_sources=manifest_sources,
        result_bundles=result_bundles,
        scalar_inputs=scalar_inputs,
        runtime_bindings=runtime_bindings,
        resource_request=resource_request,
        execution_profile=execution_profile,
        runtime_image=runtime_image,
        runtime_images=runtime_images,
        tool_databases=tool_databases,
        bundle_overrides=bundle_overrides,
        resolver=resolver,
    )
    if not typed_plan.get("supported"):
        missing = [str(item) for item in typed_plan.get("missing_requirements") or ()]
        return _plan_decline(
            reason=_decline_reason_from_typed_plan(typed_plan),
            pipeline_family=_pipeline_family_for_goal(composition_goal),
            extra_limitations=missing[:3],
        )

    target_stem = _composition_target_name(composition_goal)
    destination_dir = recipe_dir or DEFAULT_RECIPE_DIR
    destination = destination_dir / f"{make_recipe_id(target_stem)}.json"
    artifact = artifact_from_typed_plan(
        typed_plan,
        created_at=created_at or _current_plan_timestamp(),
        replay_metadata={"mcp_tool": "plan_request"},
    )
    saved_path = save_workflow_spec_artifact(artifact, destination)
    return _plan_success_composed(composition_goal, typed_plan, artifact_path=saved_path)


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
