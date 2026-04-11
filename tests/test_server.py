"""Synthetic tests for the FLyteTest MCP recipe-backed server.

These checks keep the server transport MCP-shaped while preserving the explicit
recipe-backed execution target set.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
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
    MCP_RESOURCE_URIS,
    MCP_TOOL_NAMES,
    PRIMARY_TOOL_NAME,
    PROTEIN_WORKFLOW_EXAMPLE_PROMPT,
    RESULT_CODE_DEFINITIONS,
    SHOWCASE_SERVER_NAME,
    SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME,
    SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME,
    SUPPORTED_AGAT_WORKFLOW_NAME,
    SUPPORTED_BUSCO_WORKFLOW_NAME,
    SUPPORTED_EGGNOG_WORKFLOW_NAME,
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
    _prepare_direct_workflow_inputs,
    _prompt_and_run_impl,
    _resolve_flyte_cli,
    _should_skip_stdio_line,
    _prepare_run_recipe_impl,
    _cancel_slurm_job_impl,
    _monitor_slurm_job_impl,
    _retry_slurm_job_impl,
    _run_local_recipe_impl,
    _run_slurm_recipe_impl,
    create_mcp_server,
    list_entries,
    plan_request,
    prompt_and_run,
    prepare_run_recipe,
    monitor_slurm_job,
    retry_slurm_job,
    cancel_slurm_job,
    resource_example_prompts,
    resource_prompt_and_run_contract,
    resource_scope,
    resource_supported_targets,
    run_local_recipe,
    run_slurm_recipe,
    run_task,
    run_workflow,
)
from flytetest.spec_artifacts import load_workflow_spec_artifact
from flytetest.spec_executor import load_slurm_run_record, save_slurm_run_record

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
        """Record the server name and the decorators registered during setup."""
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
    """Coverage for the FastMCP surface and recipe-backed behavior."""

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
        """List only the explicitly runnable MCP recipe targets."""
        payload = list_entries()

        self.assertEqual([entry["name"] for entry in payload["entries"]], EXPECTED_TARGET_NAMES)
        self.assertEqual(payload["server_tools"], list(MCP_TOOL_NAMES))
        self.assertIn(f"`{SUPPORTED_WORKFLOW_NAME}`", payload["limitations"][0])
        self.assertIn(f"`{SUPPORTED_PROTEIN_WORKFLOW_NAME}`", payload["limitations"][0])
        self.assertIn(f"`{SUPPORTED_TASK_NAME}`", payload["limitations"][0])
        self.assertIn("annotation_qc_busco", payload["limitations"][0])
        self.assertIn("annotation_functional_eggnog", payload["limitations"][0])
        self.assertIn("annotation_postprocess_agat_cleanup", payload["limitations"][0])

    def test_scope_resource_describes_the_recipe_surface(self) -> None:
        """Describe the stdio recipe contract without implying broader support."""
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
        self.assertIn("explicit local file paths", payload["prompt_requirements"][0])

    def test_prompt_and_run_contract_resource_matches_enforced_summary_behavior(self) -> None:
        """Document the stable result-summary contract without widening showcase scope."""
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
        """Classify the BRAKER3 prompt and freeze explicit local paths."""
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
        """Expose broader typed planning data without executing it."""
        payload = plan_request("Create a generated WorkflowSpec for repeat filtering and BUSCO QC.")

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["candidate_outcome"], "generated_workflow_spec")
        self.assertEqual(payload["biological_goal"], "repeat_filter_then_busco_qc")
        self.assertIsNotNone(payload["workflow_spec"])

    def test_plan_request_builds_protein_workflow_recipe_plan(self) -> None:
        """Classify the protein-evidence prompt and preserve protein FASTA order."""
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
        """Prepare a frozen recipe and execute it through explicit local handlers."""
        prompt = (
            "Run protein evidence alignment with genome data/braker3/reference/genome.fa and "
            "protein evidence data/braker3/protein_data/fastas/proteins.fa"
        )
        calls: list[dict[str, object]] = []

        def handler(request):  # type: ignore[no-untyped-def]
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

    def test_run_slurm_recipe_submits_saved_slurm_artifact(self) -> None:
        """Submit a frozen Slurm-profile recipe and persist a run record."""
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

    def test_run_slurm_recipe_rejects_local_profile_artifact(self) -> None:
        """Require Slurm recipes to be explicitly frozen with the Slurm profile."""
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

    def test_monitor_slurm_job_reconciles_saved_record(self) -> None:
        """Expose Slurm status reconciliation through the server helper."""
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
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 44444\n", stderr="")

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
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
        """Expose Slurm cancellation through the server helper."""
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
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 55555\n", stderr="")

            submitted = _run_slurm_recipe_impl(
                str(prepared["artifact_path"]),
                run_dir=tmp_path / "runs",
                sbatch_runner=fake_sbatch,
                command_available=lambda command: True,
            )
            calls: list[list[str]] = []

            def fake_scheduler(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
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
        """Expose explicit Slurm retry through the server helper."""
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
        """Report terminal resource failures without resubmitting them."""
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
        """Report missing run records instead of inventing state."""
        with tempfile.TemporaryDirectory() as tmp:
            status = _monitor_slurm_job_impl(Path(tmp) / "missing")

        self.assertFalse(status["supported"])
        self.assertIn("No such file", status["limitations"][0])

    def test_run_slurm_recipe_reports_missing_sbatch_as_unsupported_environment(self) -> None:
        """Expose an authenticated-environment diagnostic when `sbatch` is unavailable."""
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
        """Expose an authenticated-environment diagnostic when monitoring commands are unavailable."""
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
        """Freeze BUSCO recipe bindings from an explicit repeat-filter manifest source."""
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
        """Freeze an explicitly requested Slurm profile into the saved recipe artifact."""
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

    def test_prepare_run_recipe_rejects_missing_manifest_sources(self) -> None:
        """Return a structured decline when a manifest source cannot be validated."""
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
        """Allow the compatibility alias to execute BUSCO from explicit recipe inputs."""
        prompt = "Run BUSCO quality assessment on the annotation."
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
        """Freeze EggNOG recipe bindings from a repeat-filter manifest source."""
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
        """Freeze AGAT recipes from explicit EggNOG and AGAT conversion manifests."""
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
        """Refuse to choose among multiple compatible EggNOG input manifests."""
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
        """Execute EggNOG through the recipe context and local workflow handler."""
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
        """Execute AGAT cleanup from an explicit AGAT conversion manifest source."""
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
        """Plan and dispatch the BRAKER3 example prompt through the workflow runner."""
        prompt = (
            "Annotate the genome sequence of a small eukaryote using BRAKER3 "
            "with genome data/braker3/reference/genome.fa, RNA-seq evidence data/braker3/rnaseq/RNAseq.bam, "
            "and protein evidence data/braker3/protein_data/fastas/proteins.fa"
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
        """Layer broader typed planning into prompt-and-run without changing runnable targets."""
        payload = prompt_and_run("Create a generated WorkflowSpec for repeat filtering and BUSCO QC.")

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertTrue(payload["result_summary"]["typed_planning_available"])
        self.assertEqual(payload["typed_planning"]["candidate_outcome"], "generated_workflow_spec")
        self.assertIsNotNone(payload["typed_planning"]["workflow_spec"])

    def test_prompt_and_run_protein_workflow_prompt_uses_extracted_inputs(self) -> None:
        """Plan and dispatch the protein-evidence example prompt through the workflow runner."""
        prompt = (
            "Run protein evidence alignment with genome data/braker3/reference/genome.fa and "
            "protein evidence data/braker3/protein_data/fastas/proteins.fa"
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
        """Plan and dispatch the Exonerate example prompt through the task runner."""
        prompt = (
            "Experiment with Exonerate protein-to-genome alignment using genome "
            "data/braker3/reference/genome.fa and protein chunk data/braker3/protein_data/fastas/proteins.fa"
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
        """Dispatch the M18 BUSCO fixture task through the direct task runner."""

        class _Result:
            """Small fake Flyte directory result used by the BUSCO task runner."""

            def download_sync(self) -> str:
                """Return the synthetic BUSCO output path."""
                return "/tmp/busco_fixture_results"

        captured: dict[str, object] = {}

        def fake_busco_assess_proteins(**kwargs: object) -> _Result:
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
        """Execute the day-one target without the old downstream term blocklist."""
        prompt = (
            "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa, "
            "then continue into EVM and BUSCO."
        )

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
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
        """Decline supported language when the prompt omits explicit runnable paths."""
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
        """Return stable unsupported-request codes when the prompt does not map cleanly."""
        payload = prompt_and_run("Summarize the repository status for me.")

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertEqual(payload["plan"]["matched_entry_names"], [])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertEqual(payload["result_summary"]["result_code"], "declined_unsupported_request")
        self.assertEqual(payload["result_summary"]["reason_code"], "unsupported_or_ambiguous_request")

    def test_prompt_and_run_summarizes_execution_failure(self) -> None:
        """Report a compact failure summary when the matched execution returns non-zero."""
        prompt = (
            "Annotate the genome sequence using BRAKER3 "
            "with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa"
        )

        def fake_workflow_runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
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
        """Coerce collection-shaped workflow inputs into Flyte file artifacts for direct calls."""
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
        """Bypass the Flyte CLI when a workflow input includes collection-shaped values."""
        captured: dict[str, object] = {}

        def fake_direct(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
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
        """Use the repo-local `.venv` Flyte CLI when this checkout provides one."""
        self.assertEqual(
            _resolve_flyte_cli(),
            str((Path(__file__).resolve().parents[1] / ".venv" / "bin" / "flyte")),
        )
