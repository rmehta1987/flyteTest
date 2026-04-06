"""Synthetic tests for the narrow FLyteTest MCP showcase server.

These checks keep the server transport MCP-shaped while preserving the hard
scope limit of two workflows and one task.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest.mcp_contract import (
    DECLINE_CATEGORY_CODES,
    DECLINED_DOWNSTREAM_STAGE_NAMES,
    DECLINED_PROMPT_EXAMPLE,
    MCP_RESOURCE_URIS,
    MCP_TOOL_NAMES,
    PRIMARY_TOOL_NAME,
    PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
    RESULT_CODE_DEFINITIONS,
    SHOWCASE_SERVER_NAME,
    SUPPORTED_PROTEIN_WORKFLOW_NAME,
    SUPPORTED_TARGET_NAMES,
    SUPPORTED_TASK_NAME,
    SUPPORTED_WORKFLOW_NAME,
    TASK_EXAMPLE_PROMPT,
    WORKFLOW_EXAMPLE_PROMPT,
    supported_runnable_targets_payload,
)
from flytetest.server import (
    SERVER_RESOURCE_URIS,
    _prompt_and_run_impl,
    _resolve_flyte_cli,
    _should_skip_stdio_line,
    create_mcp_server,
    list_entries,
    plan_request,
    prompt_and_run,
    resource_example_prompts,
    resource_prompt_and_run_contract,
    resource_scope,
    resource_supported_targets,
    run_workflow,
)

EXPECTED_TARGET_NAMES = list(SUPPORTED_TARGET_NAMES)
EXPECTED_RUNNABLE_TARGETS = supported_runnable_targets_payload()


class FakeFastMCP:
    """Small FastMCP stand-in used to capture tool registration."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, object] = {}
        self.resources: dict[str, object] = {}
        self.ran = False

    def tool(self):  # type: ignore[no-untyped-def]
        """Return a decorator that records the registered tool callable."""

        def decorator(fn):  # type: ignore[no-untyped-def]
            self.tools[fn.__name__] = fn
            return fn

        return decorator

    def resource(self, uri: str):  # type: ignore[no-untyped-def]
        """Return a decorator that records the registered resource callable."""

        def decorator(fn):  # type: ignore[no-untyped-def]
            self.resources[uri] = fn
            return fn

        return decorator

    def run(self) -> None:
        """Record that server execution was requested."""
        self.ran = True


class ServerTests(TestCase):
    """Coverage for the FastMCP surface and narrow showcase behavior."""

    def test_create_mcp_server_registers_only_the_required_tools(self) -> None:
        """Keep the MCP tool surface limited to list, plan, and prompt-and-run."""
        server = create_mcp_server(fastmcp_cls=FakeFastMCP)

        self.assertEqual(server.name, SHOWCASE_SERVER_NAME)
        self.assertEqual(sorted(server.tools), sorted(MCP_TOOL_NAMES))

    def test_create_mcp_server_registers_the_read_only_resources(self) -> None:
        """Expose only the small static resource layer for MCP client discovery."""
        server = create_mcp_server(fastmcp_cls=FakeFastMCP)

        self.assertEqual(tuple(SERVER_RESOURCE_URIS), MCP_RESOURCE_URIS)
        self.assertEqual(sorted(server.resources), sorted(MCP_RESOURCE_URIS))

    def test_blank_stdio_lines_are_ignored_before_json_parsing(self) -> None:
        """Ignore whitespace-only stdio lines so tolerant clients do not break the server."""
        self.assertTrue(_should_skip_stdio_line("\n"))
        self.assertTrue(_should_skip_stdio_line("   \t  \n"))
        self.assertFalse(_should_skip_stdio_line('{"jsonrpc":"2.0"}\n'))

    def test_list_entries_exposes_only_the_supported_targets(self) -> None:
        """List exactly the two workflows and one task in scope for the showcase."""
        payload = list_entries()

        self.assertEqual([entry["name"] for entry in payload["entries"]], EXPECTED_TARGET_NAMES)
        self.assertEqual(payload["server_tools"], list(MCP_TOOL_NAMES))
        self.assertIn(f"only `{SUPPORTED_WORKFLOW_NAME}`", payload["limitations"][0])
        self.assertIn(f"`{SUPPORTED_PROTEIN_WORKFLOW_NAME}`", payload["limitations"][0])
        self.assertIn(f"`{SUPPORTED_TASK_NAME}`", payload["limitations"][0])

    def test_scope_resource_describes_the_hard_mcp_limit(self) -> None:
        """Describe the stdio showcase contract without implying broader support."""
        payload = resource_scope()

        self.assertEqual(payload["transport"], "stdio")
        self.assertEqual(payload["primary_tool"], PRIMARY_TOOL_NAME)
        self.assertEqual(payload["supported_runnable_targets"], EXPECTED_RUNNABLE_TARGETS)
        self.assertEqual(payload["declined_downstream_stages"], list(DECLINED_DOWNSTREAM_STAGE_NAMES))

    def test_supported_targets_resource_matches_the_exact_showcase_entries(self) -> None:
        """Keep the resource target list aligned with the tool-facing entry list."""
        payload = resource_supported_targets()

        self.assertEqual(payload["primary_tool"], PRIMARY_TOOL_NAME)
        self.assertEqual([entry["name"] for entry in payload["entries"]], EXPECTED_TARGET_NAMES)

    def test_example_prompts_resource_requires_explicit_local_paths(self) -> None:
        """Expose only small example prompts that match the narrow planner contract."""
        payload = resource_example_prompts()

        self.assertEqual(payload["primary_tool"], PRIMARY_TOOL_NAME)
        self.assertEqual(payload["workflow_prompt"], WORKFLOW_EXAMPLE_PROMPT)
        self.assertEqual(payload["protein_workflow_prompt"], PROTEIN_WORKFLOW_EXAMPLE_PROMPT)
        self.assertEqual(payload["task_prompt"], TASK_EXAMPLE_PROMPT)
        self.assertEqual(payload["declined_prompt_example"], DECLINED_PROMPT_EXAMPLE)
        self.assertIn("explicit local file paths", payload["prompt_requirements"][0])

    def test_prompt_and_run_contract_resource_matches_enforced_summary_behavior(self) -> None:
        """Document the stable result-summary contract without widening showcase scope."""
        payload = resource_prompt_and_run_contract()

        self.assertEqual(payload["primary_tool"], PRIMARY_TOOL_NAME)
        self.assertEqual(payload["supported_tools"], list(MCP_TOOL_NAMES))
        self.assertEqual(payload["supported_runnable_targets"], EXPECTED_RUNNABLE_TARGETS)
        self.assertIn("result_code", payload["result_summary_fields"])
        self.assertIn("reason_code", payload["result_summary_fields"])
        self.assertEqual(
            payload["result_codes"]["declined_downstream_scope"]["reason_codes"],
            RESULT_CODE_DEFINITIONS["declined_downstream_scope"]["reason_codes"],
        )
        self.assertEqual(
            payload["result_codes"]["failed_execution"]["reason_codes"],
            RESULT_CODE_DEFINITIONS["failed_execution"]["reason_codes"],
        )
        self.assertEqual(payload["decline_categories"], DECLINE_CATEGORY_CODES)
        self.assertEqual(payload["declined_downstream_stages"], list(DECLINED_DOWNSTREAM_STAGE_NAMES))
        self.assertIn("explicit local file paths", payload["prompt_requirements"][0])

    def test_plan_request_extracts_workflow_paths_from_prompt(self) -> None:
        """Classify the BRAKER3 prompt and bind only its explicit local paths."""
        prompt = (
            "Annotate the genome sequence of a small eukaryote using BRAKER3 "
            "with genome data/genome.fa, RNA-seq evidence data/RNAseq.bam, "
            "and protein evidence data/proteins.fa"
        )

        payload = plan_request(prompt)

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_name"], SUPPORTED_WORKFLOW_NAME)
        self.assertEqual(
            payload["extracted_inputs"],
            {
                "genome": "data/genome.fa",
                "rnaseq_bam_path": "data/RNAseq.bam",
                "protein_fasta_path": "data/proteins.fa",
            },
        )
        self.assertEqual(payload["declined_downstream_stages"], [])

    def test_plan_request_extracts_protein_workflow_paths_from_prompt(self) -> None:
        """Classify the protein-evidence prompt and preserve protein FASTA order."""
        prompt = (
            "Run protein evidence alignment with genome data/genome.fa, "
            "protein evidence data/proteins.fa, and protein evidence data/proteins_extra.fa"
        )

        payload = plan_request(prompt)

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_name"], SUPPORTED_PROTEIN_WORKFLOW_NAME)
        self.assertEqual(
            payload["extracted_inputs"],
            {
                "genome": "data/genome.fa",
                "protein_fastas": ["data/proteins.fa", "data/proteins_extra.fa"],
            },
        )

    def test_prompt_and_run_workflow_prompt_uses_extracted_inputs(self) -> None:
        """Plan and dispatch the BRAKER3 example prompt through the workflow runner."""
        prompt = (
            "Annotate the genome sequence of a small eukaryote using BRAKER3 "
            "with genome data/genome.fa, RNA-seq evidence data/RNAseq.bam, "
            "and protein evidence data/proteins.fa"
        )
        captured: dict[str, object] = {}

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            captured["workflow_name"] = workflow_name
            captured["inputs"] = inputs
            return {
                "supported": True,
                "entry_name": workflow_name,
                "entry_category": "workflow",
                "execution_mode": "synthetic-test",
                "exit_status": 0,
                "stdout": "",
                "stderr": "",
                "output_paths": ["/tmp/braker3_results"],
                "limitations": [],
            }

        payload = _prompt_and_run_impl(prompt, workflow_runner=fake_workflow_runner)

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertEqual(captured["workflow_name"], SUPPORTED_WORKFLOW_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "genome": "data/genome.fa",
                "rnaseq_bam_path": "data/RNAseq.bam",
                "protein_fasta_path": "data/proteins.fa",
            },
        )
        self.assertEqual(payload["execution_result"]["exit_status"], 0)
        self.assertEqual(payload["result_summary"]["status"], "succeeded")
        self.assertEqual(payload["result_summary"]["result_code"], "succeeded")
        self.assertEqual(payload["result_summary"]["reason_code"], "completed")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_WORKFLOW_NAME)
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {
                "genome": "data/genome.fa",
                "rnaseq_bam_path": "data/RNAseq.bam",
                "protein_fasta_path": "data/proteins.fa",
            },
        )
        self.assertEqual(payload["result_summary"]["output_paths"], ["/tmp/braker3_results"])
        self.assertIn("execution succeeded", payload["result_summary"]["message"])

    def test_prompt_and_run_protein_workflow_prompt_uses_extracted_inputs(self) -> None:
        """Plan and dispatch the protein-evidence example prompt through the workflow runner."""
        prompt = (
            "Run protein evidence alignment with genome data/genome.fa and "
            "protein evidence data/proteins.fa"
        )
        captured: dict[str, object] = {}

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            captured["workflow_name"] = workflow_name
            captured["inputs"] = inputs
            return {
                "supported": True,
                "entry_name": workflow_name,
                "entry_category": "workflow",
                "execution_mode": "synthetic-test",
                "exit_status": 0,
                "stdout": "",
                "stderr": "",
                "output_paths": ["/tmp/protein_evidence_results"],
                "limitations": [],
            }

        payload = _prompt_and_run_impl(prompt, workflow_runner=fake_workflow_runner)

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertEqual(captured["workflow_name"], SUPPORTED_PROTEIN_WORKFLOW_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "genome": "data/genome.fa",
                "protein_fastas": ["data/proteins.fa"],
            },
        )
        self.assertEqual(payload["result_summary"]["status"], "succeeded")
        self.assertEqual(payload["result_summary"]["result_code"], "succeeded")
        self.assertEqual(payload["result_summary"]["reason_code"], "completed")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_PROTEIN_WORKFLOW_NAME)
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {
                "genome": "data/genome.fa",
                "protein_fastas": ["data/proteins.fa"],
            },
        )
        self.assertEqual(payload["result_summary"]["output_paths"], ["/tmp/protein_evidence_results"])

    def test_prompt_and_run_task_prompt_uses_extracted_inputs(self) -> None:
        """Plan and dispatch the Exonerate example prompt through the task runner."""
        prompt = (
            "Experiment with Exonerate protein-to-genome alignment using genome "
            "data/genome.fa and protein chunk data/proteins.fa"
        )
        captured: dict[str, object] = {}

        def fake_task_runner(task_name: str, inputs: dict[str, object]) -> dict[str, object]:
            captured["task_name"] = task_name
            captured["inputs"] = inputs
            return {
                "supported": True,
                "entry_name": task_name,
                "entry_category": "task",
                "execution_mode": "synthetic-test",
                "exit_status": 0,
                "stdout": "",
                "stderr": "",
                "output_paths": ["/tmp/exonerate_results"],
                "limitations": [],
            }

        payload = _prompt_and_run_impl(prompt, task_runner=fake_task_runner)

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertEqual(captured["task_name"], SUPPORTED_TASK_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "genome": "data/genome.fa",
                "protein_chunk": "data/proteins.fa",
            },
        )
        self.assertEqual(payload["execution_result"]["entry_category"], "task")
        self.assertEqual(payload["result_summary"]["status"], "succeeded")
        self.assertEqual(payload["result_summary"]["result_code"], "succeeded")
        self.assertEqual(payload["result_summary"]["reason_code"], "completed")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_TASK_NAME)
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {
                "genome": "data/genome.fa",
                "protein_chunk": "data/proteins.fa",
            },
        )
        self.assertEqual(payload["result_summary"]["output_paths"], ["/tmp/exonerate_results"])

    def test_prompt_and_run_declines_downstream_prompt(self) -> None:
        """Decline prompts that ask for downstream stages beyond the showcase scope."""
        prompt = (
            "Run protein evidence alignment with genome data/genome.fa and protein evidence data/proteins.fa, "
            "then continue into EVM and BUSCO."
        )

        payload = prompt_and_run(prompt)

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertIn("downstream stages", payload["plan"]["limitations"][0])
        self.assertEqual(payload["plan"]["declined_downstream_stages"], ["EVM", "BUSCO"])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertEqual(payload["result_summary"]["result_code"], "declined_downstream_scope")
        self.assertEqual(payload["result_summary"]["reason_code"], "requested_downstream_stage")
        self.assertEqual(payload["result_summary"]["declined_downstream_stages"], ["EVM", "BUSCO"])
        self.assertIn("outside this MCP showcase", payload["result_summary"]["message"])

    def test_prompt_and_run_declines_missing_inputs(self) -> None:
        """Decline supported language when the prompt omits explicit runnable paths."""
        prompt = "Experiment with Exonerate protein-to-genome alignment on this genome."

        payload = prompt_and_run(prompt)

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertEqual(payload["plan"]["matched_entry_name"], SUPPORTED_TASK_NAME)
        self.assertEqual(payload["plan"]["missing_required_inputs"], ["genome", "protein_chunk"])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertEqual(payload["result_summary"]["result_code"], "declined_missing_inputs")
        self.assertEqual(payload["result_summary"]["reason_code"], "missing_required_inputs")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_TASK_NAME)
        self.assertIn("prompt omitted explicit inputs", payload["result_summary"]["message"])

    def test_prompt_and_run_declines_unsupported_request_with_codes(self) -> None:
        """Return stable unsupported-request codes when the prompt does not map cleanly."""
        payload = prompt_and_run("Summarize the repository status for me.")

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertIsNone(payload["plan"]["matched_entry_name"])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertEqual(payload["result_summary"]["result_code"], "declined_unsupported_request")
        self.assertEqual(payload["result_summary"]["reason_code"], "unsupported_or_ambiguous_request")

    def test_prompt_and_run_summarizes_execution_failure(self) -> None:
        """Report a compact failure summary when the matched execution returns non-zero."""
        prompt = (
            "Annotate the genome sequence using BRAKER3 "
            "with genome data/genome.fa and protein evidence data/proteins.fa"
        )

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            self.assertEqual(workflow_name, SUPPORTED_WORKFLOW_NAME)
            self.assertEqual(
                inputs,
                {
                    "genome": "data/genome.fa",
                    "protein_fasta_path": "data/proteins.fa",
                },
            )
            return {
                "supported": True,
                "entry_name": workflow_name,
                "entry_category": "workflow",
                "execution_mode": "synthetic-test",
                "exit_status": 2,
                "stdout": "",
                "stderr": "BRAKER3 failed to start",
                "output_paths": [],
                "limitations": [
                    "Execution stays limited to the prebuilt BRAKER3 workflow and does not imply downstream annotation stages.",
                ],
            }

        payload = _prompt_and_run_impl(prompt, workflow_runner=fake_workflow_runner)

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertEqual(payload["result_summary"]["status"], "failed")
        self.assertEqual(payload["result_summary"]["result_code"], "failed_execution")
        self.assertEqual(payload["result_summary"]["reason_code"], "nonzero_exit_status")
        self.assertEqual(payload["result_summary"]["exit_status"], 2)
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {
                "genome": "data/genome.fa",
                "protein_fasta_path": "data/proteins.fa",
            },
        )
        self.assertIn("BRAKER3 failed to start", payload["result_summary"]["message"])

    def test_run_workflow_builds_expected_flyte_command(self) -> None:
        """Shell out through the compatibility entrypoint with explicit local inputs."""
        captured: dict[str, object] = {}

        def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured["args"] = args
            captured.update(kwargs)
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="workflow completed\n/tmp/flytetest/results/run_manifest.json\n",
                stderr="",
            )

        response = run_workflow(
            workflow_name=SUPPORTED_WORKFLOW_NAME,
            inputs={
                "genome": "data/genome.fa",
                "rnaseq_bam_path": "data/RNAseq.bam",
                "protein_fasta_path": "data/proteins.fa",
                "braker_species": "small_eukaryote",
            },
            runner=fake_run,
        )

        command = captured["args"]
        self.assertTrue(response["supported"])
        self.assertEqual(
            command[:5],
            [_resolve_flyte_cli(), "run", "--local", "flyte_rnaseq_workflow.py", SUPPORTED_WORKFLOW_NAME],
        )
        self.assertIn("--genome", command)
        self.assertIn("data/genome.fa", command)
        self.assertIn("--rnaseq_bam_path", command)
        self.assertIn("--protein_fasta_path", command)
        self.assertEqual(response["exit_status"], 0)

    def test_run_workflow_builds_expected_protein_evidence_command(self) -> None:
        """Shell out through the compatibility entrypoint for the protein-evidence workflow."""
        captured: dict[str, object] = {}

        def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured["args"] = args
            captured.update(kwargs)
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="workflow completed\n",
                stderr="",
            )

        response = run_workflow(
            workflow_name=SUPPORTED_PROTEIN_WORKFLOW_NAME,
            inputs={
                "genome": "data/genome.fa",
                "protein_fastas": ["data/proteins.fa", "data/proteins_extra.fa"],
                "proteins_per_chunk": 250,
            },
            runner=fake_run,
        )

        command = captured["args"]
        self.assertTrue(response["supported"])
        self.assertEqual(
            command[:5],
            [_resolve_flyte_cli(), "run", "--local", "flyte_rnaseq_workflow.py", SUPPORTED_PROTEIN_WORKFLOW_NAME],
        )
        self.assertEqual(command.count("--protein_fastas"), 2)
        self.assertIn("data/proteins.fa", command)
        self.assertIn("data/proteins_extra.fa", command)
        self.assertIn("--proteins_per_chunk", command)
        self.assertEqual(response["exit_status"], 0)

    def test_resolve_flyte_cli_prefers_repo_local_virtualenv_binary(self) -> None:
        """Use the repo-local `.venv` Flyte CLI when this checkout provides one."""
        self.assertEqual(
            _resolve_flyte_cli(),
            str((Path(__file__).resolve().parents[1] / ".venv" / "bin" / "flyte")),
        )
