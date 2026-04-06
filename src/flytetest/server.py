"""Narrow stdio MCP server for the FLyteTest showcase planner.

This module exposes exactly two prebuilt workflows and one task through
FastMCP-backed tools, plus a tiny read-only resource surface that documents
the current showcase contract. The conversational client owns the chat; this
server only lists the supported showcase entries, serves static scope
resources, plans prompt-contained local paths, and runs the matched workflow
or task when the prompt is runnable.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from io import TextIOWrapper
from pathlib import Path
from typing import Any

from flytetest.mcp_contract import (
    DECLINE_CATEGORY_CODES,
    DECLINED_DOWNSTREAM_STAGE_NAMES,
    DECLINED_PROMPT_EXAMPLE,
    EXAMPLE_PROMPT_REQUIREMENTS,
    LIST_ENTRIES_LIMITATIONS,
    MCP_RESOURCE_URIS,
    MCP_TOOL_NAMES,
    PRIMARY_TOOL_NAME,
    PROMPT_REQUIREMENTS,
    PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
    RESULT_CODE_DECLINED_DOWNSTREAM_SCOPE,
    RESULT_CODE_DECLINED_MISSING_INPUTS,
    RESULT_CODE_DECLINED_UNSUPPORTED_REQUEST,
    RESULT_CODE_DEFINITIONS,
    RESULT_CODE_FAILED_EXECUTION,
    RESULT_CODE_SUCCEEDED,
    RESULT_SUMMARY_FIELDS,
    REASON_CODE_COMPLETED,
    REASON_CODE_MISSING_REQUIRED_INPUTS,
    REASON_CODE_NONZERO_EXIT_STATUS,
    REASON_CODE_REQUESTED_DOWNSTREAM_STAGE,
    REASON_CODE_UNSUPPORTED_EXECUTION_TARGET,
    REASON_CODE_UNSUPPORTED_OR_AMBIGUOUS_REQUEST,
    SHOWCASE_SERVER_NAME,
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
    plan_request as plan_prompt,
    showcase_limitations,
    split_entry_inputs,
    supported_entry_parameters,
)
from flytetest.registry import RegistryEntry, get_entry


REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "flyte_rnaseq_workflow.py"
SERVER_TOOL_NAMES = MCP_TOOL_NAMES
SERVER_RESOURCE_URIS = MCP_RESOURCE_URIS


def _resolve_flyte_cli() -> str:
    """Resolve the Flyte CLI, preferring the repo-local virtualenv binary."""
    repo_flyte = REPO_ROOT / ".venv" / "bin" / "flyte"
    if repo_flyte.exists():
        return str(repo_flyte)

    resolved = shutil.which("flyte")
    return resolved if resolved is not None else "flyte"


def _supported_runnable_targets() -> list[dict[str, str]]:
    """Return the exact runnable target list exposed through the showcase."""
    return supported_runnable_targets_payload()


def _entry_payload(name: str) -> dict[str, object]:
    """Serialize one supported showcase target for stable tool responses."""
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
    """Return the stable serialized target list shared by tools and resources."""
    return [_entry_payload(name) for name in SUPPORTED_TARGET_NAMES]


def _workflow_command_flag(name: str) -> str:
    """Return the exact `flyte run` CLI flag spelling for one workflow input."""
    return f"--{name}"


def _extract_output_paths(*streams: str) -> list[str]:
    """Collect existing absolute filesystem paths mentioned in command output."""
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


def list_entries() -> dict[str, object]:
    """List the exact workflow and task supported by this MCP showcase."""
    return {
        "entries": _supported_entry_payloads(),
        "server_tools": list(SERVER_TOOL_NAMES),
        "limitations": list(LIST_ENTRIES_LIMITATIONS),
    }


def resource_scope() -> dict[str, object]:
    """Describe the narrow MCP showcase contract for read-only client discovery."""
    return {
        "server_name": SHOWCASE_SERVER_NAME,
        "transport": "stdio",
        "primary_tool": PRIMARY_TOOL_NAME,
        "tool_surface": list(SERVER_TOOL_NAMES),
        "supported_runnable_targets": _supported_runnable_targets(),
        "prompt_requirements": list(PROMPT_REQUIREMENTS),
        "declined_downstream_stages": list(DECLINED_DOWNSTREAM_STAGE_NAMES),
        "limitations": list(showcase_limitations()),
    }


def resource_supported_targets() -> dict[str, object]:
    """Expose the exact runnable target metadata for the narrow showcase."""
    return {
        "primary_tool": PRIMARY_TOOL_NAME,
        "entries": _supported_entry_payloads(),
        "limitations": list(showcase_limitations()),
    }


def resource_example_prompts() -> dict[str, object]:
    """Provide small prompt examples that match the current showcase surface."""
    return {
        "primary_tool": PRIMARY_TOOL_NAME,
        "workflow_prompt": WORKFLOW_EXAMPLE_PROMPT,
        "protein_workflow_prompt": PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
        "task_prompt": TASK_EXAMPLE_PROMPT,
        "declined_prompt_example": DECLINED_PROMPT_EXAMPLE,
        "prompt_requirements": list(EXAMPLE_PROMPT_REQUIREMENTS),
    }


def resource_prompt_and_run_contract() -> dict[str, object]:
    """Document the stable `prompt_and_run` summary contract for MCP clients."""
    return {
        "primary_tool": PRIMARY_TOOL_NAME,
        "supported_tools": list(SERVER_TOOL_NAMES),
        "supported_runnable_targets": _supported_runnable_targets(),
        "prompt_requirements": list(PROMPT_REQUIREMENTS),
        "declined_downstream_stages": list(DECLINED_DOWNSTREAM_STAGE_NAMES),
        "result_summary_fields": list(RESULT_SUMMARY_FIELDS),
        "result_codes": RESULT_CODE_DEFINITIONS,
        "decline_categories": DECLINE_CATEGORY_CODES,
        "limitations": list(showcase_limitations()),
    }


def plan_request(prompt: str) -> dict[str, object]:
    """Plan one natural-language request for the supported showcase targets."""
    return plan_prompt(prompt)


def run_workflow(
    workflow_name: str,
    inputs: dict[str, object],
    runner: Any = subprocess.run,
) -> dict[str, object]:
    """Execute one supported workflow through `flyte run --local`."""
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
                    f"`{SUPPORTED_WORKFLOW_NAME}` and `{SUPPORTED_PROTEIN_WORKFLOW_NAME}` "
                    "are executable through this showcase workflow runner."
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
                "EVM or later downstream annotation stages."
            ),
        ],
    }


def run_task(task_name: str, inputs: dict[str, object]) -> dict[str, object]:
    """Execute the one supported Exonerate chunk task through a direct Python call."""
    if task_name != SUPPORTED_TASK_NAME:
        return {
            "supported": False,
            "task_name": task_name,
            "exit_status": None,
            "output_paths": [],
            "limitations": [
                f"Only `{SUPPORTED_TASK_NAME}` is executable through this showcase task runner.",
            ],
        }

    parameters = supported_entry_parameters(task_name)
    allowed_inputs = tuple(parameter.name for parameter in parameters)
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
        parameter.name
        for parameter in parameters
        if parameter.required and inputs.get(parameter.name) in (None, "")
    ]
    if missing_required:
        return {
            "supported": False,
            "task_name": task_name,
            "exit_status": None,
            "output_paths": [],
            "limitations": [f"Missing required task inputs: {', '.join(missing_required)}."],
        }

    try:
        from flyte.io import File
        from flytetest.tasks.protein_evidence import exonerate_align_chunk

        result = exonerate_align_chunk(
            genome=File.from_local_sync(str(inputs["genome"])),
            protein_chunk=File.from_local_sync(str(inputs["protein_chunk"])),
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


def _supported_target_names() -> list[str]:
    """Return the exact runnable target names exposed by this showcase."""
    return list(SUPPORTED_TARGET_NAMES)


def _summary_used_inputs(plan: dict[str, object]) -> dict[str, object]:
    """Return only the explicit prompt-derived inputs used for execution planning."""
    extracted_inputs = plan.get("extracted_inputs", {})
    if not isinstance(extracted_inputs, dict):
        return {}
    return {name: value for name, value in extracted_inputs.items() if value not in (None, "")}


def _summary_failure_reason(execution_result: dict[str, object] | None) -> str | None:
    """Extract one short failure reason from an execution payload when present."""
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
    """Build one short client-facing sentence for the prompt-and-run result."""
    if status == "declined":
        if declined_stages:
            stage_text = ", ".join(f"`{stage}`" for stage in declined_stages)
            return (
                "Declined the request because it mentions downstream stages "
                f"{stage_text}, which are outside this MCP showcase."
            )
        if decline_reason and "missing explicit required inputs" in decline_reason.lower():
            return (
                f"Declined `{target_name}` because the prompt omitted explicit inputs "
                f"needed to run this showcase target: {', '.join(used_inputs) or 'required inputs'}."
            )
        if target_name and decline_reason:
            return f"Declined `{target_name}` because {decline_reason.rstrip('.')}."
        if decline_reason:
            return f"Declined the request because {decline_reason.rstrip('.')}."
        return "Declined the request because it falls outside the MCP showcase boundary."

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
    """Return stable machine-readable result and reason codes for one run."""
    declined_stages = plan.get("declined_downstream_stages", [])
    if isinstance(declined_stages, list) and declined_stages:
        return RESULT_CODE_DECLINED_DOWNSTREAM_SCOPE, REASON_CODE_REQUESTED_DOWNSTREAM_STAGE

    missing_inputs = plan.get("missing_required_inputs", [])
    if isinstance(missing_inputs, list) and missing_inputs:
        return RESULT_CODE_DECLINED_MISSING_INPUTS, REASON_CODE_MISSING_REQUIRED_INPUTS

    if not plan.get("supported", False):
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
    """Build the compact prompt-and-run summary for MCP client presentation."""
    target_name = plan.get("matched_entry_name")
    target_category = plan.get("matched_entry_category")
    used_inputs = _summary_used_inputs(plan)
    output_paths = execution_result.get("output_paths", []) if execution_result else []
    declined_stages = plan.get("declined_downstream_stages", [])
    decline_reason = None
    result_code, reason_code = _summary_codes(plan, execution_result)

    if not plan.get("supported", False):
        status = "declined"
        limitations = plan.get("limitations", [])
        if isinstance(limitations, list) and limitations:
            decline_reason = str(limitations[0])
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
        "execution_attempted": execution_attempted,
        "used_inputs": used_inputs,
        "output_paths": output_paths if isinstance(output_paths, list) else [],
        "exit_status": exit_status,
        "decline_reason": decline_reason,
        "declined_downstream_stages": declined_stages if isinstance(declined_stages, list) else [],
        "supported_targets": _supported_target_names(),
        "message": _summary_message(
            status=status,
            target_name=target_name if isinstance(target_name, str) else None,
            target_category=target_category if isinstance(target_category, str) else None,
            used_inputs=used_inputs,
            execution_result=execution_result,
            decline_reason=decline_reason,
            declined_stages=declined_stages if isinstance(declined_stages, list) else [],
        ),
    }


def _prompt_and_run_impl(
    prompt: str,
    workflow_runner: Any = run_workflow,
    task_runner: Any = run_task,
) -> dict[str, object]:
    """Plan one prompt and execute the matched supported target when runnable."""
    plan = plan_request(prompt)
    if not plan["supported"]:
        return {
            "supported": False,
            "original_request": prompt,
            "plan": plan,
            "execution_attempted": False,
            "execution_result": None,
            "result_summary": _build_result_summary(
                plan=plan,
                execution_attempted=False,
                execution_result=None,
            ),
            "limitations": list(plan["limitations"]),
        }

    entry_name = str(plan["matched_entry_name"])
    extracted_inputs = dict(plan["extracted_inputs"])
    if entry_name in {SUPPORTED_WORKFLOW_NAME, SUPPORTED_PROTEIN_WORKFLOW_NAME}:
        execution_result = workflow_runner(workflow_name=entry_name, inputs=extracted_inputs)
    elif entry_name == SUPPORTED_TASK_NAME:
        execution_result = task_runner(task_name=entry_name, inputs=extracted_inputs)
    else:
        execution_result = {
            "supported": False,
            "exit_status": None,
            "limitations": [f"Unsupported planned target `{entry_name}`."],
        }

    return {
        "supported": bool(plan["supported"] and execution_result["supported"]),
        "original_request": prompt,
        "plan": plan,
        "execution_attempted": True,
        "execution_result": execution_result,
        "result_summary": _build_result_summary(
            plan=plan,
            execution_attempted=True,
            execution_result=execution_result,
        ),
        "limitations": list(dict.fromkeys([*plan["limitations"], *execution_result.get("limitations", [])])),
    }


def prompt_and_run(prompt: str) -> dict[str, object]:
    """Plan one prompt and run the matched supported showcase target."""
    return _prompt_and_run_impl(prompt)


def _load_fastmcp() -> Any:
    """Import `FastMCP` lazily so helper tests can run without the SDK installed."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The `mcp` package is required to run the FLyteTest MCP server. "
            "Install it with `python3 -m pip install 'mcp[cli]'`."
        ) from exc
    return FastMCP


def _should_skip_stdio_line(line: str) -> bool:
    """Return whether one stdio input line should be ignored before JSON parsing."""
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
    """Build the narrow FastMCP server for stdio execution."""
    fastmcp = _load_fastmcp() if fastmcp_cls is None else fastmcp_cls
    mcp = fastmcp(SHOWCASE_SERVER_NAME)

    mcp.tool()(list_entries)
    mcp.tool()(plan_request)
    mcp.tool()(prompt_and_run)
    mcp.resource(SERVER_RESOURCE_URIS[0])(resource_scope)
    mcp.resource(SERVER_RESOURCE_URIS[1])(resource_supported_targets)
    mcp.resource(SERVER_RESOURCE_URIS[2])(resource_example_prompts)
    mcp.resource(SERVER_RESOURCE_URIS[3])(resource_prompt_and_run_contract)
    return mcp


async def _run_stdio_server_async() -> None:
    """Run the FastMCP server over stdio with blank-line-tolerant input parsing."""
    server = create_mcp_server()
    async with _filtered_stdio_server() as (read_stream, write_stream):
        await server._mcp_server.run(  # pyright: ignore[reportPrivateUsage]
            read_stream,
            write_stream,
            server._mcp_server.create_initialization_options(),  # pyright: ignore[reportPrivateUsage]
        )


def main() -> None:
    """Run the FastMCP server over stdio."""
    try:
        import anyio

        anyio.run(_run_stdio_server_async)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
