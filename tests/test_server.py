"""Synthetic tests for the FLyteTest MCP recipe-backed server.

These checks keep the server transport MCP-shaped while preserving the explicit
recipe-backed execution target set.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest.mcp_contract import (
    DECLINE_CATEGORY_CODES,
    FETCH_JOB_LOG_TOOL_NAME,
    MCP_RESOURCE_URIS,
    MCP_TOOL_NAMES,
    PRIMARY_TOOL_NAME,
    PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
    RESULT_CODE_DEFINITIONS,
    RESULT_MANIFEST_RESOURCE_URI_PREFIX,
    RUN_RECIPE_RESOURCE_URI_PREFIX,
    SHOWCASE_SERVER_NAME,
    SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME,
    SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME,
    SUPPORTED_AGAT_WORKFLOW_NAME,
    SUPPORTED_BUSCO_FIXTURE_TASK_NAME,
    SUPPORTED_BUSCO_WORKFLOW_NAME,
    SUPPORTED_EGGNOG_WORKFLOW_NAME,
    SUPPORTED_PROTEIN_WORKFLOW_NAME,
    SUPPORTED_TARGET_NAMES,
    SUPPORTED_TASK_NAME,
    SUPPORTED_TASK_NAMES,
    SUPPORTED_WORKFLOW_NAME,
    TASK_EXAMPLE_PROMPT,
    WAIT_FOR_SLURM_JOB_TOOL_NAME,
    WORKFLOW_EXAMPLE_PROMPT,
    supported_runnable_targets_payload,
)
from flytetest.server import (
    SERVER_RESOURCE_URIS,
    MAX_MONITOR_TAIL_LINES,
    _fetch_job_log_impl,
    _get_run_summary_impl,
    _list_available_bindings_impl,
    _prepare_direct_workflow_inputs,
    _prompt_and_run_impl,
    _read_text_tail,
    _resolve_flyte_cli,
    _should_skip_stdio_line,
    _prepare_run_recipe_impl,
    _cancel_slurm_job_impl,
    _monitor_slurm_job_impl,
    _list_slurm_run_history_impl,
    _retry_slurm_job_impl,
    _run_local_recipe_impl,
    _run_slurm_recipe_impl,
    _wait_for_slurm_job_impl,
    create_mcp_server,
    fetch_job_log,
    get_run_summary,
    inspect_run_result,
    list_available_bindings,
    list_entries,
    plan_request,
    prompt_and_run,
    prepare_run_recipe,
    monitor_slurm_job,
    resource_example_prompts,
    resource_prompt_and_run_contract,
    resource_result_manifest,
    resource_run_recipe,
    resource_scope,
    resource_supported_targets,
    retry_slurm_job,
    cancel_slurm_job,
    run_local_recipe,
    run_slurm_recipe,
    run_task,
    run_workflow,
    wait_for_slurm_job,
)
from flytetest.spec_artifacts import load_workflow_spec_artifact
from flytetest.spec_executor import (
    DEFAULT_LOCAL_RUN_RECORD_FILENAME,
    DEFAULT_SLURM_RUN_RECORD_FILENAME,
    LOCAL_RUN_RECORD_SCHEMA_VERSION,
    SLURM_RUN_RECORD_SCHEMA_VERSION,
    LocalNodeExecutionResult,
    LocalRunRecord,
    SlurmRunRecord,
    load_slurm_run_record,
    save_local_run_record,
    save_slurm_run_record,
)

EXPECTED_TARGET_NAMES = list(SUPPORTED_TARGET_NAMES)
EXPECTED_RUNNABLE_TARGETS = supported_runnable_targets_payload()


def _repeat_filter_manifest_dir(tmp_path: Path) -> Path:
    """Create one synthetic repeat-filter result directory with a run manifest."""
    result_dir = tmp_path / "repeat_filter_results"
    result_dir.mkdir()
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_repeat_filtering",
                "assumptions": ["Repeat-filtered outputs are QC-ready."],
                "inputs": {"reference_genome": "data/braker3/reference/genome.fa"},
                "outputs": {
                    "all_repeats_removed_gff3": str(result_dir / "all_repeats_removed.gff3"),
                    "final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                },
            },
            indent=2,
        )
    )
    return result_dir


def _eggnog_manifest_dir(tmp_path: Path, name: str = "eggnog_results") -> Path:
    """Create one synthetic EggNOG result directory with a run manifest."""
    result_dir = tmp_path / name
    result_dir.mkdir()
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_functional_eggnog",
                "assumptions": ["EggNOG outputs are AGAT-ready."],
                "outputs": {
                    "eggnog_annotated_gff3": str(result_dir / "all_repeats_removed.eggnog.gff3"),
                    "repeat_filter_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                },
            },
            indent=2,
        )
    )
    return result_dir


def _agat_conversion_manifest_dir(tmp_path: Path) -> Path:
    """Create one synthetic AGAT conversion result directory with a run manifest."""
    result_dir = tmp_path / "agat_conversion_results"
    result_dir.mkdir()
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_postprocess_agat_conversion",
                "assumptions": ["AGAT conversion outputs are cleanup-ready."],
                "outputs": {
                    "agat_converted_gff3": str(result_dir / "all_repeats_removed.agat.gff3"),
                },
            },
            indent=2,
        )
    )
    return result_dir


class FakeFastMCP:
    """Small FastMCP stand-in used to capture tool registration."""

    def __init__(self, name: str) -> None:
        """Record the server name and fixture state."""
        self.name = name
        self.tools: dict[str, object] = {}
        self.resources: dict[str, object] = {}
        self.ran = False

    def tool(self):  # type: ignore[no-untyped-def]
        """Return a decorator that records the registered tool callable."""

        def decorator(fn):  # type: ignore[no-untyped-def]
            """Record the decorated tool callable and return it unchanged."""
            self.tools[fn.__name__] = fn
            return fn

        return decorator

    def resource(self, uri: str):  # type: ignore[no-untyped-def]
        """Return a decorator that records the registered resource callable."""

        def decorator(fn):  # type: ignore[no-untyped-def]
            """Record the decorated resource callable and return it unchanged."""
            self.resources[uri] = fn
            return fn

        return decorator

    def run(self) -> None:
        """Record that server execution was requested."""
        self.ran = True


class ServerTests(TestCase):
    """Coverage for the FastMCP surface and recipe-backed behavior.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_create_mcp_server_registers_only_the_required_tools(self) -> None:
        """Keep the MCP tool surface limited to list, plan, and prompt-and-run.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        server = create_mcp_server(fastmcp_cls=FakeFastMCP)

        self.assertEqual(server.name, SHOWCASE_SERVER_NAME)
        self.assertEqual(sorted(server.tools), sorted(MCP_TOOL_NAMES))

    def test_create_mcp_server_registers_the_read_only_resources(self) -> None:
        """Expose only the small static resource layer for MCP client discovery.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        server = create_mcp_server(fastmcp_cls=FakeFastMCP)

        self.assertEqual(tuple(SERVER_RESOURCE_URIS), MCP_RESOURCE_URIS)
        self.assertEqual(sorted(server.resources), sorted(MCP_RESOURCE_URIS))

    def test_blank_stdio_lines_are_ignored_before_json_parsing(self) -> None:
        """Ignore whitespace-only stdio lines so tolerant clients do not break the server.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        self.assertTrue(_should_skip_stdio_line("\n"))
        self.assertTrue(_should_skip_stdio_line("   \t  \n"))
        self.assertFalse(_should_skip_stdio_line('{"jsonrpc":"2.0"}\n'))

    def test_list_entries_exposes_only_the_supported_targets(self) -> None:
        """List only the explicitly runnable MCP recipe targets.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = list_entries()
        entries_by_name = {entry["name"]: entry for entry in payload["entries"]}

        self.assertEqual([entry["name"] for entry in payload["entries"]], EXPECTED_TARGET_NAMES)
        self.assertIn("slurm", entries_by_name[SUPPORTED_WORKFLOW_NAME]["supported_execution_profiles"])
        self.assertIn("slurm", entries_by_name[SUPPORTED_BUSCO_FIXTURE_TASK_NAME]["supported_execution_profiles"])
        self.assertEqual(entries_by_name[SUPPORTED_TASK_NAME]["supported_execution_profiles"], ["local"])
        self.assertEqual(entries_by_name[SUPPORTED_WORKFLOW_NAME]["default_execution_profile"], "local")
        self.assertEqual(payload["server_tools"], list(MCP_TOOL_NAMES))
        self.assertIn(f"`{SUPPORTED_WORKFLOW_NAME}`", payload["limitations"][0])
        self.assertIn(f"`{SUPPORTED_PROTEIN_WORKFLOW_NAME}`", payload["limitations"][0])
        self.assertIn(f"`{SUPPORTED_TASK_NAME}`", payload["limitations"][0])
        self.assertIn(f"`{SUPPORTED_BUSCO_FIXTURE_TASK_NAME}`", payload["limitations"][0])
        self.assertIn("annotation_qc_busco", payload["limitations"][0])
        self.assertIn("annotation_functional_eggnog", payload["limitations"][0])
        self.assertIn("annotation_postprocess_agat_cleanup", payload["limitations"][0])

    def test_scope_resource_describes_the_recipe_surface(self) -> None:
        """Describe the stdio recipe contract without implying broader support.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = resource_scope()

        self.assertEqual(payload["transport"], "stdio")
        self.assertEqual(payload["primary_tool"], PRIMARY_TOOL_NAME)
        self.assertEqual(payload["supported_runnable_targets"], EXPECTED_RUNNABLE_TARGETS)
        self.assertIn(".runtime/specs", payload["recipe_artifact_directory"])
        self.assertIn("manifest_sources", payload["recipe_input_context_fields"])
        self.assertTrue(any("busco_lineages_text" in rule for rule in payload["recipe_input_runtime_rules"]))
        self.assertTrue(any("eggnog_data_dir" in rule for rule in payload["recipe_input_runtime_rules"]))
        self.assertTrue(any("annotation_fasta_path" in rule for rule in payload["recipe_input_runtime_rules"]))

    def test_supported_targets_resource_matches_the_exact_showcase_entries(self) -> None:
        """Keep the resource target list aligned with the tool-facing entry list.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = resource_supported_targets()
        entries_by_name = {entry["name"]: entry for entry in payload["entries"]}

        self.assertEqual(payload["primary_tool"], PRIMARY_TOOL_NAME)
        self.assertEqual([entry["name"] for entry in payload["entries"]], EXPECTED_TARGET_NAMES)
        self.assertIn("slurm", entries_by_name[SUPPORTED_BUSCO_WORKFLOW_NAME]["supported_execution_profiles"])

    def test_example_prompts_resource_requires_explicit_local_paths(self) -> None:
        """Expose only small example prompts that match the narrow planner contract.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = resource_example_prompts()

        self.assertEqual(payload["primary_tool"], PRIMARY_TOOL_NAME)
        self.assertEqual(payload["workflow_prompt"], WORKFLOW_EXAMPLE_PROMPT)
        self.assertEqual(payload["protein_workflow_prompt"], PROTEIN_WORKFLOW_EXAMPLE_PROMPT)
        self.assertEqual(payload["task_prompt"], TASK_EXAMPLE_PROMPT)
        self.assertIn("explicit local file paths", payload["prompt_requirements"][0])

    def test_prompt_and_run_contract_resource_matches_enforced_summary_behavior(self) -> None:
        """Document the stable result-summary contract without widening showcase scope.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = resource_prompt_and_run_contract()

        self.assertEqual(payload["primary_tool"], PRIMARY_TOOL_NAME)
        self.assertEqual(payload["supported_tools"], list(MCP_TOOL_NAMES))
        self.assertEqual(payload["supported_runnable_targets"], EXPECTED_RUNNABLE_TARGETS)
        self.assertIn("manifest_sources", payload["recipe_input_context_fields"])
        self.assertTrue(any("QualityAssessmentTarget" in rule for rule in payload["recipe_input_binding_rules"]))
        self.assertIn("result_code", payload["result_summary_fields"])
        self.assertIn("reason_code", payload["result_summary_fields"])
        self.assertEqual(
            payload["result_codes"]["failed_execution"]["reason_codes"],
            RESULT_CODE_DEFINITIONS["failed_execution"]["reason_codes"],
        )
        self.assertEqual(payload["decline_categories"], DECLINE_CATEGORY_CODES)
        self.assertIn(".runtime/specs", payload["recipe_artifact_directory"])
        self.assertIn("explicit local file paths", payload["prompt_requirements"][0])
        self.assertIn("typed_planning_available", payload["result_summary_fields"])
        self.assertIn("artifact_path", payload["result_summary_fields"])
        self.assertIn("workflow_spec", payload["typed_planning_fields"])

    def test_plan_request_builds_workflow_recipe_plan_from_prompt_paths(self) -> None:
        """Classify the BRAKER3 prompt and freeze explicit local paths.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = (
            "Annotate the genome sequence of a small eukaryote using BRAKER3 "
            "with genome data/braker3/reference/genome.fa, RNA-seq evidence data/braker3/rnaseq/RNAseq.bam, "
            "and protein evidence data/braker3/protein_data/fastas/proteins.fa"
        )

        payload = plan_request(prompt)

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_names"], [SUPPORTED_WORKFLOW_NAME])
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "rnaseq_bam_path": "data/braker3/rnaseq/RNAseq.bam",
                "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
            },
        )

    def test_plan_request_still_reports_broader_typed_specs(self) -> None:
        """Expose broader typed planning data without executing it.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = plan_request("Create a generated WorkflowSpec for repeat filtering and BUSCO QC.")

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["candidate_outcome"], "generated_workflow_spec")
        self.assertEqual(payload["biological_goal"], "repeat_filter_then_busco_qc")
        self.assertIsNotNone(payload["workflow_spec"])

    def test_plan_request_builds_protein_workflow_recipe_plan(self) -> None:
        """Classify the protein-evidence prompt and preserve protein FASTA order.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = (
            "Run protein evidence alignment with genome data/braker3/reference/genome.fa, "
            "protein evidence data/braker3/protein_data/fastas/proteins.fa, and protein evidence data/braker3/protein_data/fastas/proteins_extra.fa"
        )

        payload = plan_request(prompt)

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_names"], [SUPPORTED_PROTEIN_WORKFLOW_NAME])
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "protein_fastas": [
                    "data/braker3/protein_data/fastas/proteins.fa",
                    "data/braker3/protein_data/fastas/proteins_extra.fa",
                ],
            },
        )

    def test_prepare_and_run_local_recipe_round_trips_saved_artifact(self) -> None:
        """Prepare a frozen recipe and execute it through explicit local handlers.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = (
            "Run protein evidence alignment with genome data/braker3/reference/genome.fa and "
            "protein evidence data/braker3/protein_data/fastas/proteins.fa"
        )
        calls: list[dict[str, object]] = []

        def handler(request):  # type: ignore[no-untyped-def]
            """Capture the forwarded workflow inputs and return a stub result path."""
            calls.append(dict(request.inputs))
            return {"results_dir": "/tmp/protein_evidence_results"}

        with tempfile.TemporaryDirectory() as tmp:
            prepared = _prepare_run_recipe_impl(prompt, recipe_dir=Path(tmp))
            self.assertTrue(prepared["supported"])
            self.assertTrue(Path(str(prepared["artifact_path"])).exists())

            executed = _run_local_recipe_impl(
                str(prepared["artifact_path"]),
                handlers={SUPPORTED_PROTEIN_WORKFLOW_NAME: handler},
            )

        self.assertTrue(executed["supported"])
        self.assertEqual(calls[0], {"genome": "data/braker3/reference/genome.fa", "protein_fastas": ["data/braker3/protein_data/fastas/proteins.fa"]})
        self.assertEqual(executed["execution_result"]["output_paths"], ["/tmp/protein_evidence_results"])

    def test_run_local_recipe_impl_can_resume_from_prior_local_record(self) -> None:
        """Run-local execution should forward a prior local run record into the executor."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                recipe_dir=tmp_path,
            )
            artifact_path = Path(str(prepared["artifact_path"]))
            artifact = load_workflow_spec_artifact(artifact_path)
            node = artifact.workflow_spec.nodes[0]

            prior_run_dir = tmp_path / "prior_local_run"
            prior_run_dir.mkdir()
            prior_results_dir = tmp_path / "prior_busco_results"
            prior_results_dir.mkdir()
            (prior_results_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow": "annotation_qc_busco",
                        "outputs": {
                            "results_dir": str(prior_results_dir),
                        },
                    },
                    indent=2,
                )
            )
            prior_record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="prior-local-run-001",
                workflow_name=artifact.workflow_spec.name,
                run_record_path=prior_run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-04-13T12:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target=artifact.binding_plan.target_name,
                node_completion_state={node.name: True},
                node_results=(
                    LocalNodeExecutionResult(
                        node_name=node.name,
                        reference_name=node.reference_name,
                        outputs={node.output_names[0]: str(prior_results_dir)},
                    ),
                ),
                artifact_path=artifact_path,
                final_outputs={binding.output_name: str(prior_results_dir) for binding in artifact.workflow_spec.final_output_bindings},
                completed_at="2026-04-13T12:00:01Z",
            )
            save_local_run_record(prior_record)

            handler_called = False

            def handler(request):  # type: ignore[no-untyped-def]
                """Fail if the resumed node is executed again."""
                nonlocal handler_called
                handler_called = True
                return {"results_dir": "/tmp/unexpected"}

            executed = _run_local_recipe_impl(
                str(artifact_path),
                handlers={SUPPORTED_BUSCO_WORKFLOW_NAME: handler},
                resume_from_local_record=prior_run_dir,
            )

        self.assertTrue(executed["supported"])
        self.assertFalse(handler_called)
        self.assertEqual(executed["execution_result"]["final_outputs"]["results_dir"], str(prior_results_dir))

    def test_run_slurm_recipe_submits_saved_slurm_artifact(self) -> None:
        """Submit a frozen Slurm-profile recipe and persist a run record.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={"cpu": 12, "memory": "48Gi", "queue": "batch", "walltime": "02:00:00"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            captured: dict[str, object] = {}

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                captured["args"] = args
                captured.update(kwargs)
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 24680\n", stderr="")

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            run_record_exists = Path(str(submitted["run_record_path"])).exists()

        self.assertTrue(prepared["supported"])
        self.assertTrue(submitted["supported"])
        self.assertEqual(submitted["job_id"], "24680")
        self.assertTrue(run_record_exists)
        self.assertEqual(captured["args"][0], "sbatch")
        self.assertEqual(submitted["execution_result"]["execution_mode"], "slurm-workflow-spec-executor")
        self.assertEqual(submitted["execution_result"]["run_record"]["resource_spec"]["queue"], "batch")
        self.assertEqual(submitted["execution_result"]["run_record"]["resource_spec"]["account"], "rcc-staff")

    def test_run_slurm_recipe_updates_generic_latest_pointer_on_back_to_back_submissions(self) -> None:
        """Direct MCP Slurm submissions should refresh the shared latest-run pointer."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            job_ids = iter(("24680", "24681"))

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Return distinct job IDs for consecutive submissions."""
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=f"Submitted batch job {next(job_ids)}\n",
                    stderr="",
                )

            first = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            second = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )

            latest_run_pointer = tmp_path / "runs" / "latest_slurm_run_record.txt"
            latest_artifact_pointer = tmp_path / "runs" / "latest_slurm_artifact.txt"
            latest_run_pointer_value = latest_run_pointer.read_text().strip()
            latest_artifact_pointer_value = latest_artifact_pointer.read_text().strip()

        self.assertTrue(first["supported"])
        self.assertTrue(second["supported"])
        self.assertNotEqual(first["run_record_path"], second["run_record_path"])
        self.assertEqual(latest_run_pointer_value, str(second["run_record_path"]))
        self.assertEqual(latest_artifact_pointer_value, str(prepared["artifact_path"]))

    def test_run_slurm_recipe_rejects_local_profile_artifact(self) -> None:
        """Require Slurm recipes to be explicitly frozen with the Slurm profile.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            prepared = _prepare_run_recipe_impl(
                "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa",
                recipe_dir=Path(tmp),
            )
            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=Path(tmp) / "runs",
                sbatch_runner=lambda *args, **kwargs: subprocess.CompletedProcess(args=args, returncode=0),
                command_available=lambda command: True,
            )

        self.assertFalse(submitted["supported"])
        self.assertIn("execution_profile `slurm`", submitted["limitations"][0])

    def test_list_slurm_run_history_returns_recent_records_and_latest_pointer(self) -> None:
        """Filesystem history should list durable Slurm runs newest first."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            job_ids = iter(("60101", "60102"))

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Return distinct Slurm job IDs for consecutive submissions."""
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=f"Submitted batch job {next(job_ids)}\n",
                    stderr="",
                )

            first = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            second = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )

            save_slurm_run_record(
                replace(
                    load_slurm_run_record(Path(str(first["run_record_path"]))),
                    submitted_at="2026-04-13T12:00:00Z",
                )
            )
            save_slurm_run_record(
                replace(
                    load_slurm_run_record(Path(str(second["run_record_path"]))),
                    submitted_at="2026-04-13T12:00:01Z",
                )
            )
            history = _list_slurm_run_history_impl(run_dir=tmp_path / "runs", limit=5)

        self.assertTrue(history["supported"])
        self.assertEqual(history["filters"], {
            "workflow_name": None,
            "active_only": False,
            "terminal_only": False,
            "limit": 5,
        })
        self.assertEqual(history["returned_count"], 2)
        self.assertEqual(history["matched_count"], 2)
        self.assertEqual(history["total_count"], 2)
        self.assertEqual(history["latest_run_record_path"], str(second["run_record_path"]))
        self.assertEqual(history["entries"][0]["run_record_path"], str(second["run_record_path"]))
        self.assertEqual(history["entries"][0]["job_id"], "60102")
        self.assertEqual(history["entries"][1]["job_id"], "60101")

    def test_list_slurm_run_history_returns_empty_payload_when_no_runs_exist(self) -> None:
        """Missing run roots should return an empty, supported history payload."""
        with tempfile.TemporaryDirectory() as tmp:
            history = _list_slurm_run_history_impl(run_dir=Path(tmp) / "missing", limit=5)

        self.assertTrue(history["supported"])
        self.assertEqual(history["entries"], [])
        self.assertEqual(history["returned_count"], 0)
        self.assertEqual(history["matched_count"], 0)
        self.assertEqual(history["total_count"], 0)
        self.assertIsNone(history["latest_run_record_path"])

    def test_list_slurm_run_history_filters_by_workflow_and_terminal_state(self) -> None:
        """History filters should support workflow selection and active or terminal views."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            busco_result_dir = _repeat_filter_manifest_dir(tmp_path)
            busco_recipe = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(busco_result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            protein_recipe = _prepare_run_recipe_impl(
                "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa using execution profile slurm.",
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            job_ids = iter(("60201", "60202"))

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Return distinct Slurm job IDs for the BUSCO and protein recipes."""
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=f"Submitted batch job {next(job_ids)}\n",
                    stderr="",
                )

            busco_run = _run_slurm_recipe_impl(
                str(busco_recipe["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            protein_run = _run_slurm_recipe_impl(
                str(protein_recipe["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )

            save_slurm_run_record(
                replace(
                    load_slurm_run_record(Path(str(busco_run["run_record_path"]))),
                    submitted_at="2026-04-13T12:00:00Z",
                    scheduler_state="RUNNING",
                    final_scheduler_state=None,
                )
            )
            save_slurm_run_record(
                replace(
                    load_slurm_run_record(Path(str(protein_run["run_record_path"]))),
                    submitted_at="2026-04-13T12:00:01Z",
                    scheduler_state="COMPLETED",
                    final_scheduler_state="COMPLETED",
                    scheduler_exit_code="0:0",
                )
            )
            protein_workflow_name = load_slurm_run_record(
                Path(str(protein_run["run_record_path"]))
            ).workflow_name

            workflow_filtered = _list_slurm_run_history_impl(
                run_dir=tmp_path / "runs",
                limit=5,
                workflow_name=protein_workflow_name,
            )
            active_only = _list_slurm_run_history_impl(
                run_dir=tmp_path / "runs",
                limit=5,
                active_only=True,
            )
            terminal_only = _list_slurm_run_history_impl(
                run_dir=tmp_path / "runs",
                limit=5,
                terminal_only=True,
            )

        self.assertTrue(workflow_filtered["supported"])
        self.assertEqual(workflow_filtered["matched_count"], 1)
        self.assertEqual(workflow_filtered["entries"][0]["workflow_name"], protein_workflow_name)
        self.assertTrue(active_only["supported"])
        self.assertEqual(active_only["matched_count"], 1)
        self.assertEqual(active_only["entries"][0]["job_id"], "60201")
        self.assertFalse(active_only["entries"][0]["is_terminal"])
        self.assertTrue(terminal_only["supported"])
        self.assertEqual(terminal_only["matched_count"], 1)
        self.assertEqual(terminal_only["entries"][0]["job_id"], "60202")
        self.assertTrue(terminal_only["entries"][0]["is_terminal"])

    def test_list_slurm_run_history_rejects_conflicting_state_filters(self) -> None:
        """Active-only and terminal-only are mutually exclusive history views."""
        with tempfile.TemporaryDirectory() as tmp:
            history = _list_slurm_run_history_impl(
                run_dir=Path(tmp),
                limit=5,
                active_only=True,
                terminal_only=True,
            )

        self.assertFalse(history["supported"])
        self.assertIn("active_only and terminal_only cannot both be true", history["limitations"][0])

    def test_monitor_slurm_job_reconciles_saved_record(self) -> None:
        """Expose Slurm status reconciliation through the server helper.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={"cpu": 12, "memory": "48Gi", "queue": "batch"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 44444\n", stderr="")

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate scheduler inspection commands with a canned state snapshot."""
                if args[0] == "squeue":
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="PENDING\n", stderr="")
                if args[0] == "scontrol":
                    return subprocess.CompletedProcess(
                        args=args,
                        returncode=0,
                        stdout=f"JobId=44444 JobState=PENDING ExitCode=0:0 StdOut={tmp_path / 'job.out'} StdErr={tmp_path / 'job.err'} Reason=Resources\n",
                        stderr="",
                    )
                if args[0] == "sacct":
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
                raise AssertionError(args)

            status = _monitor_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=fake_scheduler,
                command_available=lambda command: True,
            )

        self.assertTrue(status["supported"])
        self.assertEqual(status["lifecycle_result"]["scheduler_state"], "PENDING")
        self.assertEqual(status["lifecycle_result"]["job_id"], "44444")
        self.assertEqual(status["lifecycle_result"]["scheduler_snapshot"]["source"], "squeue")

    def test_cancel_slurm_job_records_cancellation_request(self) -> None:
        """Expose Slurm cancellation through the server helper.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 55555\n", stderr="")

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            calls: list[list[str]] = []

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate scheduler inspection commands with a canned state snapshot."""
                calls.append(args)
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

            cancelled = _cancel_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=fake_scheduler,
                command_available=lambda command: True,
            )

        self.assertTrue(cancelled["supported"])
        self.assertEqual(calls, [["scancel", "55555"]])
        self.assertEqual(cancelled["lifecycle_result"]["scheduler_state"], "cancellation_requested")

    def test_retry_slurm_job_resubmits_retryable_failure(self) -> None:
        """Expose explicit Slurm retry through the server helper.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            job_ids = iter(("55601", "55602"))

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=f"Submitted batch job {next(job_ids)}\n",
                    stderr="",
                )

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            failed_record = load_slurm_run_record(Path(str(submitted["run_record_path"])))
            failed_record = failed_record.__class__.from_dict(
                {
                    **failed_record.to_dict(),
                    "scheduler_state": "NODE_FAIL",
                    "scheduler_exit_code": "0:0",
                    "scheduler_reason": "Node failure detected by scheduler.",
                    "final_scheduler_state": "NODE_FAIL",
                    "failure_classification": None,
                }
            )
            save_slurm_run_record(failed_record)

            retried = _retry_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )

        self.assertTrue(retried["supported"])
        self.assertEqual(retried["job_id"], "55602")
        self.assertEqual(retried["retry_result"]["execution_mode"], "slurm-retry")
        self.assertEqual(retried["retry_result"]["failure_classification"]["status"], "retryable_failure")
        self.assertEqual(retried["retry_result"]["retry_execution"]["execution_mode"], "slurm-workflow-spec-executor")

    def test_retry_slurm_job_declines_nonretryable_failure(self) -> None:
        """Report terminal resource failures without resubmitting them.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 55701\n", stderr="")

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            failed_record = load_slurm_run_record(Path(str(submitted["run_record_path"])))
            failed_record = failed_record.__class__.from_dict(
                {
                    **failed_record.to_dict(),
                    "scheduler_state": "OUT_OF_MEMORY",
                    "scheduler_exit_code": "1:0",
                    "scheduler_reason": "Out Of Memory",
                    "final_scheduler_state": "OUT_OF_MEMORY",
                    "failure_classification": None,
                }
            )
            save_slurm_run_record(failed_record)

            retried = _retry_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )

        self.assertFalse(retried["supported"])
        self.assertEqual(retried["retry_result"]["failure_classification"]["failure_class"], "resource_exhaustion")
        self.assertIn("not retryable", retried["limitations"][0])

    def test_monitor_slurm_job_reports_missing_record(self) -> None:
        """Report missing run records instead of inventing state.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            status = _monitor_slurm_job_impl(Path(tmp) / "missing")

        self.assertFalse(status["supported"])
        self.assertIn("No such file", status["limitations"][0])

    def test_run_slurm_recipe_reports_missing_sbatch_as_unsupported_environment(self) -> None:
        """Expose an authenticated-environment diagnostic when `sbatch` is unavailable.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                command_available=lambda command: False,
            )

        self.assertFalse(submitted["supported"])
        self.assertIn("already-authenticated scheduler environment", submitted["limitations"][0])

    def test_monitor_slurm_job_reports_missing_scheduler_commands_as_unsupported_environment(self) -> None:
        """Expose an authenticated-environment diagnostic when monitoring commands are unavailable.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )

            def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                """Simulate sbatch submission with a canned batch-job response."""
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 88888\n", stderr="")

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: command == "sbatch",
            )
            status = _monitor_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("scheduler runner should not be called")),
                command_available=lambda command: False,
            )

        self.assertFalse(status["supported"])
        self.assertIn("already-authenticated scheduler environment", status["limitations"][0])

    def test_prepare_run_recipe_accepts_busco_manifest_sources_and_runtime_bindings(self) -> None:
        """Freeze BUSCO recipe bindings from an explicit repeat-filter manifest source.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={
                    "busco_lineages_text": "embryophyta_odb10",
                    "busco_sif": "busco.sif",
                    "busco_cpu": 12,
                },
                resource_request={"cpu": 12, "memory": "48Gi", "queue": "short"},
                execution_profile="local",
                runtime_image={"apptainer_image": "busco.sif"},
                recipe_dir=tmp_path,
            )
            artifact = load_workflow_spec_artifact(Path(str(prepared["artifact_path"])))

        self.assertTrue(prepared["supported"])
        self.assertEqual(prepared["recipe_input_context"]["manifest_sources"], [str(result_dir)])
        self.assertEqual(
            prepared["recipe_input_context"]["resource_request"],
            {"cpu": 12, "memory": "48Gi", "queue": "short"},
        )
        self.assertEqual(
            prepared["typed_plan"]["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(result_dir),
        )
        self.assertEqual(prepared["typed_plan"]["execution_profile"], "local")
        self.assertEqual(prepared["typed_plan"]["resource_spec"]["cpu"], "12")
        self.assertEqual(prepared["typed_plan"]["resource_spec"]["memory"], "48Gi")
        self.assertEqual(prepared["typed_plan"]["runtime_image"]["apptainer_image"], "busco.sif")
        self.assertEqual(
            prepared["typed_plan"]["binding_plan"]["runtime_bindings"],
            {
                "busco_lineages_text": "embryophyta_odb10",
                "busco_sif": "busco.sif",
                "busco_cpu": 12,
            },
        )
        self.assertEqual(artifact.binding_plan.resource_spec.memory, "48Gi")
        self.assertEqual(artifact.binding_plan.runtime_image.apptainer_image, "busco.sif")

    def test_prepare_run_recipe_preserves_explicit_slurm_profile(self) -> None:
        """Freeze an explicitly requested Slurm profile into the saved recipe artifact.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prepared = _prepare_run_recipe_impl(
                "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa",
                runtime_bindings={"exonerate_sif": "data/images/exonerate_2.2.0--1.sif"},
                resource_request={
                    "account": "rcc-staff",
                    "queue": "caslake",
                    "cpu": 8,
                    "memory": "32Gi",
                    "walltime": "02:00:00",
                },
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            artifact = load_workflow_spec_artifact(Path(str(prepared["artifact_path"])))

        self.assertTrue(prepared["supported"])
        self.assertEqual(prepared["recipe_input_context"]["execution_profile"], "slurm")
        self.assertEqual(prepared["typed_plan"]["execution_profile"], "slurm")
        self.assertEqual(prepared["typed_plan"]["binding_plan"]["execution_profile"], "slurm")
        self.assertEqual(artifact.binding_plan.execution_profile, "slurm")

    def test_prepare_run_recipe_persists_module_loads_in_frozen_artifact(self) -> None:
        """module_loads passed via resource_request flows through to the frozen artifact.

        This covers the full MCP surface path: resource_request dict with a module_loads
        list → _coerce_resource_spec → _merge_resource_specs → artifact binding_plan.
        The executor and rendering tests (test_spec_executor.py) only verify the render
        layer; this test verifies the planning-layer wiring.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prepared = _prepare_run_recipe_impl(
                "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa",
                runtime_bindings={"exonerate_sif": "data/images/exonerate_2.2.0--1.sif"},
                resource_request={
                    "account": "rcc-staff",
                    "queue": "caslake",
                    "cpu": 8,
                    "memory": "32Gi",
                    "walltime": "02:00:00",
                    "module_loads": ["cuda/12.0", "python/3.12"],
                },
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            artifact = load_workflow_spec_artifact(Path(str(prepared["artifact_path"])))

        self.assertTrue(prepared["supported"])
        self.assertEqual(artifact.binding_plan.resource_spec.module_loads, ("cuda/12.0", "python/3.12"))

    def test_prepare_run_recipe_accepts_m18_busco_fixture_prompt(self) -> None:
        """Freeze the M18 BUSCO fixture task through the MCP recipe path."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prepared = _prepare_run_recipe_impl(
                (
                    "Run the Milestone 18 BUSCO eukaryota fixture using execution profile slurm "
                    "with BUSCO_SIF data/images/busco_v6.0.0_cv1.sif, busco_cpu 2, "
                    "2 CPUs, memory 8Gi, queue caslake, account rcc-staff, walltime 00:10:00."
                ),
                recipe_dir=tmp_path,
            )
            artifact = load_workflow_spec_artifact(Path(str(prepared["artifact_path"])))

        self.assertTrue(prepared["supported"])
        self.assertEqual(prepared["typed_plan"]["biological_goal"], "busco_assess_proteins")
        self.assertEqual(prepared["typed_plan"]["candidate_outcome"], "registered_task")
        self.assertEqual(prepared["typed_plan"]["execution_profile"], "slurm")
        self.assertEqual(artifact.binding_plan.target_name, "busco_assess_proteins")
        self.assertEqual(artifact.binding_plan.target_kind, "task")
        self.assertEqual(artifact.binding_plan.runtime_bindings["proteins_fasta"], "data/busco/test_data/eukaryota/genome.fna")
        self.assertEqual(artifact.binding_plan.runtime_bindings["lineage_dataset"], "auto-lineage")
        self.assertEqual(artifact.binding_plan.runtime_bindings["busco_mode"], "geno")
        self.assertEqual(artifact.binding_plan.runtime_bindings["busco_cpu"], 2)
        self.assertEqual(artifact.binding_plan.runtime_bindings["busco_sif"], "data/images/busco_v6.0.0_cv1.sif")
        self.assertEqual(artifact.binding_plan.resource_spec.cpu, "2")
        self.assertEqual(artifact.binding_plan.resource_spec.memory, "8Gi")

    def test_prepare_run_recipe_rejects_missing_manifest_sources(self) -> None:
        """Return a structured decline when a manifest source cannot be validated.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(tmp_path / "missing",),
                recipe_dir=tmp_path,
            )

        self.assertFalse(prepared["supported"])
        self.assertIsNone(prepared["artifact_path"])
        self.assertIn("does not exist", prepared["limitations"][0])
        self.assertEqual(prepared["recipe_input_context"]["manifest_sources"], [str(tmp_path / "missing")])

    def test_prompt_and_run_accepts_busco_recipe_context(self) -> None:
        """Allow the compatibility alias to execute BUSCO from explicit recipe inputs.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = "Run BUSCO quality assessment on the annotation."
        captured: dict[str, object] = {}

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture workflow invocations from the compatibility path."""
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
                "output_paths": ["/tmp/busco_results"],
                "limitations": [],
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            payload = _prompt_and_run_impl(
                prompt,
                workflow_runner=fake_workflow_runner,
                manifest_sources=(result_dir,),
                runtime_bindings={
                    "busco_lineages_text": "embryophyta_odb10",
                    "busco_sif": "busco.sif",
                    "busco_cpu": 12,
                },
                resource_request={"cpu": 12, "memory": "48Gi"},
                recipe_dir=tmp_path,
            )
            artifact_exists = Path(str(payload["artifact_path"])).exists()

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertTrue(artifact_exists)
        self.assertEqual(captured["workflow_name"], SUPPORTED_BUSCO_WORKFLOW_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "repeat_filter_results": result_dir,
                "busco_lineages_text": "embryophyta_odb10",
                "busco_sif": "busco.sif",
                "busco_cpu": 12,
            },
        )
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {
                "repeat_filter_results": str(result_dir),
                "busco_lineages_text": "embryophyta_odb10",
                "busco_sif": "busco.sif",
                "busco_cpu": 12,
            },
        )
        self.assertEqual(
            payload["execution_result"]["resolved_planner_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(result_dir),
        )
        self.assertEqual(payload["execution_result"]["execution_profile"], "local")
        self.assertEqual(payload["execution_result"]["resource_spec"]["cpu"], "12")
        self.assertEqual(payload["execution_result"]["resource_spec"]["memory"], "48Gi")
        self.assertEqual(payload["result_summary"]["execution_profile"], "local")
        self.assertEqual(payload["result_summary"]["resource_spec"]["memory"], "48Gi")

    def test_prepare_run_recipe_accepts_eggnog_manifest_sources_and_runtime_bindings(self) -> None:
        """Freeze EggNOG recipe bindings from a repeat-filter manifest source.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run EggNOG functional annotation on the repeat-filtered proteins.",
                manifest_sources=(result_dir,),
                runtime_bindings={
                    "eggnog_data_dir": "/db/eggnog",
                    "eggnog_sif": "eggnog.sif",
                    "eggnog_cpu": 16,
                    "eggnog_database": "Diptera",
                },
                recipe_dir=tmp_path,
            )
            artifact = load_workflow_spec_artifact(Path(str(prepared["artifact_path"])))

        self.assertTrue(prepared["supported"])
        self.assertEqual(prepared["typed_plan"]["matched_entry_names"], [SUPPORTED_EGGNOG_WORKFLOW_NAME])
        self.assertEqual(
            artifact.binding_plan.runtime_bindings,
            {
                "eggnog_data_dir": "/db/eggnog",
                "eggnog_sif": "eggnog.sif",
                "eggnog_cpu": 16,
                "eggnog_database": "Diptera",
            },
        )
        self.assertEqual(
            artifact.binding_plan.manifest_derived_paths["QualityAssessmentTarget"]["label"],
            str(result_dir / "run_manifest.json"),
        )

    def test_prepare_run_recipe_accepts_agat_manifest_sources(self) -> None:
        """Freeze AGAT recipes from explicit EggNOG and AGAT conversion manifests.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eggnog_dir = _eggnog_manifest_dir(tmp_path)
            conversion_dir = _agat_conversion_manifest_dir(tmp_path)
            stats = _prepare_run_recipe_impl(
                "Run AGAT statistics on the EggNOG-annotated GFF3.",
                manifest_sources=(eggnog_dir,),
                runtime_bindings={"annotation_fasta_path": "data/braker3/reference/genome.fa", "agat_sif": "agat.sif"},
                recipe_dir=tmp_path,
            )
            conversion = _prepare_run_recipe_impl(
                "Run AGAT conversion on the EggNOG-annotated GFF3.",
                manifest_sources=(eggnog_dir,),
                runtime_bindings={"agat_sif": "agat.sif"},
                recipe_dir=tmp_path,
            )
            cleanup = _prepare_run_recipe_impl(
                "Run AGAT cleanup on the converted GFF3.",
                manifest_sources=(conversion_dir,),
                recipe_dir=tmp_path,
            )

        self.assertTrue(stats["supported"])
        self.assertTrue(conversion["supported"])
        self.assertTrue(cleanup["supported"])
        self.assertEqual(stats["typed_plan"]["matched_entry_names"], [SUPPORTED_AGAT_WORKFLOW_NAME])
        self.assertEqual(conversion["typed_plan"]["matched_entry_names"], [SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME])
        self.assertEqual(cleanup["typed_plan"]["matched_entry_names"], [SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME])
        self.assertEqual(
            stats["typed_plan"]["binding_plan"]["runtime_bindings"],
            {"annotation_fasta_path": "data/braker3/reference/genome.fa", "agat_sif": "agat.sif"},
        )
        self.assertEqual(conversion["typed_plan"]["binding_plan"]["runtime_bindings"], {"agat_sif": "agat.sif"})
        self.assertEqual(
            cleanup["typed_plan"]["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(conversion_dir),
        )

    def test_prepare_run_recipe_declines_ambiguous_eggnog_manifest_sources(self) -> None:
        """Refuse to choose among multiple compatible EggNOG input manifests.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first = _eggnog_manifest_dir(tmp_path, "eggnog_results_a")
            second = _eggnog_manifest_dir(tmp_path, "eggnog_results_b")
            prepared = _prepare_run_recipe_impl(
                "Run AGAT conversion on the EggNOG-annotated GFF3.",
                manifest_sources=(first, second),
                runtime_bindings={"agat_sif": "agat.sif"},
                recipe_dir=tmp_path,
            )

        self.assertFalse(prepared["supported"])
        self.assertIsNone(prepared["artifact_path"])
        self.assertIn("choose one explicitly", prepared["limitations"][0])

    def test_prompt_and_run_accepts_eggnog_recipe_context(self) -> None:
        """Execute EggNOG through the recipe context and local workflow handler.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        captured: dict[str, object] = {}

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture workflow invocations from the compatibility path."""
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
                "output_paths": ["/tmp/eggnog_results"],
                "limitations": [],
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            payload = _prompt_and_run_impl(
                "Run EggNOG functional annotation on the repeat-filtered proteins.",
                workflow_runner=fake_workflow_runner,
                manifest_sources=(result_dir,),
                runtime_bindings={
                    "eggnog_data_dir": "/db/eggnog",
                    "eggnog_sif": "eggnog.sif",
                    "eggnog_cpu": 16,
                    "eggnog_database": "Diptera",
                },
                recipe_dir=tmp_path,
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(captured["workflow_name"], SUPPORTED_EGGNOG_WORKFLOW_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "repeat_filter_results": result_dir,
                "eggnog_data_dir": "/db/eggnog",
                "eggnog_sif": "eggnog.sif",
                "eggnog_cpu": 16,
                "eggnog_database": "Diptera",
            },
        )
        self.assertEqual(payload["result_summary"]["used_inputs"]["repeat_filter_results"], str(result_dir))
        self.assertEqual(payload["result_summary"]["used_inputs"]["eggnog_data_dir"], "/db/eggnog")

    def test_prompt_and_run_accepts_agat_cleanup_recipe_context(self) -> None:
        """Execute AGAT cleanup from an explicit AGAT conversion manifest source.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        captured: dict[str, object] = {}

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture workflow invocations from the compatibility path."""
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
                "output_paths": ["/tmp/agat_cleanup_results"],
                "limitations": [],
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            conversion_dir = _agat_conversion_manifest_dir(tmp_path)
            payload = _prompt_and_run_impl(
                "Run AGAT cleanup on the converted GFF3.",
                workflow_runner=fake_workflow_runner,
                manifest_sources=(conversion_dir,),
                recipe_dir=tmp_path,
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(captured["workflow_name"], SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME)
        self.assertEqual(captured["inputs"], {"agat_conversion_results": conversion_dir})
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {"agat_conversion_results": str(conversion_dir)},
        )

    def test_prompt_and_run_workflow_prompt_uses_extracted_inputs(self) -> None:
        """Plan and dispatch the BRAKER3 example prompt through the workflow runner.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = (
            "Annotate the genome sequence of a small eukaryote using BRAKER3 "
            "with genome data/braker3/reference/genome.fa, RNA-seq evidence data/braker3/rnaseq/RNAseq.bam, "
            "and protein evidence data/braker3/protein_data/fastas/proteins.fa"
        )
        captured: dict[str, object] = {}

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture workflow invocations from the compatibility path."""
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

        with tempfile.TemporaryDirectory() as tmp:
            payload = _prompt_and_run_impl(
                prompt,
                workflow_runner=fake_workflow_runner,
                recipe_dir=Path(tmp),
            )
            artifact_exists = Path(str(payload["artifact_path"])).exists()

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertTrue(artifact_exists)
        self.assertEqual(captured["workflow_name"], SUPPORTED_WORKFLOW_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "rnaseq_bam_path": "data/braker3/rnaseq/RNAseq.bam",
                "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
            },
        )
        self.assertEqual(payload["execution_result"]["exit_status"], 0)
        self.assertEqual(payload["result_summary"]["status"], "succeeded")
        self.assertEqual(payload["result_summary"]["result_code"], "succeeded")
        self.assertEqual(payload["result_summary"]["reason_code"], "completed")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_WORKFLOW_NAME)
        self.assertEqual(payload["execution_result"]["execution_mode"], "local-workflow-spec-executor")
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "rnaseq_bam_path": "data/braker3/rnaseq/RNAseq.bam",
                "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
            },
        )
        self.assertEqual(payload["result_summary"]["output_paths"], ["/tmp/braker3_results"])
        self.assertTrue(payload["result_summary"]["typed_planning_available"])
        self.assertEqual(payload["result_summary"]["artifact_path"], payload["artifact_path"])
        self.assertIn("execution succeeded", payload["result_summary"]["message"])

    def test_prompt_and_run_reports_typed_preview_without_executing_broader_request(self) -> None:
        """Layer broader typed planning into prompt-and-run without changing runnable targets.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = prompt_and_run("Create a generated WorkflowSpec for repeat filtering and BUSCO QC.")

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertTrue(payload["result_summary"]["typed_planning_available"])
        self.assertEqual(payload["typed_planning"]["candidate_outcome"], "generated_workflow_spec")
        self.assertIsNotNone(payload["typed_planning"]["workflow_spec"])

    def test_prompt_and_run_protein_workflow_prompt_uses_extracted_inputs(self) -> None:
        """Plan and dispatch the protein-evidence example prompt through the workflow runner.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = (
            "Run protein evidence alignment with genome data/braker3/reference/genome.fa and "
            "protein evidence data/braker3/protein_data/fastas/proteins.fa"
        )
        captured: dict[str, object] = {}

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture workflow invocations from the compatibility path."""
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

        with tempfile.TemporaryDirectory() as tmp:
            payload = _prompt_and_run_impl(
                prompt,
                workflow_runner=fake_workflow_runner,
                recipe_dir=Path(tmp),
            )
            artifact_exists = Path(str(payload["artifact_path"])).exists()

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertTrue(artifact_exists)
        self.assertEqual(captured["workflow_name"], SUPPORTED_PROTEIN_WORKFLOW_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "protein_fastas": ["data/braker3/protein_data/fastas/proteins.fa"],
            },
        )
        self.assertEqual(payload["result_summary"]["status"], "succeeded")
        self.assertEqual(payload["result_summary"]["result_code"], "succeeded")
        self.assertEqual(payload["result_summary"]["reason_code"], "completed")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_PROTEIN_WORKFLOW_NAME)
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "protein_fastas": ["data/braker3/protein_data/fastas/proteins.fa"],
            },
        )
        self.assertEqual(payload["result_summary"]["output_paths"], ["/tmp/protein_evidence_results"])

    def test_prompt_and_run_task_prompt_uses_extracted_inputs(self) -> None:
        """Plan and dispatch the Exonerate example prompt through the task runner.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = (
            "Experiment with Exonerate protein-to-genome alignment using genome "
            "data/braker3/reference/genome.fa and protein chunk data/braker3/protein_data/fastas/proteins.fa"
        )
        captured: dict[str, object] = {}

        def fake_task_runner(task_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture task invocations from the compatibility path."""
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

        with tempfile.TemporaryDirectory() as tmp:
            payload = _prompt_and_run_impl(
                prompt,
                task_runner=fake_task_runner,
                recipe_dir=Path(tmp),
            )
            artifact_exists = Path(str(payload["artifact_path"])).exists()

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertTrue(artifact_exists)
        self.assertEqual(captured["task_name"], SUPPORTED_TASK_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "protein_chunk": "data/braker3/protein_data/fastas/proteins.fa",
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
                "genome": "data/braker3/reference/genome.fa",
                "protein_chunk": "data/braker3/protein_data/fastas/proteins.fa",
            },
        )
        self.assertEqual(payload["result_summary"]["output_paths"], ["/tmp/exonerate_results"])

    def test_run_task_supports_busco_fixture_task(self) -> None:
        """Dispatch the M18 BUSCO fixture task through the direct task runner.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""

        class _Result:
            """Small fake Flyte directory result used by the BUSCO task runner.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

            def download_sync(self) -> str:
                """Return the synthetic BUSCO output path."""
                return "/tmp/busco_fixture_results"

        captured: dict[str, object] = {}

        def fake_busco_assess_proteins(**kwargs: object) -> _Result:
            """Capture the BUSCO task inputs and return a synthetic result object."""
            captured.update(kwargs)
            return _Result()

        with patch("flytetest.tasks.functional.busco_assess_proteins", side_effect=fake_busco_assess_proteins):
            payload = run_task(
                "busco_assess_proteins",
                {
                    "proteins_fasta": "data/busco/test_data/eukaryota/genome.fna",
                    "lineage_dataset": "auto-lineage",
                    "busco_cpu": 2,
                    "busco_mode": "geno",
                },
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["exit_status"], 0)
        self.assertEqual(payload["output_paths"], ["/tmp/busco_fixture_results"])
        self.assertEqual(captured["lineage_dataset"], "auto-lineage")
        self.assertEqual(captured["busco_cpu"], 2)
        self.assertEqual(captured["busco_mode"], "geno")

    def test_prompt_and_run_no_longer_blocks_downstream_terms(self) -> None:
        """Execute the day-one target without the old downstream term blocklist.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = (
            "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa, "
            "then continue into EVM and BUSCO."
        )

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture workflow invocations from the compatibility path."""
            self.assertEqual(workflow_name, SUPPORTED_PROTEIN_WORKFLOW_NAME)
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

        with tempfile.TemporaryDirectory() as tmp:
            payload = _prompt_and_run_impl(
                prompt,
                workflow_runner=fake_workflow_runner,
                recipe_dir=Path(tmp),
            )

        self.assertTrue(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertEqual(payload["result_summary"]["status"], "succeeded")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_PROTEIN_WORKFLOW_NAME)

    def test_prompt_and_run_declines_missing_inputs(self) -> None:
        """Decline supported language when the prompt omits explicit runnable paths.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = "Experiment with Exonerate protein-to-genome alignment on this genome."

        payload = prompt_and_run(prompt)

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertEqual(payload["plan"]["matched_entry_names"], [SUPPORTED_TASK_NAME])
        self.assertIn("genome", payload["plan"]["missing_requirements"][0])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertEqual(payload["result_summary"]["result_code"], "declined_missing_inputs")
        self.assertEqual(payload["result_summary"]["reason_code"], "missing_required_inputs")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_TASK_NAME)

    def test_prompt_and_run_declines_unsupported_request_with_codes(self) -> None:
        """Return stable unsupported-request codes when the prompt does not map cleanly.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = prompt_and_run("Summarize the repository status for me.")

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertEqual(payload["plan"]["matched_entry_names"], [])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertEqual(payload["result_summary"]["result_code"], "declined_unsupported_request")
        self.assertEqual(payload["result_summary"]["reason_code"], "unsupported_or_ambiguous_request")

    def test_prompt_and_run_summarizes_execution_failure(self) -> None:
        """Report a compact failure summary when the matched execution returns non-zero.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = (
            "Annotate the genome sequence using BRAKER3 "
            "with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa"
        )

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture workflow invocations from the compatibility path."""
            self.assertEqual(workflow_name, SUPPORTED_WORKFLOW_NAME)
            self.assertEqual(
                inputs,
                {
                    "genome": "data/braker3/reference/genome.fa",
                    "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
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

        with tempfile.TemporaryDirectory() as tmp:
            payload = _prompt_and_run_impl(
                prompt,
                workflow_runner=fake_workflow_runner,
                recipe_dir=Path(tmp),
            )

        self.assertFalse(payload["supported"])
        self.assertTrue(payload["execution_attempted"])
        self.assertEqual(payload["result_summary"]["status"], "failed")
        self.assertEqual(payload["result_summary"]["result_code"], "failed_execution")
        self.assertEqual(payload["result_summary"]["reason_code"], "nonzero_exit_status")
        self.assertEqual(payload["result_summary"]["exit_status"], 1)
        self.assertEqual(
            payload["result_summary"]["used_inputs"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
            },
        )
        self.assertIn("BRAKER3 failed to start", payload["result_summary"]["message"])

    def test_run_workflow_builds_expected_flyte_command(self) -> None:
        """Shell out through the compatibility entrypoint with explicit local inputs.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        captured: dict[str, object] = {}

        def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            """Simulate an external command invocation and record the provided args."""
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
                "genome": "data/braker3/reference/genome.fa",
                "rnaseq_bam_path": "data/braker3/rnaseq/RNAseq.bam",
                "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
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
        self.assertIn("data/braker3/reference/genome.fa", command)
        self.assertIn("--rnaseq_bam_path", command)
        self.assertIn("--protein_fasta_path", command)
        self.assertEqual(response["exit_status"], 0)

    def test_prepare_direct_workflow_inputs_wraps_collection_file_values(self) -> None:
        """Coerce collection-shaped workflow inputs into Flyte file artifacts for direct calls.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        from flyte.io import File
        from flytetest.workflows.protein_evidence import protein_evidence_alignment

        prepared = _prepare_direct_workflow_inputs(
            protein_evidence_alignment,
            {
                "genome": "data/braker3/reference/genome.fa",
                "protein_fastas": [
                    "data/braker3/protein_data/fastas/proteins.fa",
                    "data/braker3/protein_data/fastas/proteins_extra.fa",
                ],
                "proteins_per_chunk": 250,
            },
        )

        self.assertIsInstance(prepared["genome"], File)
        self.assertEqual(prepared["genome"].path, "data/braker3/reference/genome.fa")
        self.assertEqual([artifact.path for artifact in prepared["protein_fastas"]], [
            "data/braker3/protein_data/fastas/proteins.fa",
            "data/braker3/protein_data/fastas/proteins_extra.fa",
        ])
        self.assertEqual(prepared["proteins_per_chunk"], 250)

    def test_run_workflow_uses_direct_python_for_collection_inputs(self) -> None:
        """Bypass the Flyte CLI when a workflow input includes collection-shaped values.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        captured: dict[str, object] = {}

        def fake_direct(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            """Capture direct workflow invocation inputs for the compatibility path."""
            captured["workflow_name"] = workflow_name
            captured["inputs"] = inputs
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
                "output_paths": ["/tmp/protein_evidence_results"],
                "limitations": [],
            }

        with patch("flytetest.server._run_workflow_direct", side_effect=fake_direct) as direct_runner:
            response = run_workflow(
                workflow_name=SUPPORTED_PROTEIN_WORKFLOW_NAME,
                inputs={
                    "genome": "data/braker3/reference/genome.fa",
                    "protein_fastas": [
                        "data/braker3/protein_data/fastas/proteins.fa",
                        "data/braker3/protein_data/fastas/proteins_extra.fa",
                    ],
                    "proteins_per_chunk": 250,
                },
            )

        self.assertEqual(direct_runner.call_count, 1)
        self.assertTrue(response["supported"])
        self.assertEqual(response["execution_mode"], "direct-python-call")
        self.assertEqual(captured["workflow_name"], SUPPORTED_PROTEIN_WORKFLOW_NAME)
        self.assertEqual(
            captured["inputs"],
            {
                "genome": "data/braker3/reference/genome.fa",
                "protein_fastas": [
                    "data/braker3/protein_data/fastas/proteins.fa",
                    "data/braker3/protein_data/fastas/proteins_extra.fa",
                ],
                "proteins_per_chunk": 250,
            },
        )
        self.assertEqual(response["exit_status"], 0)

    def test_resolve_flyte_cli_prefers_repo_local_virtualenv_binary(self) -> None:
        """Use the repo-local `.venv` Flyte CLI when this checkout provides one.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        self.assertEqual(
            _resolve_flyte_cli(),
            str((Path(__file__).resolve().parents[1] / ".venv" / "bin" / "flyte")),
        )

    # ------------------------------------------------------------------
    # Slurm terminal-state monitoring
    # ------------------------------------------------------------------

    def _submit_busco_slurm_recipe(self, tmp_path: Path, job_id: str) -> dict[str, object]:
        """Prepare and submit a BUSCO Slurm recipe, returning the submission payload.

        Shared setup for monitor and retry tests that need an already-submitted
        run record to work from.  The sbatch call is faked so no real cluster
        access is required.

        Args:
            tmp_path: Temporary directory that owns the recipe artifact and run records.
            job_id: Synthetic Slurm job ID to embed in the fake sbatch response.
        """
        result_dir = _repeat_filter_manifest_dir(tmp_path)
        prepared = _prepare_run_recipe_impl(
            "Run BUSCO quality assessment on the annotation.",
            manifest_sources=(result_dir,),
            runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
            resource_request={
                "cpu": 8,
                "memory": "32Gi",
                "queue": "caslake",
                "account": "rcc-staff",
                "walltime": "02:00:00",
            },
            execution_profile="slurm",
            recipe_dir=tmp_path,
        )
        return _run_slurm_recipe_impl(
            str(prepared["artifact_path"]),
            run_dir=tmp_path / "runs",
            sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                args=args, returncode=0, stdout=f"Submitted batch job {job_id}\n", stderr=""
            ),
            command_available=lambda _: True,
        )

    def _fake_terminal_scheduler(
        self, job_id: str, state: str, exit_code: str = "0:0"
    ):
        """Return a fake scheduler runner reporting a terminal state for one job.

        Simulates a job that has left squeue (empty squeue response) and is
        visible only through sacct — the normal path for completed Slurm jobs.

        Args:
            job_id: Slurm job identifier expected in sacct output.
            state: Terminal scheduler state to report (e.g. ``"COMPLETED"``).
            exit_code: Exit code string to embed in the sacct response.
        """
        def runner(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
            """Dispatch canned responses for squeue, scontrol, and sacct."""
            if args[0] == "squeue":
                # Empty response: job has aged off the active queue.
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if args[0] == "scontrol":
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if args[0] == "sacct":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=f"{job_id}|{state}|{exit_code}\n",
                    stderr="",
                )
            raise AssertionError(f"unexpected scheduler command: {args}")
        return runner

    def test_monitor_slurm_job_reports_completed_terminal_state(self) -> None:
        """Set final_scheduler_state when monitor reconciles a COMPLETED job.

        final_scheduler_state being non-null is the MCP client polling gate;
        this test verifies it is populated when the job reaches a terminal state.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "71001")

            status = _monitor_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=self._fake_terminal_scheduler("71001", "COMPLETED"),
                command_available=lambda _: True,
            )

        self.assertTrue(status["supported"])
        self.assertEqual(status["lifecycle_result"]["scheduler_state"], "COMPLETED")
        self.assertIsNotNone(status["lifecycle_result"]["final_scheduler_state"])
        self.assertEqual(status["lifecycle_result"]["final_scheduler_state"], "COMPLETED")

    def test_monitor_slurm_job_reports_failed_terminal_state(self) -> None:
        """Expose stdout_path and stderr_path when monitor reconciles a FAILED job.

        Clients need these paths to retrieve diagnostic output after a failure;
        this test verifies they are present in the response for terminal states.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "71002")

            status = _monitor_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=self._fake_terminal_scheduler("71002", "FAILED", "1:0"),
                command_available=lambda _: True,
            )

        self.assertTrue(status["supported"])
        self.assertEqual(status["lifecycle_result"]["final_scheduler_state"], "FAILED")
        self.assertIsNotNone(status["lifecycle_result"]["stdout_path"])
        self.assertIsNotNone(status["lifecycle_result"]["stderr_path"])

    def test_monitor_slurm_job_reports_timeout_terminal_state(self) -> None:
        """TIMEOUT is a terminal state: supported=True with final_scheduler_state set.

        Distinguishing TIMEOUT from FAILED matters because TIMEOUT requires a
        new prepare_run_recipe call with updated walltime rather than a retry.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "71003")

            status = _monitor_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=self._fake_terminal_scheduler("71003", "TIMEOUT"),
                command_available=lambda _: True,
            )

        self.assertTrue(status["supported"])
        self.assertEqual(status["lifecycle_result"]["scheduler_state"], "TIMEOUT")
        self.assertIsNotNone(status["lifecycle_result"]["final_scheduler_state"])

    def test_monitor_slurm_job_uses_sacct_when_squeue_is_empty(self) -> None:
        """Fall back to sacct when squeue has no record of the job.

        Jobs age off squeue after completion; this is the normal COMPLETED
        transition path in practice.  The source field confirms sacct was used.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "71004")

            # squeue returns empty; sacct carries the COMPLETED state.
            def fake_scheduler(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
                """Simulate squeue miss and sacct hit for a completed job."""
                if args[0] == "squeue":
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
                if args[0] == "scontrol":
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
                if args[0] == "sacct":
                    return subprocess.CompletedProcess(
                        args=args, returncode=0, stdout="71004|COMPLETED|0:0\n", stderr=""
                    )
                raise AssertionError(args)

            status = _monitor_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=fake_scheduler,
                command_available=lambda _: True,
            )

        self.assertTrue(status["supported"])
        self.assertEqual(status["lifecycle_result"]["scheduler_state"], "COMPLETED")
        # sacct was the source because squeue had no record.
        self.assertEqual(status["lifecycle_result"]["scheduler_snapshot"]["source"], "sacct")

    # ------------------------------------------------------------------
    # retry_slurm_job — additional terminal-state branches
    # ------------------------------------------------------------------

    def _submit_and_force_state(
        self, tmp_path: Path, job_id: str, state: str, exit_code: str = "1:0"
    ) -> dict[str, object]:
        """Submit a BUSCO recipe and overwrite the run record to a given terminal state.

        Args:
            tmp_path: Temporary directory owning all recipe and run files.
            job_id: Synthetic Slurm job ID to use for submission.
            state: Terminal scheduler state to force into the durable run record.
            exit_code: Exit code string to embed in the forced state.
        """
        submitted = self._submit_busco_slurm_recipe(tmp_path, job_id)
        record = load_slurm_run_record(Path(str(submitted["run_record_path"])))
        forced = record.__class__.from_dict({
            **record.to_dict(),
            "scheduler_state": state,
            "scheduler_exit_code": exit_code,
            "final_scheduler_state": state,
            "failure_classification": None,
        })
        save_slurm_run_record(forced)
        return submitted

    def test_retry_slurm_job_declines_timeout_failure(self) -> None:
        """TIMEOUT is terminal: retry must decline and explain resource escalation is needed.

        Only OOM was previously tested; this covers the other resource-exhaustion
        terminal state that requires a new prepare_run_recipe call with updated walltime.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_and_force_state(tmp_path, "72001", "TIMEOUT")

            retried = _retry_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sbatch should not be called")),
                command_available=lambda _: True,
            )

        self.assertFalse(retried["supported"])
        self.assertIn("not retryable", retried["limitations"][0])

    def test_retry_slurm_job_declines_cancelled_record(self) -> None:
        """CANCELLED is terminal: retry must decline without resubmitting.

        A cancelled job has no exit code to classify; the retry path should
        recognise the terminal state and return a clear limitation message.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_and_force_state(tmp_path, "72002", "CANCELLED", "0:0")

            retried = _retry_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sbatch should not be called")),
                command_available=lambda _: True,
            )

        self.assertFalse(retried["supported"])

    def test_retry_slurm_job_child_record_links_to_parent(self) -> None:
        """The child run record carries retry_parent_run_record_path pointing to the original.

        This link is required for run-history tracing and for confirming that a
        retry is connected to its originating failed submission.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_and_force_state(tmp_path, "72003", "NODE_FAIL")
            job_ids = iter(("72003", "72004"))

            retried = _retry_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=f"Submitted batch job {next(job_ids)}\n", stderr=""
                ),
                command_available=lambda _: True,
            )

            self.assertTrue(retried["supported"])
            child_record_path = Path(str(retried["retry_run_record_path"]))
            child_record = load_slurm_run_record(child_record_path)

        self.assertIsNotNone(child_record.retry_parent_run_record_path)
        self.assertEqual(
            child_record.retry_parent_run_record_path,
            Path(str(submitted["run_record_path"])).parent / DEFAULT_SLURM_RUN_RECORD_FILENAME,
        )

    # ------------------------------------------------------------------
    # cancel_slurm_job — idempotency and scancel failure
    # ------------------------------------------------------------------

    def test_cancel_slurm_job_is_idempotent(self) -> None:
        """A second cancel on an already-cancelled record must not call scancel again.

        Duplicate scancel calls for a completed job would produce scheduler errors;
        the idempotency guard prevents that without returning an error to the client.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "73001")
            scancel_calls: list[list[str]] = []

            def fake_scheduler(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
                """Record scancel calls and return success."""
                scancel_calls.append(args)
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

            run_record_path = str(submitted["run_record_path"])
            first = _cancel_slurm_job_impl(
                run_record_path,
                run_dir=tmp_path / "runs",
                scheduler_runner=fake_scheduler,
                command_available=lambda _: True,
            )
            second = _cancel_slurm_job_impl(
                run_record_path,
                run_dir=tmp_path / "runs",
                scheduler_runner=fake_scheduler,
                command_available=lambda _: True,
            )

        self.assertTrue(first["supported"])
        self.assertTrue(second["supported"])
        # scancel must have been called exactly once across both cancel calls.
        self.assertEqual(len(scancel_calls), 1)

    def test_cancel_slurm_job_persists_cancellation_when_scancel_fails(self) -> None:
        """cancellation_requested_at is persisted even when scancel returns non-zero.

        The cancellation intent should be durable regardless of whether the scheduler
        accepted the request, so a later reconcile can confirm the final state.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "73002")

            def failing_scancel(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
                """Simulate a scancel that the scheduler rejects (e.g. job already done)."""
                return subprocess.CompletedProcess(
                    args=args, returncode=1, stdout="", stderr="scancel: error: Invalid job id specified"
                )

            cancelled = _cancel_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=failing_scancel,
                command_available=lambda _: True,
            )
            reloaded = load_slurm_run_record(Path(str(submitted["run_record_path"])))

        # The MCP response signals the scheduler rejected the request.
        self.assertFalse(cancelled["supported"])
        # But the durable record still carries the cancellation timestamp.
        self.assertIsNotNone(reloaded.cancellation_requested_at)

    # ------------------------------------------------------------------
    # Full cancel → monitor → CANCELLED cycle
    # ------------------------------------------------------------------

    def test_cancel_then_monitor_shows_cancelled_state(self) -> None:
        """After cancel, a monitor call that reconciles CANCELLED sets final_scheduler_state.

        This covers the full lifecycle sequence a client would follow: cancel the
        job, then poll until final_scheduler_state is non-null.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "74001")
            run_record_path = str(submitted["run_record_path"])

            _cancel_slurm_job_impl(
                run_record_path,
                run_dir=tmp_path / "runs",
                scheduler_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="", stderr=""
                ),
                command_available=lambda _: True,
            )

            # After cancel the record has cancellation_requested_at set but the
            # scheduler has not yet confirmed CANCELLED.  A subsequent monitor
            # call that reconciles the CANCELLED state should close the record.
            # Reload the record directly from disk to bypass the cached path.
            reloaded = load_slurm_run_record(Path(run_record_path))
            # Reset to a schedulable state so reconcile has something to update.
            reset = reloaded.__class__.from_dict({
                **reloaded.to_dict(),
                "scheduler_state": "RUNNING",
                "cancellation_requested_at": None,
                "final_scheduler_state": None,
            })
            save_slurm_run_record(reset)

            status = _monitor_slurm_job_impl(
                run_record_path,
                run_dir=tmp_path / "runs",
                scheduler_runner=self._fake_terminal_scheduler("74001", "CANCELLED"),
                command_available=lambda _: True,
            )

        self.assertTrue(status["supported"])
        self.assertEqual(status["lifecycle_result"]["scheduler_state"], "CANCELLED")
        self.assertIsNotNone(status["lifecycle_result"]["final_scheduler_state"])

    # ------------------------------------------------------------------
    # sbatch script content and script_path existence
    # ------------------------------------------------------------------

    def test_run_slurm_recipe_saves_script_with_correct_directives(self) -> None:
        """The saved sbatch script contains #SBATCH directives matching resource_request.

        The script is the authoritative source for what was submitted; this test
        guards against the frozen resource_request being silently dropped during
        script rendering.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={
                    "cpu": 4,
                    "memory": "16Gi",
                    "queue": "caslake",
                    "account": "rcc-staff",
                    "walltime": "01:00:00",
                },
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="Submitted batch job 75001\n", stderr=""
                ),
                command_available=lambda _: True,
            )
            run_record = load_slurm_run_record(Path(str(submitted["run_record_path"])))
            script_text = run_record.script_path.read_text()

        self.assertIn("#SBATCH --cpus-per-task=4", script_text)
        self.assertIn("#SBATCH --mem=16G", script_text)
        self.assertIn("#SBATCH --partition=caslake", script_text)
        self.assertIn("#SBATCH --account=rcc-staff", script_text)
        self.assertIn("#SBATCH --time=01:00:00", script_text)

    def test_run_slurm_recipe_script_path_points_to_existing_file(self) -> None:
        """The script_path field in the run record points to a file that exists on disk.

        If the script file is missing, the sbatch script cannot be inspected and
        any resubmission from the run record would fail silently.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "75002")
            run_record = load_slurm_run_record(Path(str(submitted["run_record_path"])))

            self.assertTrue(
                run_record.script_path.exists(),
                f"script_path {run_record.script_path} does not exist",
            )

    # ------------------------------------------------------------------
    # slurm_resource_hints in list_entries
    # ------------------------------------------------------------------

    def test_list_entries_exposes_slurm_resource_hints_for_slurm_capable_workflows(self) -> None:
        """list_entries includes slurm_resource_hints for Slurm-capable workflows.

        Clients read these hints to discover starting-point cpu/memory/walltime
        values before calling prepare_run_recipe; the hints must be present and
        non-empty for workflows that support the Slurm execution profile.
        """
        payload = list_entries()
        entries_by_name = {entry["name"]: entry for entry in payload["entries"]}

        busco_entry = entries_by_name[SUPPORTED_BUSCO_WORKFLOW_NAME]
        self.assertIn("slurm_resource_hints", busco_entry)
        hints = busco_entry["slurm_resource_hints"]
        self.assertIn("cpu", hints)
        self.assertIn("memory", hints)
        self.assertIn("walltime", hints)
        # queue and account are site-specific and must never appear in hints.
        self.assertNotIn("queue", hints)
        self.assertNotIn("account", hints)

    # ------------------------------------------------------------------
    # run_slurm_recipe with a prior LocalRunRecord
    # ------------------------------------------------------------------

    def test_run_slurm_recipe_carries_forward_local_resume_node_state(self) -> None:
        """A prior LocalRunRecord's completed nodes are recorded in the Slurm run record.

        When a local run completes some nodes, the Slurm submission should carry
        that state forward so the compute node can skip already-finished stages.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            artifact_path = Path(str(prepared["artifact_path"]))
            from flytetest.spec_artifacts import load_workflow_spec_artifact as _load
            artifact = _load(artifact_path)
            node = artifact.workflow_spec.nodes[0]

            # Build a prior local run record with the first node completed.
            prior_run_dir = tmp_path / "prior_local"
            prior_run_dir.mkdir()
            prior_results_dir = tmp_path / "prior_busco_results"
            prior_results_dir.mkdir()
            (prior_results_dir / "run_manifest.json").write_text(
                json.dumps({"workflow": "annotation_qc_busco", "outputs": {"results_dir": str(prior_results_dir)}})
            )
            prior_record = LocalRunRecord(
                schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
                run_id="prior-local-76001",
                workflow_name=artifact.workflow_spec.name,
                run_record_path=prior_run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
                created_at="2026-04-13T12:00:00Z",
                execution_profile="local",
                resolved_planner_inputs={},
                binding_plan_target=artifact.binding_plan.target_name,
                node_completion_state={node.name: True},
                node_results=(
                    LocalNodeExecutionResult(
                        node_name=node.name,
                        reference_name=node.reference_name,
                        outputs={node.output_names[0]: str(prior_results_dir)},
                    ),
                ),
                artifact_path=artifact_path,
                final_outputs={b.output_name: str(prior_results_dir) for b in artifact.workflow_spec.final_output_bindings},
                completed_at="2026-04-13T12:00:01Z",
            )
            save_local_run_record(prior_record)

            submitted = _run_slurm_recipe_impl(
                str(artifact_path),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="Submitted batch job 76001\n", stderr=""
                ),
                command_available=lambda _: True,
                resume_from_local_record=prior_run_dir,
            )
            slurm_record = load_slurm_run_record(Path(str(submitted["run_record_path"])))

        self.assertTrue(submitted["supported"])
        self.assertIn(node.name, slurm_record.local_resume_node_state)
        self.assertTrue(slurm_record.local_resume_node_state[node.name])

    # ------------------------------------------------------------------
    # Schema version mismatch and duplicate artifact submission
    # ------------------------------------------------------------------

    def test_monitor_slurm_job_rejects_unknown_schema_version(self) -> None:
        """A run record with an unrecognised schema_version raises a clear error.

        A cryptic KeyError or AttributeError from a stale record would be
        harder to diagnose than a version-mismatch message.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "77001")
            record_path = Path(str(submitted["run_record_path"]))

            # Overwrite the record with an unrecognised schema_version.
            payload = json.loads(record_path.read_text())
            payload["schema_version"] = "slurm-run-record-v999"
            record_path.write_text(json.dumps(payload))

            status = _monitor_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
            )

        self.assertFalse(status["supported"])
        self.assertTrue(
            any("schema" in lim.lower() or "version" in lim.lower() for lim in status["limitations"]),
            f"Expected a schema-version message in limitations: {status['limitations']}",
        )

    def test_run_slurm_recipe_twice_produces_independent_run_records(self) -> None:
        """Submitting the same artifact twice produces two records with distinct run_ids.

        Duplicate job IDs in run records would corrupt run history; each
        submission must produce an independent record with a unique run_id.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                "Run BUSCO quality assessment on the annotation.",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            job_ids = iter(("78001", "78002"))

            first = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=f"Submitted batch job {next(job_ids)}\n", stderr=""
                ),
                command_available=lambda _: True,
            )
            second = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=f"Submitted batch job {next(job_ids)}\n", stderr=""
                ),
                command_available=lambda _: True,
            )
            first_record = load_slurm_run_record(Path(str(first["run_record_path"])))
            second_record = load_slurm_run_record(Path(str(second["run_record_path"])))

        self.assertTrue(first["supported"])
        self.assertTrue(second["supported"])
        self.assertNotEqual(first_record.run_id, second_record.run_id)
        self.assertNotEqual(first["run_record_path"], second["run_record_path"])

    # ------------------------------------------------------------------
    # M20a: resource_overrides escalation retry via _retry_slurm_job_impl
    # ------------------------------------------------------------------

    def test_retry_slurm_job_oom_with_resource_overrides_escalates(self) -> None:
        """OOM + resource_overrides memory resubmits with the new memory value.

        Validates that _retry_slurm_job_impl passes resource_overrides through
        to the executor and the child run record reflects the escalated memory.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_and_force_state(tmp_path, "79001", "OUT_OF_MEMORY", "1:0")
            job_ids = iter(("79002",))

            retried = _retry_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=f"Submitted batch job {next(job_ids)}\n", stderr=""
                ),
                command_available=lambda _: True,
                resource_overrides={"memory": "64Gi"},
            )

            child_record = load_slurm_run_record(Path(str(retried["retry_run_record_path"])))

        self.assertTrue(retried["supported"], retried.get("limitations"))
        self.assertEqual(retried["job_id"], "79002")
        self.assertEqual(child_record.resource_spec.memory, "64Gi")
        self.assertIsNotNone(child_record.resource_overrides)
        self.assertEqual(child_record.resource_overrides.memory, "64Gi")

    def test_retry_slurm_job_unknown_resource_override_key_is_declined(self) -> None:
        """An unrecognised resource_overrides key must be declined without submitting.

        The validation must fire for any failure class, not just resource_exhaustion.
        This guards the escalation path from silently ignoring misspelled fields.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_and_force_state(tmp_path, "79101", "NODE_FAIL", "0:0")

            retried = _retry_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sbatch must not be called")),
                command_available=lambda _: True,
                resource_overrides={"unknown_key": "bad_value"},
            )

        self.assertFalse(retried["supported"])
        self.assertTrue(
            any("unknown_key" in lim or "not supported" in lim or "unsupported" in lim for lim in retried["limitations"]),
            f"Expected limitation mentioning unknown_key or unsupported, got: {retried['limitations']}",
        )

    def test_retry_slurm_job_deadline_is_declined_even_with_walltime_override(self) -> None:
        """DEADLINE is not eligible for escalation even when walltime is supplied.

        DEADLINE reflects a scheduler-enforced policy rejection, not a soft
        limit.  The user must call prepare_run_recipe with an updated walltime.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_and_force_state(tmp_path, "79201", "DEADLINE", "0:1")

            retried = _retry_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sbatch must not be called")),
                command_available=lambda _: True,
                resource_overrides={"walltime": "24:00:00"},
            )

        self.assertFalse(retried["supported"])

    # ------------------------------------------------------------------
    # M20a: _read_text_tail and monitor log-tail tests
    # ------------------------------------------------------------------

    def test_read_text_tail_raises_for_negative_tail_lines(self) -> None:
        """_read_text_tail must raise ValueError when tail_lines is negative."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            log_file = tmp_path / "test.log"
            log_file.write_text("line\n")

            with self.assertRaises(ValueError):
                _read_text_tail(log_file, tail_lines=-1, allowed_root=tmp_path)

    def test_read_text_tail_clamps_oversized_tail_lines_to_max(self) -> None:
        """_read_text_tail silently clamps tail_lines above MAX_MONITOR_TAIL_LINES.

        An oversized request must not raise; it should return at most
        MAX_MONITOR_TAIL_LINES lines from the file.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            log_file = tmp_path / "big.log"
            # Write 10 lines; oversized clamp should still return all 10.
            log_file.write_text("\n".join(f"line {i}" for i in range(10)))

            result = _read_text_tail(
                log_file, tail_lines=MAX_MONITOR_TAIL_LINES + 9999, allowed_root=tmp_path
            )

        self.assertIsNotNone(result)
        lines = result.splitlines()
        self.assertLessEqual(len(lines), MAX_MONITOR_TAIL_LINES)
        self.assertEqual(len(lines), 10)

    def test_read_text_tail_returns_none_for_path_outside_allowed_root(self) -> None:
        """_read_text_tail returns None for paths that resolve outside allowed_root.

        This guards against a tampered run record pointing stdout_path at an
        arbitrary file outside the run directory.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir = tmp_path / "runs"
            run_dir.mkdir()
            outside_file = tmp_path / "secret.txt"
            outside_file.write_text("sensitive content\n")

            result = _read_text_tail(outside_file, tail_lines=10, allowed_root=run_dir)

        self.assertIsNone(result)

    def test_monitor_slurm_job_includes_stdout_tail_for_terminal_state(self) -> None:
        """monitor_slurm_job returns stdout_tail with the last N lines when terminal.

        Validates the full pipeline: submit → force terminal state → monitor
        with a log file present → stdout_tail is non-None.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "76001")
            run_record_path = Path(str(submitted["run_record_path"]))
            record = load_slurm_run_record(run_record_path)

            # Write a synthetic stdout log so the tail reader has content.
            log_dir = run_record_path.parent
            stdout_file = log_dir / "slurm-76001.out"
            stdout_file.write_text("\n".join(f"output line {i}" for i in range(10)) + "\n")

            # Force terminal state with paths pointing at the synthetic log.
            forced = record.__class__.from_dict({
                **record.to_dict(),
                "scheduler_state": "COMPLETED",
                "final_scheduler_state": "COMPLETED",
                "scheduler_exit_code": "0:0",
                "failure_classification": None,
                "stdout_path": str(stdout_file),
                "stderr_path": None,
            })
            save_slurm_run_record(forced)

            status = _monitor_slurm_job_impl(
                str(run_record_path),
                run_dir=tmp_path / "runs",
                scheduler_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="76001|COMPLETED|0:0\n" if args[0] == "sacct" else "", stderr=""
                ),
                command_available=lambda _: True,
                tail_lines=5,
            )

        self.assertTrue(status["supported"])
        stdout_tail = status["lifecycle_result"].get("stdout_tail")
        self.assertIsNotNone(stdout_tail, "stdout_tail must be set for a terminal run with a log file")
        # Only the last 5 lines of 10 should be returned.
        tail_lines = stdout_tail.splitlines()
        self.assertLessEqual(len(tail_lines), 5)

    def test_monitor_slurm_job_sets_stdout_tail_to_none_for_running_job(self) -> None:
        """monitor_slurm_job sets stdout_tail to None when the job is still running.

        Log tails must only be present for terminal states.  Returning partial
        logs for a live job could mislead the client about completion.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "76201")

            status = _monitor_slurm_job_impl(
                str(submitted["run_record_path"]),
                run_dir=tmp_path / "runs",
                scheduler_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=("RUNNING\n" if args[0] == "squeue"
                            else f"JobId=76201 JobState=RUNNING ExitCode=0:0 StdOut={tmp_path / 'job.out'} StdErr={tmp_path / 'job.err'} Reason=None\n"
                            if args[0] == "scontrol"
                            else ""),
                    stderr="",
                ),
                command_available=lambda _: True,
            )

        self.assertTrue(status["supported"])
        self.assertIsNone(status["lifecycle_result"].get("stdout_tail"))
        self.assertIsNone(status["lifecycle_result"].get("stderr_tail"))

    def test_monitor_slurm_job_stdout_tail_is_none_when_log_file_absent(self) -> None:
        """monitor_slurm_job sets stdout_tail to None when the log file does not exist.

        A terminal job whose output has been cleaned up or was never written
        must not cause an error; stdout_tail should simply be None.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submitted = self._submit_busco_slurm_recipe(tmp_path, "76301")
            run_record_path = Path(str(submitted["run_record_path"]))
            record = load_slurm_run_record(run_record_path)

            # Force terminal state with a non-existent stdout_path.
            forced = record.__class__.from_dict({
                **record.to_dict(),
                "scheduler_state": "COMPLETED",
                "final_scheduler_state": "COMPLETED",
                "scheduler_exit_code": "0:0",
                "failure_classification": None,
                "stdout_path": str(tmp_path / "nonexistent_76301.out"),
                "stderr_path": None,
            })
            save_slurm_run_record(forced)

            status = _monitor_slurm_job_impl(
                str(run_record_path),
                run_dir=tmp_path / "runs",
                scheduler_runner=lambda args, **kw: subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="76301|COMPLETED|0:0\n" if args[0] == "sacct" else "",
                    stderr="",
                ),
                command_available=lambda _: True,
            )

        self.assertTrue(status["supported"])
        self.assertIsNone(status["lifecycle_result"].get("stdout_tail"))

    # ------------------------------------------------------------------
    # M21 Phase 1 — ad hoc task surface (T1–T4)
    # ------------------------------------------------------------------

    def test_run_task_declines_unknown_task_name(self) -> None:
        """Unknown task name returns supported=False from run_task.

        T1: Guards the eligibility gate so only explicit ShowcaseTarget entries
        can be dispatched through the ad hoc execution surface.
        """
        payload = run_task("nonexistent_task", {})
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["task_name"], "nonexistent_task")
        limitation = payload["limitations"][0]
        self.assertIn("Only", limitation)
        for name in SUPPORTED_TASK_NAMES:
            self.assertIn(f"`{name}`", limitation)

    def test_run_task_declines_missing_required_inputs(self) -> None:
        """Missing required input for a known task returns supported=False.

        T2: Validates that parameter validation fires before any handler is
        reached when a required input is absent.
        """
        payload = run_task("fastqc", {})
        self.assertFalse(payload["supported"])
        self.assertIn("Missing required task inputs", payload["limitations"][0])

    def test_run_task_declines_unknown_input_keys(self) -> None:
        """Extra input key for a known task returns supported=False.

        T3: Prevents callers from silently passing unrecognised keys that would
        be ignored and cause unexpected behaviour.
        """
        payload = run_task(
            "gffread_proteins",
            {
                "annotation_gff3": "a.gff3",
                "genome_fasta": "g.fa",
                "bogus_extra_key": "should_not_be_here",
            },
        )
        self.assertFalse(payload["supported"])
        self.assertIn("Unknown task inputs", payload["limitations"][0])
        self.assertIn("bogus_extra_key", payload["limitations"][0])

    def test_run_task_routes_all_supported_tasks_with_synthetic_handler(self) -> None:
        """Each SUPPORTED_TASK_NAMES entry reaches the handler when inputs are valid.

        T4: Demonstrates that run_task passes validation and dispatches every
        supported task name; uses module-level patches so no real tools run.
        """
        valid_inputs: dict[str, dict[str, object]] = {
            "exonerate_align_chunk": {
                "genome": "g.fa",
                "protein_chunk": "p.fa",
            },
            "busco_assess_proteins": {
                "proteins_fasta": "p.fa",
                "lineage_dataset": "auto-lineage",
            },
            "fastqc": {
                "left": "R1.fastq.gz",
                "right": "R2.fastq.gz",
            },
            "gffread_proteins": {
                "annotation_gff3": "ann.gff3",
                "genome_fasta": "g.fa",
            },
        }

        class _FakeResult:
            """Minimal Flyte result stub that satisfies download_sync."""

            def download_sync(self) -> str:
                """Return a synthetic output path."""
                return "/tmp/fake_result"

        module_map = {
            "exonerate_align_chunk": ("flytetest.tasks.protein_evidence", "exonerate_align_chunk"),
            "busco_assess_proteins": ("flytetest.tasks.functional", "busco_assess_proteins"),
            "fastqc": ("flytetest.tasks.qc", "fastqc"),
            "gffread_proteins": ("flytetest.tasks.filtering", "gffread_proteins"),
        }

        for task_name in SUPPORTED_TASK_NAMES:
            reached: list[str] = []

            def _make_fake(captured_name: str) -> object:
                def _fake(**_kw: object) -> _FakeResult:
                    reached.append(captured_name)
                    return _FakeResult()
                return _fake

            module_path, fn_name = module_map[task_name]
            with patch(f"{module_path}.{fn_name}", side_effect=_make_fake(task_name)):
                payload = run_task(task_name, valid_inputs[task_name])

            self.assertTrue(payload.get("supported"), f"run_task({task_name!r}) should be supported")
            self.assertEqual(len(reached), 1, f"Handler not reached for task {task_name!r}")

    # ------------------------------------------------------------------
    # M21 Phase 2 — binding discovery (T5–T7)
    # ------------------------------------------------------------------

    def test_list_available_bindings_declines_unknown_task(self) -> None:
        """Unknown task name returns supported=False from list_available_bindings.

        T5: Mirrors the run_task eligibility gate for the binding discovery tool.
        """
        payload = list_available_bindings("not_a_real_task")
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["task_name"], "not_a_real_task")

    def test_list_available_bindings_finds_files_matching_fasta_pattern(self) -> None:
        """FASTA files planted under search_root appear in the binding list.

        T6: Validates that the depth-3 heuristic scan returns real files for
        parameters whose suffix maps to FASTA extensions.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fasta_file = tmp_path / "genome.fasta"
            fasta_file.write_text(">seq1\nACGT\n")
            payload = _list_available_bindings_impl("gffread_proteins", search_root=str(tmp_path))

        self.assertTrue(payload["supported"])
        bindings = payload["bindings"]
        self.assertIn("genome_fasta", bindings)
        genome_candidates = bindings["genome_fasta"]
        self.assertIsInstance(genome_candidates, list)
        self.assertEqual(len(genome_candidates), 1)
        self.assertIn("genome.fasta", genome_candidates[0])

    def test_list_available_bindings_returns_scalar_hints_for_non_path_params(self) -> None:
        """Scalar parameters return a hint string, not a file list.

        T7: Ensures callers are told to enter a value manually instead of
        receiving an empty file list for string/int parameters.
        """
        with tempfile.TemporaryDirectory() as tmp:
            payload = _list_available_bindings_impl("gffread_proteins", search_root=tmp)

        bindings = payload["bindings"]
        scalar_hint = bindings.get("protein_output_stem")
        self.assertIsInstance(scalar_hint, str)
        self.assertIn("scalar", scalar_hint)

    # ------------------------------------------------------------------
    # M21 Phase 3 — run dashboard (T8–T10)
    # ------------------------------------------------------------------

    def test_get_run_summary_returns_empty_for_missing_run_dir(self) -> None:
        """Missing run directory returns supported=True with empty results.

        T8: A fresh install or a clean test environment must not cause an error.
        """
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does_not_exist"
            payload = _get_run_summary_impl(run_dir=missing)

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["total_scanned"], 0)
        self.assertEqual(payload["recent"], [])
        self.assertEqual(payload["by_state"], {})

    def test_get_run_summary_groups_slurm_records_by_state(self) -> None:
        """Slurm records are counted in by_state and appear in recent.

        T9: Validates state grouping logic for COMPLETED and FAILED records.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def _write_slurm_record(subdir: str, state: str, final: str | None) -> None:
                run_dir = tmp_path / subdir
                run_dir.mkdir()
                record_path = run_dir / DEFAULT_SLURM_RUN_RECORD_FILENAME
                data = {
                    "schema_version": SLURM_RUN_RECORD_SCHEMA_VERSION,
                    "run_id": subdir,
                    "recipe_id": "test-recipe",
                    "workflow_name": "annotation_qc_busco",
                    "artifact_path": str(tmp_path / "artifact.json"),
                    "script_path": str(tmp_path / "script.sh"),
                    "stdout_path": str(tmp_path / "out.txt"),
                    "stderr_path": str(tmp_path / "err.txt"),
                    "run_record_path": str(record_path),
                    "job_id": "99001",
                    "execution_profile": "slurm",
                    "scheduler_state": state,
                    "final_scheduler_state": final,
                }
                record_path.write_text(json.dumps(data))

            _write_slurm_record("run_completed", "COMPLETED", "COMPLETED")
            _write_slurm_record("run_failed", "FAILED", "FAILED")

            result = _get_run_summary_impl(run_dir=tmp_path)

        self.assertTrue(result["supported"])
        self.assertEqual(result["total_scanned"], 2)
        self.assertEqual(result["by_state"].get("COMPLETED"), 1)
        self.assertEqual(result["by_state"].get("FAILED"), 1)
        kinds = {entry["kind"] for entry in result["recent"]}
        self.assertEqual(kinds, {"slurm"})

    def test_get_run_summary_includes_local_run_records(self) -> None:
        """Local run records appear in recent with kind='local'.

        T10: Validates that local (non-Slurm) records are discovered and
        reported with correct state inference from completed_at.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir = tmp_path / "run_local_001"
            run_dir.mkdir()
            record_path = run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME
            data = {
                "schema_version": LOCAL_RUN_RECORD_SCHEMA_VERSION,
                "run_id": "local-001",
                "workflow_name": "annotation_qc_busco",
                "run_record_path": str(record_path),
                "created_at": "2026-04-14T10:00:00Z",
                "execution_profile": "local",
                "resolved_planner_inputs": {},
                "binding_plan_target": "annotation_qc_busco",
                "node_completion_state": {},
                "node_results": [],
                "completed_at": "2026-04-14T10:05:00Z",
            }
            record_path.write_text(json.dumps(data))

            result = _get_run_summary_impl(run_dir=tmp_path)

        self.assertTrue(result["supported"])
        self.assertEqual(result["total_scanned"], 1)
        self.assertEqual(result["by_state"].get("COMPLETED"), 1)
        self.assertEqual(len(result["recent"]), 1)
        entry = result["recent"][0]
        self.assertEqual(entry["kind"], "local")
        self.assertEqual(entry["state"], "COMPLETED")
        self.assertEqual(entry["workflow_name"], "annotation_qc_busco")

    # ------------------------------------------------------------------
    # M21b — HPC Observability
    # ------------------------------------------------------------------

    def test_resource_run_recipe_returns_json_of_valid_file(self) -> None:
        """resource_run_recipe reads a JSON file inside REPO_ROOT.

        T11: Validates that a file within the allowed root is returned verbatim.
        """
        import json as _json
        from flytetest.server import REPO_ROOT

        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            recipe_path = Path(tmp) / "recipe.json"
            payload = {"recipe_id": "test-recipe", "workflow_name": "braker3_annotation"}
            recipe_path.write_text(_json.dumps(payload))

            result = resource_run_recipe(str(recipe_path))

        loaded = _json.loads(result)
        self.assertEqual(loaded["recipe_id"], "test-recipe")

    def test_resource_result_manifest_returns_run_manifest_json(self) -> None:
        """resource_result_manifest reads run_manifest.json inside REPO_ROOT.

        T12: Validates manifest look-up when a directory is supplied.
        """
        import json as _json
        from flytetest.server import REPO_ROOT

        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            manifest = {"status": "COMPLETED", "workflow": "braker3_annotation"}
            (Path(tmp) / "run_manifest.json").write_text(_json.dumps(manifest))

            result = resource_result_manifest(tmp)

        loaded = _json.loads(result)
        self.assertEqual(loaded["status"], "COMPLETED")

    def test_fetch_job_log_returns_tail_of_existing_log(self) -> None:
        """fetch_job_log returns file content when the log exists inside run dir.

        T13: Validates content is returned and supported=True for a valid log.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            log = tmp_path / "slurm-12345.out"
            log.write_text("line1\nline2\nline3\n")

            result = _fetch_job_log_impl(str(log), 10, run_dir=tmp_path)

        self.assertTrue(result["supported"])
        self.assertIn("line1", result["content"])
        self.assertEqual(result["log_path"], str(log))

    def test_fetch_job_log_returns_not_supported_for_absent_file(self) -> None:
        """fetch_job_log returns supported=False when the log file does not exist.

        T14: Validates graceful handling of missing log files.
        """
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nothere.out"
            result = _fetch_job_log_impl(str(missing), 10, run_dir=Path(tmp))

        self.assertFalse(result["supported"])
        self.assertIsNone(result["content"])
        self.assertTrue(len(result["limitations"]) > 0)

    def test_fetch_job_log_returns_not_supported_outside_run_dir(self) -> None:
        """fetch_job_log refuses to read files outside the run directory.

        T15: Validates path-traversal protection.
        """
        with tempfile.TemporaryDirectory() as run_tmp:
            with tempfile.TemporaryDirectory() as outside_tmp:
                log = Path(outside_tmp) / "escape.out"
                log.write_text("secret\n")
                result = _fetch_job_log_impl(str(log), 10, run_dir=Path(run_tmp))

        self.assertFalse(result["supported"])
        self.assertIsNone(result["content"])

    def test_wait_for_slurm_job_returns_immediately_when_terminal_on_first_poll(
        self,
    ) -> None:
        """wait_for_slurm_job returns timed_out=False with no sleep when already terminal.

        T16: Validates that a job already in a terminal state resolves in one poll.
        """
        terminal_result = {
            "supported": True,
            "run_record_path": "/fake/record.json",
            "lifecycle_result": {"final_scheduler_state": "COMPLETED"},
            "limitations": [],
        }
        sleep_calls: list[float] = []

        with patch("flytetest.server._monitor_slurm_job_impl", return_value=terminal_result):
            result = _wait_for_slurm_job_impl(
                "/fake/record.json",
                timeout_s=60,
                poll_interval_s=10,
                sleep_fn=sleep_calls.append,
            )

        self.assertFalse(result.get("timed_out"))
        self.assertEqual(sleep_calls, [])

    def test_wait_for_slurm_job_sleeps_when_terminal_on_second_poll(self) -> None:
        """wait_for_slurm_job sleeps once when the job turns terminal on the second poll.

        T17: Validates one sleep cycle before the terminal poll completes.
        """
        call_count = 0

        terminal_result = {
            "supported": True,
            "run_record_path": "/fake/record.json",
            "lifecycle_result": {"final_scheduler_state": "COMPLETED"},
            "limitations": [],
        }
        running_result = {
            "supported": True,
            "run_record_path": "/fake/record.json",
            "lifecycle_result": {"final_scheduler_state": None},
            "limitations": [],
        }

        def fake_monitor(*_a: object, **_kw: object) -> dict:
            nonlocal call_count
            call_count += 1
            return running_result if call_count == 1 else terminal_result

        sleep_calls: list[float] = []

        with patch("flytetest.server._monitor_slurm_job_impl", side_effect=fake_monitor):
            result = _wait_for_slurm_job_impl(
                "/fake/record.json",
                timeout_s=60,
                poll_interval_s=10,
                sleep_fn=sleep_calls.append,
            )

        self.assertFalse(result.get("timed_out"))
        self.assertEqual(len(sleep_calls), 1)

    def test_wait_for_slurm_job_times_out_when_never_terminal(self) -> None:
        """wait_for_slurm_job sets timed_out=True when the job never reaches terminal state.

        T18: Validates timeout path with timed_out=True in the returned payload.
        """
        running_result = {
            "supported": True,
            "run_record_path": "/fake/record.json",
            "lifecycle_result": {"final_scheduler_state": None},
            "limitations": [],
        }

        import time as _time

        original_monotonic = _time.monotonic
        calls: list[int] = [0]

        def fake_sleep(_: float) -> None:
            calls[0] += 1

        def fast_deadline() -> float:
            # Return a time that expires after 2 real seconds of monotonic
            # elapsed.  We use a counter approach with patch instead.
            return original_monotonic()

        with patch("flytetest.server._monitor_slurm_job_impl", return_value=running_result):
            # Use a 0-second timeout so it expires immediately after the first poll.
            result = _wait_for_slurm_job_impl(
                "/fake/record.json",
                timeout_s=0,
                poll_interval_s=5,
                sleep_fn=fake_sleep,
            )

        self.assertTrue(result.get("timed_out"))
