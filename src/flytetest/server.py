"""Stdio MCP server for recipe-backed FLyteTest planning and execution.

    This module exposes a recipe-first MCP surface: prompts are planned into typed
    workflow specs, saved as inspectable artifacts, and then executed locally
    through explicit node handlers.
"""

from __future__ import annotations

import hashlib
import inspect
from importlib import import_module
import os
import shlex
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from collections.abc import Mapping, Sequence
from io import TextIOWrapper
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

from flytetest.mcp_contract import (
    DECLINE_CATEGORY_CODES,
    EXAMPLE_PROMPT_REQUIREMENTS,
    LIST_ENTRIES_LIMITATIONS,
    MCP_RESOURCE_URIS,
    MCP_TOOL_NAMES,
    RECIPE_INPUT_BINDING_RULES,
    RECIPE_INPUT_CONTEXT_FIELDS,
    RECIPE_INPUT_MANIFEST_RULES,
    RECIPE_INPUT_RUNTIME_RULES,
    PRIMARY_TOOL_NAME,
    PROMPT_REQUIREMENTS,
    PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
    RETRY_SLURM_JOB_TOOL_NAME,
    RUN_SLURM_RECIPE_TOOL_NAME,
    RESULT_CODE_DECLINED_MISSING_INPUTS,
    RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST,
    RESULT_CODE_DEFINITIONS,
    RESULT_CODE_FAILED_EXECUTION,
    RESULT_CODE_SUCCEEDED,
    RESULT_SUMMARY_FIELDS,
    REASON_CODE_COMPLETED,
    REASON_CODE_MISSING_REQUIRED_INPUTS,
    REASON_CODE_NONZERO_EXIT_STATUS,
    REASON_CODE_UNSUPPORTED_EXECUTION_TARGET,
    REASON_CODE_UNSUPPORTED_OR_AMBIGUOUS_REQUEST,
    SHOWCASE_SERVER_NAME,
    SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME,
    SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME,
    SUPPORTED_AGAT_WORKFLOW_NAME,
    SUPPORTED_BUSCO_WORKFLOW_NAME,
    SUPPORTED_EGGNOG_WORKFLOW_NAME,
    SUPPORTED_PROTEIN_WORKFLOW_NAME,
    SUPPORTED_TARGET_NAMES,
    SUPPORTED_TASK_NAME,
    SUPPORTED_WORKFLOW_NAMES,
    SUPPORTED_WORKFLOW_NAME,
    TASK_EXAMPLE_PROMPT,
    WORKFLOW_EXAMPLE_PROMPT,
    supported_runnable_targets_payload,
)
from flytetest.planning import (
    plan_typed_request,
    showcase_limitations,
    split_entry_inputs,
    supported_entry_parameters,
)
from flytetest.registry import RegistryEntry, get_entry
from flytetest.spec_artifacts import artifact_from_typed_plan, save_workflow_spec_artifact
from flytetest.spec_executor import (
    LocalNodeExecutionRequest,
    LocalSpecExecutionResult,
    SlurmRetryResult,
    LocalWorkflowSpecExecutor,
    SlurmLifecycleResult,
    SlurmSpecExecutionResult,
    SlurmWorkflowSpecExecutor,
    _command_is_available,
)
from flytetest.specs import ResourceSpec, RuntimeImageSpec


REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "flyte_rnaseq_workflow.py"
DEFAULT_RECIPE_DIR = REPO_ROOT / ".runtime" / "specs"
DEFAULT_RUN_DIR = REPO_ROOT / ".runtime" / "runs"
SERVER_TOOL_NAMES = MCP_TOOL_NAMES
SERVER_RESOURCE_URIS = MCP_RESOURCE_URIS
BUSCO_FIXTURE_TASK_NAME = "busco_assess_proteins"


def _resolve_flyte_cli() -> str:
    """Resolve the Flyte CLI, preferring the repo-local virtualenv binary.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `str` result computed by this helper.
"""
    repo_flyte = REPO_ROOT / ".venv" / "bin" / "flyte"
    if repo_flyte.exists():
        return str(repo_flyte)

    resolved = shutil.which("flyte")
    return resolved if resolved is not None else "flyte"


def _supported_runnable_targets() -> list[dict[str, str]]:
    """Return the exact runnable target list exposed through the showcase.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `list[dict[str, str]]` result computed by this helper.
"""
    return supported_runnable_targets_payload()


def _entry_payload(name: str) -> dict[str, object]:
    """Serialize one supported showcase target for stable tool responses.

    Args:
        name: Registry entry, planner type, or target name being looked up.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    entry: RegistryEntry = get_entry(name)
    required_inputs, optional_inputs = split_entry_inputs(name)
    return {
        "name": entry.name,
        "category": entry.category,
        "description": entry.description,
        "required_inputs": [asdict(field) for field in required_inputs],
        "optional_inputs": [asdict(field) for field in optional_inputs],
        "outputs": [asdict(field) for field in entry.outputs],
    }


def _supported_entry_payloads() -> list[dict[str, object]]:
    """Return the stable serialized target list shared by tools and resources.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `list[dict[str, object]]` result computed by this helper.
"""
    return [_entry_payload(name) for name in SUPPORTED_TARGET_NAMES]


def _normalize_manifest_sources(manifest_sources: Sequence[str | Path] | None) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    """Validate manifest-source paths before typed planning runs.

    Args:
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.

    Returns:
        A `tuple[tuple[Path, ...], tuple[str, ...]]` result computed by this helper.
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
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        runtime_bindings: Frozen runtime inputs supplied alongside planner-discovered values.
        resource_request: Caller-supplied compute resource policy or override.
        execution_profile: Named execution profile requested or selected for the recipe.
        runtime_image: Caller-supplied runtime image policy or override.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        limitations: Recorded limitations that explain why a request was declined or constrained.
        recipe_input_context: The `recipe_input_context` input processed by this helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
    """Return the exact `flyte run` CLI flag spelling for one workflow input.

    Args:
        name: Registry entry, planner type, or target name being looked up.

    Returns:
        A `str` result computed by this helper.
"""
    return f"--{name}"


def _extract_output_paths(*streams: str) -> list[str]:
    """Collect existing absolute filesystem paths mentioned in command output.

    Args:
        streams: The `streams` input processed by this helper.

    Returns:
        A `list[str]` result computed by this helper.
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
    """Return whether one workflow input payload should bypass `flyte run`.

    Args:
        inputs: The inputs forwarded to the workflow or task helper.

    Returns:
        A `bool` result computed by this helper.
"""
    return any(isinstance(value, (list, tuple, dict)) for value in inputs.values())


def _is_flyte_file_annotation(annotation: Any) -> bool:
    """Return whether one annotation represents `flyte.io.File`.

    Args:
        annotation: Type annotation being inspected by the serializer.

    Returns:
        A `bool` result computed by this helper.
"""
    from flyte.io import File

    return annotation is File or get_origin(annotation) is File


def _is_flyte_dir_annotation(annotation: Any) -> bool:
    """Return whether one annotation represents `flyte.io.Dir`.

    Args:
        annotation: Type annotation being inspected by the serializer.

    Returns:
        A `bool` result computed by this helper.
"""
    from flyte.io import Dir

    return annotation is Dir or get_origin(annotation) is Dir


def _coerce_direct_workflow_input(annotation: Any, value: Any) -> Any:
    """Convert local path inputs into the objects expected by direct workflow calls.

    Args:
        annotation: Type annotation being inspected by the serializer.
        value: The value or values processed by the helper.

    Returns:
        A `Any` result computed by this helper.
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
    """Import one runnable showcase workflow by name.

    Args:
        workflow_name: The registered workflow or task name forwarded by the caller.

    Returns:
        A `Any` result computed by this helper.
"""
    from flytetest.mcp_contract import SHOWCASE_TARGETS_BY_NAME

    target = SHOWCASE_TARGETS_BY_NAME.get(workflow_name)
    if target is None or target.category != "workflow":
        raise ValueError(f"No runnable showcase workflow metadata is registered for `{workflow_name}`.")

    module = import_module(target.module_name)
    workflow = getattr(module, workflow_name, None)
    if workflow is None:
        raise AttributeError(f"Workflow `{workflow_name}` is not exported from `{target.module_name}`.")
    return workflow


def _prepare_direct_workflow_inputs(workflow: Any, inputs: Mapping[str, object]) -> dict[str, object]:
    """Build one direct-call argument payload from plain local path values.

    Args:
        workflow: Workflow object or workflow metadata being adapted.
        inputs: The inputs forwarded to the workflow or task helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        value: The value or values processed by the helper.

    Returns:
        A `list[str]` result computed by this helper.
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
        workflow_name: The registered workflow or task name forwarded by the caller.
        inputs: The inputs forwarded to the workflow or task helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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


def list_entries() -> dict[str, object]:
    """List the day-one MCP recipe execution targets.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return {
        "entries": _supported_entry_payloads(),
        "server_tools": list(SERVER_TOOL_NAMES),
        "limitations": list(LIST_ENTRIES_LIMITATIONS),
    }


def resource_scope() -> dict[str, object]:
    """Describe the MCP recipe contract for read-only client discovery.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
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
    """Expose the exact day-one recipe target metadata.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return {
        "primary_tool": PRIMARY_TOOL_NAME,
        "entries": _supported_entry_payloads(),
        "limitations": list(showcase_limitations()),
    }


def resource_example_prompts() -> dict[str, object]:
    """Provide small prompt examples that match the day-one recipe surface.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return {
        "primary_tool": PRIMARY_TOOL_NAME,
        "workflow_prompt": WORKFLOW_EXAMPLE_PROMPT,
        "protein_workflow_prompt": PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
        "task_prompt": TASK_EXAMPLE_PROMPT,
        "prompt_requirements": list(EXAMPLE_PROMPT_REQUIREMENTS),
    }


def resource_prompt_and_run_contract() -> dict[str, object]:
    """Document the recipe-backed `prompt_and_run` summary contract.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
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


def _typed_planning_preview(prompt: str) -> dict[str, object]:
    """Return additive typed-planning metadata for MCP responses.

    Args:
        prompt: Natural-language prompt being planned or frozen into a recipe.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return plan_typed_request(prompt)


def plan_request(prompt: str) -> dict[str, object]:
    """Plan one request through the typed recipe planner.

    Args:
        prompt: Natural-language prompt being planned or frozen into a recipe.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return _typed_planning_preview(prompt)


def run_workflow(
    workflow_name: str,
    inputs: dict[str, object],
    runner: Any = subprocess.run,
) -> dict[str, object]:
    """Execute one supported workflow through `flyte run` or direct Python.

    Args:
        workflow_name: The registered workflow or task name forwarded by the caller.
        inputs: The inputs forwarded to the workflow or task helper.
        runner: Injected command runner used to execute the helper workflow.

    Returns:
        A `dict[str, object]` result computed by this helper.
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


def run_task(task_name: str, inputs: dict[str, object]) -> dict[str, object]:
    """Execute one supported direct task through a Python call.

    Args:
        task_name: The registered workflow or task name forwarded by the caller.
        inputs: The inputs forwarded to the workflow or task helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    if task_name not in {SUPPORTED_TASK_NAME, BUSCO_FIXTURE_TASK_NAME}:
        return {
            "supported": False,
            "task_name": task_name,
            "exit_status": None,
            "output_paths": [],
            "limitations": [
                (
                    "Only "
                    f"`{SUPPORTED_TASK_NAME}` and `{BUSCO_FIXTURE_TASK_NAME}` "
                    "are executable through this showcase task runner."
                ),
            ],
        }

    if task_name == BUSCO_FIXTURE_TASK_NAME:
        parameters = (
            ("proteins_fasta", True),
            ("lineage_dataset", True),
            ("busco_sif", False),
            ("busco_cpu", False),
            ("busco_mode", False),
        )
    else:
        parameters = tuple((parameter.name, parameter.required) for parameter in supported_entry_parameters(task_name))
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

    if task_name == BUSCO_FIXTURE_TASK_NAME:
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


def _jsonable(value: Any) -> Any:
    """Convert paths and nested containers into JSON-compatible values.

    Args:
        value: The value or values processed by the helper.

    Returns:
        A `Any` result computed by this helper.
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
        execution_result: A directory path used by the helper.

    Returns:
        A `str` result computed by this helper.
"""
    output_paths = execution_result.get("output_paths", [])
    if isinstance(output_paths, list) and output_paths:
        return str(output_paths[0])
    return ""


def _local_node_handlers(
    *,
    workflow_runner: Any = run_workflow,
    task_runner: Any = run_task,
) -> dict[str, Any]:
    """Build explicit node handlers for the day-one MCP execution targets.

    Args:
        workflow_runner: Injected workflow execution function used by the adapter.
        task_runner: Injected task execution function used by the adapter.

    Returns:
        A `dict[str, Any]` result computed by this helper.
"""

    def workflow_handler(request: LocalNodeExecutionRequest) -> dict[str, object]:
        """Run one workflow target through the local execution adapter.

    Args:
        request: The local execution request forwarded by the caller.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        request: The local execution request forwarded by the caller.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        SUPPORTED_WORKFLOW_NAME: workflow_handler,
        SUPPORTED_PROTEIN_WORKFLOW_NAME: workflow_handler,
        SUPPORTED_BUSCO_WORKFLOW_NAME: workflow_handler,
        SUPPORTED_EGGNOG_WORKFLOW_NAME: workflow_handler,
        SUPPORTED_AGAT_WORKFLOW_NAME: workflow_handler,
        SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME: workflow_handler,
        SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME: workflow_handler,
        SUPPORTED_TASK_NAME: task_handler,
        BUSCO_FIXTURE_TASK_NAME: task_handler,
    }


def _created_at() -> str:
    """Return a stable UTC timestamp for saved recipe metadata.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `str` result computed by this helper.
"""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _recipe_artifact_destination(prompt: str, *, recipe_dir: Path | None = None) -> Path:
    """Build a readable unique path for one frozen recipe artifact.

    Args:
        prompt: Natural-language prompt being planned or frozen into a recipe.
        recipe_dir: A directory path used by the helper.

    Returns:
        A `Path` result computed by this helper.
"""
    created = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    return (recipe_dir or DEFAULT_RECIPE_DIR) / f"{created}-{digest}.json"


def _limitations_from_typed_plan(plan: dict[str, object]) -> list[str]:
    """Return concise limitations for unsupported typed-plan payloads.

    Args:
        plan: Typed planning result being summarized.

    Returns:
        A `list[str]` result computed by this helper.
"""
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
        result: A directory path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        result: A directory path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        result: A directory path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        result: A directory path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        runtime_bindings: Frozen runtime inputs supplied alongside planner-discovered values.
        resource_request: Caller-supplied compute resource policy or override.
        execution_profile: Named execution profile requested or selected for the recipe.
        runtime_image: Caller-supplied runtime image policy or override.
        recipe_dir: A directory path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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

    typed_plan = plan_typed_request(
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

    created_at = _created_at()
    artifact = artifact_from_typed_plan(
        typed_plan,
        created_at=created_at,
        replay_metadata={"mcp_tool": "prepare_run_recipe"},
    )
    artifact_path = save_workflow_spec_artifact(
        artifact,
        _recipe_artifact_destination(prompt, recipe_dir=recipe_dir),
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
    """Plan one prompt and save a frozen workflow-spec recipe artifact.

    Args:
        prompt: Natural-language prompt being planned or frozen into a recipe.
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        runtime_bindings: Frozen runtime inputs supplied alongside planner-discovered values.
        resource_request: Caller-supplied compute resource policy or override.
        execution_profile: Named execution profile requested or selected for the recipe.
        runtime_image: Caller-supplied runtime image policy or override.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
) -> dict[str, object]:
    """Execute one frozen workflow-spec recipe through local node handlers.

    Args:
        artifact_path: A filesystem path used by the helper.
        handlers: The `handlers` input processed by this helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    try:
        result = LocalWorkflowSpecExecutor(handlers or _local_node_handlers()).execute(Path(artifact_path))
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
    """Run a previously frozen workflow-spec recipe artifact.

    Args:
        artifact_path: A filesystem path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return _run_local_recipe_impl(artifact_path)


def _run_slurm_recipe_impl(
    artifact_path: str | Path,
    *,
    run_dir: Path | None = None,
    sbatch_runner: Any = subprocess.run,
    command_available: Any = None,
) -> dict[str, object]:
    """Submit one frozen workflow-spec recipe through `sbatch`.

    Args:
        artifact_path: A filesystem path used by the helper.
        run_dir: A directory path used by the helper.
        sbatch_runner: Injected submission command runner used for Slurm submission.
        command_available: The `command_available` input processed by this helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    result = SlurmWorkflowSpecExecutor(
        run_root=run_dir or DEFAULT_RUN_DIR,
        repo_root=REPO_ROOT,
        sbatch_runner=sbatch_runner,
        command_available=command_available or _command_is_available,
    ).submit(Path(artifact_path))
    execution_result = _result_from_slurm_spec_execution(result)
    return {
        "supported": bool(result.supported),
        "artifact_path": str(artifact_path),
        "execution_result": execution_result,
        "run_record_path": str(result.run_record.run_record_path) if result.run_record is not None else None,
        "job_id": result.run_record.job_id if result.run_record is not None else None,
        "limitations": list(result.limitations),
    }


def run_slurm_recipe(artifact_path: str) -> dict[str, object]:
    """Submit a previously frozen workflow-spec recipe artifact to Slurm.

    Args:
        artifact_path: A filesystem path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return _run_slurm_recipe_impl(artifact_path)


def _monitor_slurm_job_impl(
    run_record_path: str | Path,
    *,
    run_dir: Path | None = None,
    scheduler_runner: Any = subprocess.run,
    command_available: Any = None,
) -> dict[str, object]:
    """Reconcile one Slurm job from its durable run record.

    Args:
        run_record_path: A filesystem path used by the helper.
        run_dir: A directory path used by the helper.
        scheduler_runner: Injected scheduler command runner used for status and cancellation.
        command_available: The `command_available` input processed by this helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    result = SlurmWorkflowSpecExecutor(
        run_root=run_dir or DEFAULT_RUN_DIR,
        repo_root=REPO_ROOT,
        scheduler_runner=scheduler_runner,
        command_available=command_available or _command_is_available,
    ).reconcile(Path(run_record_path))
    return {
        "supported": bool(result.supported),
        "run_record_path": str(run_record_path),
        "lifecycle_result": _result_from_slurm_lifecycle(result),
        "limitations": list(result.limitations),
    }


def monitor_slurm_job(run_record_path: str) -> dict[str, object]:
    """Inspect and reconcile a submitted Slurm job from its run record.

    Args:
        run_record_path: A filesystem path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return _monitor_slurm_job_impl(run_record_path)


def _cancel_slurm_job_impl(
    run_record_path: str | Path,
    *,
    run_dir: Path | None = None,
    scheduler_runner: Any = subprocess.run,
    command_available: Any = None,
) -> dict[str, object]:
    """Cancel one Slurm job from its durable run record.

    Args:
        run_record_path: A filesystem path used by the helper.
        run_dir: A directory path used by the helper.
        scheduler_runner: Injected scheduler command runner used for status and cancellation.
        command_available: The `command_available` input processed by this helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    result = SlurmWorkflowSpecExecutor(
        run_root=run_dir or DEFAULT_RUN_DIR,
        repo_root=REPO_ROOT,
        scheduler_runner=scheduler_runner,
        command_available=command_available or _command_is_available,
    ).cancel(Path(run_record_path))
    return {
        "supported": bool(result.supported),
        "run_record_path": str(run_record_path),
        "lifecycle_result": _result_from_slurm_lifecycle(result),
        "limitations": list(result.limitations),
    }


def cancel_slurm_job(run_record_path: str) -> dict[str, object]:
    """Request cancellation for a submitted Slurm job from its run record.

    Args:
        run_record_path: A filesystem path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return _cancel_slurm_job_impl(run_record_path)


def _retry_slurm_job_impl(
    run_record_path: str | Path,
    *,
    run_dir: Path | None = None,
    sbatch_runner: Any = subprocess.run,
    scheduler_runner: Any = subprocess.run,
    command_available: Any = None,
) -> dict[str, object]:
    """Retry one failed Slurm job from its durable run record.

    Args:
        run_record_path: A filesystem path used by the helper.
        run_dir: A directory path used by the helper.
        sbatch_runner: Injected submission command runner used for Slurm submission.
        scheduler_runner: Injected scheduler command runner used for status and cancellation.
        command_available: The `command_available` input processed by this helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    result = SlurmWorkflowSpecExecutor(
        run_root=run_dir or DEFAULT_RUN_DIR,
        repo_root=REPO_ROOT,
        sbatch_runner=sbatch_runner,
        scheduler_runner=scheduler_runner,
        command_available=command_available or _command_is_available,
    ).retry(Path(run_record_path))
    retry_run_record = result.retry_execution.run_record if result.retry_execution is not None else None
    return {
        "supported": bool(result.supported),
        "run_record_path": str(run_record_path),
        "retry_run_record_path": str(retry_run_record.run_record_path) if retry_run_record is not None else None,
        "job_id": retry_run_record.job_id if retry_run_record is not None else None,
        "retry_result": _result_from_slurm_retry(result),
        "limitations": list(result.limitations),
    }


def retry_slurm_job(run_record_path: str) -> dict[str, object]:
    """Retry a failed Slurm job from its durable run record.

    Args:
        run_record_path: A filesystem path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
"""
    return _retry_slurm_job_impl(run_record_path)


def _supported_target_names() -> list[str]:
    """Return the exact day-one recipe target names exposed through MCP.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `list[str]` result computed by this helper.
"""
    return list(SUPPORTED_TARGET_NAMES)


def _summary_used_inputs(plan: dict[str, object]) -> dict[str, object]:
    """Return the prompt-derived or frozen runtime inputs used for execution.

    Args:
        plan: Typed planning result being summarized.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
                SUPPORTED_BUSCO_WORKFLOW_NAME: "repeat_filter_results",
                SUPPORTED_EGGNOG_WORKFLOW_NAME: "repeat_filter_results",
                SUPPORTED_AGAT_WORKFLOW_NAME: "eggnog_results",
                SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME: "eggnog_results",
                SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME: "agat_conversion_results",
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
        execution_result: A directory path used by the helper.

    Returns:
        A `str | None` result computed by this helper.
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
        status: The `status` input processed by this helper.
        target_name: The `target_name` input processed by this helper.
        target_category: The `target_category` input processed by this helper.
        used_inputs: The `used_inputs` input processed by this helper.
        execution_result: A directory path used by the helper.
        decline_reason: The `decline_reason` input processed by this helper.
        declined_stages: Downstream stages intentionally not exposed for this prompt.

    Returns:
        A `str` result computed by this helper.
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
        execution_result: A directory path used by the helper.

    Returns:
        A `tuple[str, str]` result computed by this helper.
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
        execution_attempted: The `execution_attempted` input processed by this helper.
        execution_result: A directory path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        workflow_runner: Injected workflow execution function used by the adapter.
        task_runner: Injected task execution function used by the adapter.
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        runtime_bindings: Frozen runtime inputs supplied alongside planner-discovered values.
        resource_request: Caller-supplied compute resource policy or override.
        execution_profile: Named execution profile requested or selected for the recipe.
        runtime_image: Caller-supplied runtime image policy or override.
        recipe_dir: A directory path used by the helper.

    Returns:
        A `dict[str, object]` result computed by this helper.
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
        manifest_sources: Manifest paths or inline manifest mappings that may contain planner values.
        explicit_bindings: Caller-supplied planner values that should win over discovered inputs.
        runtime_bindings: Frozen runtime inputs supplied alongside planner-discovered values.
        resource_request: Caller-supplied compute resource policy or override.
        execution_profile: Named execution profile requested or selected for the recipe.
        runtime_image: Caller-supplied runtime image policy or override.

    Returns:
        A `dict[str, object]` result computed by this helper.
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


def _load_fastmcp() -> Any:
    """Import `FastMCP` lazily so helper tests can run without the SDK installed.

    This helper keeps the relevant planning or execution step explicit and easy to review.

    Returns:
        A `Any` result computed by this helper.
"""
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
        line: One stdio line being filtered before JSON parsing.

    Returns:
        A `bool` result computed by this helper.
"""
    return not line.strip()


@asynccontextmanager
async def _filtered_stdio_server():
    """Wrap stdio transport while ignoring blank client lines that break JSON-RPC parsing.

    This helper keeps the relevant planning or execution step explicit and easy to review.
"""
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
        """Read stdio messages, drop blank lines, and forward JSON-RPC payloads.

    This helper keeps the relevant planning or execution step explicit and easy to review.
"""
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
        """Serialize MCP session messages back to stdout for the transport.

    This helper keeps the relevant planning or execution step explicit and easy to review.
"""
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

    Returns:
        A `Any` result computed by this helper.
"""
    fastmcp = _load_fastmcp() if fastmcp_cls is None else fastmcp_cls
    mcp = fastmcp(SHOWCASE_SERVER_NAME)

    mcp.tool()(list_entries)
    mcp.tool()(plan_request)
    mcp.tool()(prepare_run_recipe)
    mcp.tool()(run_local_recipe)
    mcp.tool()(run_slurm_recipe)
    mcp.tool()(monitor_slurm_job)
    mcp.tool()(retry_slurm_job)
    mcp.tool()(cancel_slurm_job)
    mcp.tool()(prompt_and_run)
    mcp.resource(SERVER_RESOURCE_URIS[0])(resource_scope)
    mcp.resource(SERVER_RESOURCE_URIS[1])(resource_supported_targets)
    mcp.resource(SERVER_RESOURCE_URIS[2])(resource_example_prompts)
    mcp.resource(SERVER_RESOURCE_URIS[3])(resource_prompt_and_run_contract)
    return mcp


async def _run_stdio_server_async() -> None:
    """Run the FastMCP server over stdio with blank-line-tolerant input parsing.

    This helper keeps the relevant planning or execution step explicit and easy to review.
"""
    server = create_mcp_server()
    async with _filtered_stdio_server() as (read_stream, write_stream):
        await server._mcp_server.run(  # pyright: ignore[reportPrivateUsage]
            read_stream,
            write_stream,
            server._mcp_server.create_initialization_options(),  # pyright: ignore[reportPrivateUsage]
        )


def main() -> None:
    """Run the FastMCP server over stdio.

    This helper keeps the relevant planning or execution step explicit and easy to review.
"""
    try:
        import anyio

        anyio.run(_run_stdio_server_async)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
