"""Synthetic tests for the FLyteTest MCP recipe-backed server.

These checks keep the server transport MCP-shaped while preserving the explicit
recipe-backed execution target set.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

import flytetest.planner_types as planner_types_module
from flytetest.config import (
    AGAT_CLEANUP_WORKFLOW_NAME as SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME,
    AGAT_CONVERSION_WORKFLOW_NAME as SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME,
    AGAT_WORKFLOW_NAME as SUPPORTED_AGAT_WORKFLOW_NAME,
    EGGNOG_WORKFLOW_NAME as SUPPORTED_EGGNOG_WORKFLOW_NAME,
    FUNCTIONAL_QC_WORKFLOW_NAME as SUPPORTED_BUSCO_WORKFLOW_NAME,
    TABLE2ASN_WORKFLOW_NAME as SUPPORTED_TABLE2ASN_WORKFLOW_NAME,
)
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
    SUPPORTED_BUSCO_FIXTURE_TASK_NAME,
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
from flytetest.errors import (
    BindingPathMissingError,
    BindingTypeMismatchError,
    ManifestNotFoundError,
    UnknownOutputNameError,
    UnknownRunIdError,
)
from flytetest.server import (
    SERVER_RESOURCE_URIS,
    MAX_MONITOR_TAIL_LINES,
    _execute_run_tool,
    _limitation_reply,
    _unsupported_target_reply,
    _fetch_job_log_impl,
    _get_run_summary_impl,
    _list_available_bindings_impl,
    _path_fields_for,
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
    list_bundles,
    load_bundle,
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
    validate_run_recipe,
    _execute_workflow_direct,
    wait_for_slurm_job,
)
from flytetest.planning import plan_typed_request
from flytetest.registry import InterfaceField, RegistryCompatibilityMetadata, RegistryEntry, get_entry
from flytetest.spec_artifacts import load_workflow_spec_artifact, artifact_from_typed_plan, save_workflow_spec_artifact, SavedWorkflowSpecArtifact
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
BUSCO_GOAL_PROMPT = "BUSCO annotation quality assessment"
PROTEIN_GOAL_PROMPT = "protein evidence alignment"
BRAKER_GOAL_PROMPT = "BRAKER3 ab initio annotation"


@dataclass(frozen=True, slots=True)
class SyntheticBindingBundle:
    custom_fasta_path: Path
    custom_gff3_path: Path | None = None
    source_result_dir: Path | None = None
    label: str = ""


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


def _protein_workflow_bindings(*extra_fastas: str) -> dict[str, object]:
    """Return structured planner bindings for the protein-evidence workflow."""
    reference_genome = planner_types_module.ReferenceGenome(
        fasta_path=Path("data/braker3/reference/genome.fa")
    )
    protein_evidence = planner_types_module.ProteinEvidenceSet(
        reference_genome=reference_genome,
        source_protein_fastas=(
            Path("data/braker3/protein_data/fastas/proteins.fa"),
            *(Path(path) for path in extra_fastas),
        ),
    )
    return {
        "ReferenceGenome": reference_genome,
        "ProteinEvidenceSet": protein_evidence,
    }


def _protein_runtime_inputs(*extra_fastas: str) -> dict[str, object]:
    """Return concrete runtime inputs for the protein-evidence workflow."""
    return {
        "genome": "data/braker3/reference/genome.fa",
        "protein_fastas": [
            "data/braker3/protein_data/fastas/proteins.fa",
            *extra_fastas,
        ],
    }


def _braker_workflow_bindings() -> dict[str, object]:
    """Return structured planner bindings for the BRAKER3 workflow."""
    reference_genome = planner_types_module.ReferenceGenome(
        fasta_path=Path("data/braker3/reference/genome.fa")
    )
    transcript_evidence = planner_types_module.TranscriptEvidenceSet(
        reference_genome=reference_genome,
        merged_bam_path=Path("data/braker3/rnaseq/RNAseq.bam"),
    )
    protein_evidence = planner_types_module.ProteinEvidenceSet(
        reference_genome=reference_genome,
        source_protein_fastas=(Path("data/braker3/protein_data/fastas/proteins.fa"),),
    )
    return {
        "ReferenceGenome": reference_genome,
        "TranscriptEvidenceSet": transcript_evidence,
        "ProteinEvidenceSet": protein_evidence,
    }


def _braker_runtime_inputs() -> dict[str, object]:
    """Return concrete runtime inputs for the BRAKER3 workflow."""
    return {
        "genome": "data/braker3/reference/genome.fa",
        "rnaseq_bam_path": "data/braker3/rnaseq/RNAseq.bam",
        "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
    }


class FakeFastMCP:
    """Small FastMCP stand-in used to capture tool registration."""

    def __init__(self, name: str) -> None:
        """Record the server name and fixture state."""
        self.name = name
        self.tools: dict[str, object] = {}
        self.resources: dict[str, object] = {}
        self.ran = False

    def tool(self, *, description: str | None = None, **_kw):  # type: ignore[no-untyped-def]
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

    def test_supported_target_names_match_expected_set(self) -> None:
        """Derived SUPPORTED_TARGET_NAMES must exactly match the known showcase set.

    This guards against accidental additions or removals when registry entries change.
"""
        from flytetest.mcp_contract import SUPPORTED_TARGET_NAMES
        expected = (
            "ab_initio_annotation_braker3",
            "protein_evidence_alignment",
            "exonerate_align_chunk",
            "busco_assess_proteins",
            "annotation_qc_busco",
            "annotation_functional_eggnog",
            "annotation_postprocess_agat",
            "annotation_postprocess_agat_conversion",
            "annotation_postprocess_agat_cleanup",
            "annotation_postprocess_table2asn",
            "fastqc",
            "gffread_proteins",
            # Milestone H — GATK4 germline variant calling (original 7 tasks + 7 workflows)
            "create_sequence_dictionary",
            "index_feature_file",
            "base_recalibrator",
            "apply_bqsr",
            "haplotype_caller",
            "combine_gvcfs",
            "joint_call_gvcfs",
            "prepare_reference",
            "preprocess_sample",
            "germline_short_variant_discovery",
            "genotype_refinement",
            "preprocess_sample_from_ubam",
            "post_genotyping_refinement",
            # Milestone I — ported tasks (9) + new tasks (5) + renamed workflow + 4 new workflows
            "bwa_mem2_index",
            "bwa_mem2_mem",
            "sort_sam",
            "mark_duplicates",
            "variant_recalibrator",
            "apply_vqsr",
            "merge_bam_alignment",
            "gather_vcfs",
            "calculate_genotype_posteriors",
            "variant_filtration",
            "collect_wgs_metrics",
            "bcftools_stats",
            "multiqc_summarize",
            "snpeff_annotate",
            "sequential_interval_haplotype_caller",
            "small_cohort_filter",
            "pre_call_coverage_qc",
            "post_call_qc_summary",
            "annotate_variants_snpeff",
        )
        self.assertEqual(set(SUPPORTED_TARGET_NAMES), set(expected))

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
        self.assertTrue(payload["supported"])
        self.assertIn("limitations", payload)
        entries = payload["entries"]
        entries_by_name = {entry["name"]: entry for entry in entries}

        self.assertEqual([entry["name"] for entry in entries], EXPECTED_TARGET_NAMES)
        self.assertIn("slurm", entries_by_name[SUPPORTED_WORKFLOW_NAME]["supported_execution_profiles"])
        self.assertIn("slurm", entries_by_name[SUPPORTED_BUSCO_FIXTURE_TASK_NAME]["supported_execution_profiles"])
        self.assertEqual(entries_by_name[SUPPORTED_TASK_NAME]["supported_execution_profiles"], ["local"])
        # wider payload fields
        wf_entry = entries_by_name[SUPPORTED_WORKFLOW_NAME]
        self.assertIn("pipeline_family", wf_entry)
        self.assertIn("biological_stage", wf_entry)
        self.assertIn("accepted_planner_types", wf_entry)
        self.assertIn("produced_planner_types", wf_entry)
        self.assertIn("inputs", wf_entry)
        self.assertIn("tags", wf_entry)
        self.assertIn("execution_defaults", wf_entry)

    def test_list_entries_category_filter_returns_only_tasks(self) -> None:
        """list_entries(category='task') returns only task entries."""
        entries = list_entries(category="task")["entries"]
        self.assertTrue(len(entries) > 0)
        for entry in entries:
            self.assertEqual(entry["category"], "task")

    def test_list_entries_category_filter_returns_only_workflows(self) -> None:
        """list_entries(category='workflow') returns only workflow entries."""
        entries = list_entries(category="workflow")["entries"]
        self.assertTrue(len(entries) > 0)
        for entry in entries:
            self.assertEqual(entry["category"], "workflow")

    def test_list_entries_pipeline_family_filter(self) -> None:
        """list_entries(pipeline_family=...) filters to matching entries only."""
        all_entries = list_entries()["entries"]
        families = {e["pipeline_family"] for e in all_entries if e["pipeline_family"]}
        if not families:
            self.skipTest("no entries with pipeline_family set")
        family = next(iter(sorted(families)))
        filtered = list_entries(pipeline_family=family)["entries"]
        self.assertTrue(len(filtered) > 0)
        for entry in filtered:
            self.assertEqual(entry["pipeline_family"], family)
        # filtered must be a strict subset
        all_names = {e["name"] for e in all_entries}
        for entry in filtered:
            self.assertIn(entry["name"], all_names)

    def test_list_entries_excludes_non_showcased_entries(self) -> None:
        """list_entries omits registry entries that have no showcase_module."""
        from flytetest.registry import REGISTRY_ENTRIES
        non_showcased = [e.name for e in REGISTRY_ENTRIES if not e.showcase_module]
        if not non_showcased:
            self.skipTest("all registry entries have showcase_module set")
        returned_names = {e["name"] for e in list_entries()["entries"]}
        for name in non_showcased:
            self.assertNotIn(name, returned_names)

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

    def test_plan_request_matches_exact_registered_stage_name(self) -> None:
        """Free-text preview routes an exact biological stage to its registered target.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = plan_request(BRAKER_GOAL_PROMPT)

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["target"], SUPPORTED_WORKFLOW_NAME)
        self.assertEqual(payload["pipeline_family"], "annotation")
        self.assertTrue(
            any("ReferenceGenome" in limitation for limitation in payload["limitations"])
        )
        bundle_names = [bundle["name"] for bundle in payload["suggested_bundles"]]
        self.assertIn("braker3_small_eukaryote", bundle_names)

    def test_plan_request_still_reports_broader_typed_specs(self) -> None:
        """Composition-eligible prompts decline with §10 recovery channels when no bindings exist.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = plan_request("Process annotation workflow data.")

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["pipeline_family"], "annotation")
        self.assertGreater(len(payload["suggested_bundles"]), 0)
        self.assertGreater(len(payload["next_steps"]), 0)

    def test_plan_request_matches_exact_entry_name_without_parsing_paths(self) -> None:
        """Free-text preview can still resolve an exact registered entry name.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = plan_request("protein_evidence_alignment")

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["target"], SUPPORTED_PROTEIN_WORKFLOW_NAME)
        self.assertEqual(payload["pipeline_family"], "annotation")
        bundle_names = [bundle["name"] for bundle in payload["suggested_bundles"]]
        self.assertIn("protein_evidence_demo", bundle_names)

    def test_prepare_and_run_local_recipe_round_trips_saved_artifact(self) -> None:
        """Prepare a frozen recipe and execute it through explicit local handlers.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = PROTEIN_GOAL_PROMPT
        calls: list[dict[str, object]] = []

        def handler(request):  # type: ignore[no-untyped-def]
            """Capture the forwarded workflow inputs and return a stub result path."""
            calls.append(dict(request.inputs))
            return {"results_dir": "/tmp/protein_evidence_results"}

        with tempfile.TemporaryDirectory() as tmp:
            prepared = _prepare_run_recipe_impl(
                prompt,
                explicit_bindings=_protein_workflow_bindings(),
                runtime_bindings=_protein_runtime_inputs(),
                recipe_dir=Path(tmp),
            )
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
                BUSCO_GOAL_PROMPT,
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
                BUSCO_GOAL_PROMPT,
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={"cpu": 12, "memory": "48Gi", "partition": "batch", "walltime": "02:00:00"},
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
        self.assertEqual(submitted["execution_result"]["run_record"]["resource_spec"]["partition"], "batch")
        self.assertEqual(submitted["execution_result"]["run_record"]["resource_spec"]["account"], "rcc-staff")

    def test_run_slurm_recipe_updates_generic_latest_pointer_on_back_to_back_submissions(self) -> None:
        """Direct MCP Slurm submissions should refresh the shared latest-run pointer."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path)
            prepared = _prepare_run_recipe_impl(
                BUSCO_GOAL_PROMPT,
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
                PROTEIN_GOAL_PROMPT,
                explicit_bindings=_protein_workflow_bindings(),
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
                BUSCO_GOAL_PROMPT,
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
                BUSCO_GOAL_PROMPT,
                manifest_sources=(busco_result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                execution_profile="slurm",
                recipe_dir=tmp_path,
            )
            protein_recipe = _prepare_run_recipe_impl(
                PROTEIN_GOAL_PROMPT,
                explicit_bindings=_protein_workflow_bindings(),
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
                BUSCO_GOAL_PROMPT,
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={"cpu": 12, "memory": "48Gi", "partition": "batch"},
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
                BUSCO_GOAL_PROMPT,
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
                BUSCO_GOAL_PROMPT,
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
                BUSCO_GOAL_PROMPT,
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
                BUSCO_GOAL_PROMPT,
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
                BUSCO_GOAL_PROMPT,
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
                BUSCO_GOAL_PROMPT,
                manifest_sources=(result_dir,),
                runtime_bindings={
                    "busco_lineages_text": "embryophyta_odb10",
                    "busco_sif": "busco.sif",
                    "busco_cpu": 12,
                },
                resource_request={"cpu": 12, "memory": "48Gi", "partition": "short"},
                execution_profile="local",
                runtime_image={"apptainer_image": "busco.sif"},
                recipe_dir=tmp_path,
            )
            artifact = load_workflow_spec_artifact(Path(str(prepared["artifact_path"])))

        self.assertTrue(prepared["supported"])
        self.assertEqual(prepared["recipe_input_context"]["manifest_sources"], [str(result_dir)])
        self.assertEqual(
            prepared["recipe_input_context"]["resource_request"],
            {"cpu": 12, "memory": "48Gi", "partition": "short"},
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
                PROTEIN_GOAL_PROMPT,
                explicit_bindings=_protein_workflow_bindings(),
                runtime_bindings={"exonerate_sif": "data/images/exonerate_2.2.0--1.sif"},
                resource_request={
                    "account": "rcc-staff",
                    "partition": "caslake",
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
                PROTEIN_GOAL_PROMPT,
                explicit_bindings=_protein_workflow_bindings(),
                runtime_bindings={"exonerate_sif": "data/images/exonerate_2.2.0--1.sif"},
                resource_request={
                    "account": "rcc-staff",
                    "partition": "caslake",
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
                SUPPORTED_BUSCO_FIXTURE_TASK_NAME,
                runtime_bindings={
                    "proteins_fasta": "data/busco/test_data/eukaryota/genome.fna",
                    "lineage_dataset": "auto-lineage",
                    "busco_mode": "geno",
                    "busco_cpu": 2,
                    "busco_sif": "data/images/busco_v6.0.0_cv1.sif",
                },
                resource_request={
                    "cpu": 2,
                    "memory": "8Gi",
                    "partition": "caslake",
                    "account": "rcc-staff",
                    "walltime": "00:10:00",
                },
                execution_profile="slurm",
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
                BUSCO_GOAL_PROMPT,
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
        prompt = BUSCO_GOAL_PROMPT
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
                "annotation_functional_eggnog",
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
                "annotation_postprocess_agat",
                manifest_sources=(eggnog_dir,),
                runtime_bindings={"annotation_fasta_path": "data/braker3/reference/genome.fa", "agat_sif": "agat.sif"},
                recipe_dir=tmp_path,
            )
            conversion = _prepare_run_recipe_impl(
                "annotation_postprocess_agat_conversion",
                manifest_sources=(eggnog_dir,),
                runtime_bindings={"agat_sif": "agat.sif"},
                recipe_dir=tmp_path,
            )
            cleanup = _prepare_run_recipe_impl(
                "annotation_postprocess_agat_cleanup",
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
                "annotation_postprocess_agat_conversion",
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
                "annotation_functional_eggnog",
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
                "annotation_postprocess_agat_cleanup",
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
        prompt = BRAKER_GOAL_PROMPT
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
                explicit_bindings=_braker_workflow_bindings(),
                runtime_bindings=_braker_runtime_inputs(),
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
        payload = prompt_and_run("Process annotation workflow data.")

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
        prompt = PROTEIN_GOAL_PROMPT
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
                explicit_bindings=_protein_workflow_bindings(),
                runtime_bindings=_protein_runtime_inputs(),
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
        prompt = SUPPORTED_TASK_NAME
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
                runtime_bindings={
                    "genome": "data/braker3/reference/genome.fa",
                    "protein_chunk": "data/braker3/protein_data/fastas/proteins.fa",
                },
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
        """Dispatch the M18 BUSCO fixture task through the reshaped run_task.

        The reshaped ``run_task`` freezes a WorkflowSpec artifact and then
        dispatches through :class:`LocalWorkflowSpecExecutor`; the underlying
        BUSCO Python entry point is still the ``busco_assess_proteins`` task.
        """

        class _Result:
            """Small fake Flyte directory result used by the BUSCO task runner."""

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
                inputs={
                    "proteins_fasta": "data/busco/test_data/eukaryota/genome.fna",
                    "lineage_dataset": "auto-lineage",
                    "busco_cpu": 2,
                    "busco_mode": "geno",
                },
                source_prompt="BUSCO fixture smoke via reshaped run_task.",
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["execution_profile"], "local")
        self.assertEqual(payload["execution_status"], "success")
        self.assertEqual(payload["exit_status"], 0)
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

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertEqual(payload["result_summary"]["status"], "declined")

    def test_prompt_and_run_declines_missing_inputs(self) -> None:
        """Decline supported language when the prompt omits explicit runnable paths.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        prompt = PROTEIN_GOAL_PROMPT

        payload = prompt_and_run(prompt)

        self.assertFalse(payload["supported"])
        self.assertFalse(payload["execution_attempted"])
        self.assertEqual(payload["plan"]["matched_entry_names"], [SUPPORTED_PROTEIN_WORKFLOW_NAME])
        self.assertIn("ReferenceGenome", payload["plan"]["missing_requirements"][0])
        self.assertEqual(payload["result_summary"]["status"], "declined")
        self.assertEqual(payload["result_summary"]["result_code"], "declined_missing_inputs")
        self.assertEqual(payload["result_summary"]["reason_code"], "missing_required_inputs")
        self.assertEqual(payload["result_summary"]["target_name"], SUPPORTED_PROTEIN_WORKFLOW_NAME)

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
        prompt = BRAKER_GOAL_PROMPT

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
                    explicit_bindings=_braker_workflow_bindings(),
                    runtime_bindings={
                        "genome": "data/braker3/reference/genome.fa",
                        "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
                    },
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

        response = _execute_workflow_direct(
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
            response = _execute_workflow_direct(
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
            BUSCO_GOAL_PROMPT,
            manifest_sources=(result_dir,),
            runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
            resource_request={
                "cpu": 8,
                "memory": "32Gi",
                "partition": "caslake",
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
                BUSCO_GOAL_PROMPT,
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={
                    "cpu": 4,
                    "memory": "16Gi",
                    "partition": "caslake",
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
        entries_by_name = {entry["name"]: entry for entry in list_entries()["entries"]}

        busco_entry = entries_by_name[SUPPORTED_BUSCO_WORKFLOW_NAME]
        self.assertIn("slurm_resource_hints", busco_entry)
        hints = busco_entry["slurm_resource_hints"]
        self.assertIn("cpu", hints)
        self.assertIn("memory", hints)
        self.assertIn("walltime", hints)
        # partition and account are site-specific and must never appear in hints.
        self.assertNotIn("partition", hints)
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
                BUSCO_GOAL_PROMPT,
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
                BUSCO_GOAL_PROMPT,
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

        T1: Guards the eligibility gate so only supported task entries can be
        dispatched through the reshaped ad hoc execution surface.
        """
        payload = run_task("nonexistent_task")
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["target"], "nonexistent_task")
        limitation = payload["limitations"][0]
        self.assertIn("not a supported task", limitation)

    def test_run_task_declines_missing_required_inputs(self) -> None:
        """Missing required input for a known task returns a structured decline.

        T2: Validates that scalar-input validation fires before the plan is
        frozen when a required input is absent.
        """
        payload = run_task("fastqc")
        self.assertFalse(payload["supported"])
        self.assertIn("Missing required inputs", payload["limitations"][0])

    def test_run_task_declines_unknown_input_keys(self) -> None:
        """Extra input key for a known task returns a structured decline.

        T3: Prevents callers from silently passing unrecognised scalar keys
        that would otherwise be ignored and cause unexpected behaviour.
        """
        payload = run_task(
            "gffread_proteins",
            inputs={
                "annotation_gff3": "a.gff3",
                "genome_fasta": "g.fa",
                "bogus_extra_key": "should_not_be_here",
            },
        )
        self.assertFalse(payload["supported"])
        self.assertIn("Unknown scalar inputs", payload["limitations"][0])
        self.assertIn("bogus_extra_key", payload["limitations"][0])

    def test_run_task_routes_all_supported_tasks_with_synthetic_handler(self) -> None:
        """Each SUPPORTED_TASK_NAMES entry reaches the handler when inputs are valid.

        T4: Demonstrates that the reshaped run_task freezes a recipe and the
        local executor dispatches every supported task name; uses module-level
        patches so no real tools run.
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
            if task_name not in valid_inputs:
                # GATK variant-calling tasks require typed bindings (ReferenceGenome, etc.);
                # their dispatch is covered by VariantCallingMcpDispatchTests.
                continue

            reached: list[str] = []

            def _make_fake(captured_name: str) -> object:
                def _fake(**_kw: object) -> _FakeResult:
                    reached.append(captured_name)
                    return _FakeResult()
                return _fake

            module_path, fn_name = module_map[task_name]
            with patch(f"{module_path}.{fn_name}", side_effect=_make_fake(task_name)):
                payload = run_task(task_name, inputs=valid_inputs[task_name])

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
        self.assertEqual(payload["typed_bindings"], {})

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

    def test_list_available_bindings_typed_keys_follow_registry_accepted_types(self) -> None:
        """typed_bindings keys should mirror the registry entry's accepted planner types."""
        with tempfile.TemporaryDirectory() as tmp:
            payload = _list_available_bindings_impl("gffread_proteins", search_root=tmp)

        entry = get_entry("gffread_proteins")
        self.assertEqual(
            set(payload["typed_bindings"].keys()),
            set(entry.compatibility.accepted_planner_types),
        )

    def test_list_available_bindings_typed_inner_keys_follow_planner_path_fields(self) -> None:
        """typed_bindings inner keys should come from planner Path field annotations."""
        synthetic_entry = RegistryEntry(
            name="gffread_proteins",
            category="task",
            description="Synthetic compatibility entry for typed binding discovery.",
            inputs=(InterfaceField("annotation_gff3", "File", "Annotation GFF3."),),
            outputs=(InterfaceField("proteins_dir", "Dir", "Protein outputs."),),
            tags=("synthetic",),
            compatibility=RegistryCompatibilityMetadata(
                accepted_planner_types=("SyntheticBindingBundle",),
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "genome.fasta").write_text(">seq1\nACGT\n")
            (tmp_path / "annotation.gff3").write_text("##gff-version 3\n")
            run_dir = tmp_path / "prior_results"
            run_dir.mkdir()
            (run_dir / "run_manifest.json").write_text("{}")

            with patch("flytetest.server.get_entry", return_value=synthetic_entry), patch.object(
                planner_types_module,
                "SyntheticBindingBundle",
                SyntheticBindingBundle,
                create=True,
            ):
                payload = _list_available_bindings_impl("gffread_proteins", search_root=str(tmp_path))

        typed_bindings = payload["typed_bindings"]
        self.assertEqual(
            set(typed_bindings["SyntheticBindingBundle"].keys()),
            set(_path_fields_for(SyntheticBindingBundle)),
        )
        self.assertNotIn("label", typed_bindings["SyntheticBindingBundle"])

    def test_list_available_bindings_surfaces_new_planner_types_without_server_edits(self) -> None:
        """New planner types should appear in typed_bindings when the registry entry references them."""
        synthetic_entry = RegistryEntry(
            name="gffread_proteins",
            category="task",
            description="Synthetic compatibility entry for typed binding discovery.",
            inputs=(InterfaceField("annotation_gff3", "File", "Annotation GFF3."),),
            outputs=(InterfaceField("proteins_dir", "Dir", "Protein outputs."),),
            tags=("synthetic",),
            compatibility=RegistryCompatibilityMetadata(
                accepted_planner_types=("SyntheticBindingBundle",),
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fasta_path = tmp_path / "candidate.fasta"
            fasta_path.write_text(">seq1\nACGT\n")
            gff_path = tmp_path / "candidate.gff3"
            gff_path.write_text("##gff-version 3\n")
            result_dir = tmp_path / "synthetic_results"
            result_dir.mkdir()
            (result_dir / "run_manifest.json").write_text("{}")

            with patch("flytetest.server.get_entry", return_value=synthetic_entry), patch.object(
                planner_types_module,
                "SyntheticBindingBundle",
                SyntheticBindingBundle,
                create=True,
            ):
                payload = _list_available_bindings_impl("gffread_proteins", search_root=str(tmp_path))

        typed_binding = payload["typed_bindings"]["SyntheticBindingBundle"]
        self.assertIn(str(fasta_path), typed_binding["custom_fasta_path"])
        self.assertIn(str(gff_path), typed_binding["custom_gff3_path"])
        self.assertIn(str(result_dir), typed_binding["source_result_dir"])

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

    # ------------------------------------------------------------------
    # M21c — table2asn surface tests
    # ------------------------------------------------------------------

    def test_run_task_does_not_expose_table2asn_as_ad_hoc_task(self) -> None:
        """run_task declines table2asn_submission — it is workflow-surface only.

        T19: Validates that the ad hoc task surface does not expose the
        table2asn step.
        """
        result = run_task("table2asn_submission")
        self.assertFalse(result.get("supported"))

    def test_list_entries_includes_table2asn_workflow(self) -> None:
        """list_entries includes annotation_postprocess_table2asn with category=workflow.

        T20: Validates the new ShowcaseTarget entry is present.
        """
        entries = list_entries()["entries"]
        names = [e["name"] for e in entries]
        self.assertIn(SUPPORTED_TABLE2ASN_WORKFLOW_NAME, names)
        table2asn_entry = next(e for e in entries if e["name"] == SUPPORTED_TABLE2ASN_WORKFLOW_NAME)
        self.assertEqual(table2asn_entry["category"], "workflow")

    # ------------------------------------------------------------------
    # _execute_run_tool (Step 19): typed exception → PlanDecline
    # ------------------------------------------------------------------

    def _assert_decline_base(
        self,
        reply: dict,
        *,
        target: str,
        pipeline_family: str,
    ) -> None:
        self.assertIs(reply["supported"], False)
        self.assertEqual(reply["target"], target)
        self.assertEqual(reply["pipeline_family"], pipeline_family)
        self.assertIsInstance(reply["limitations"], tuple)
        self.assertIsInstance(reply["next_steps"], tuple)
        self.assertEqual(reply["suggested_bundles"], ())
        self.assertEqual(reply["suggested_prior_runs"], ())

    def test_execute_run_tool_translates_unknown_run_id(self) -> None:
        """UnknownRunIdError → PlanDecline pointing at list_available_bindings + durable index."""

        def body() -> dict[str, object]:
            raise UnknownRunIdError("missing-run", available_count=3)

        with self.assertNoLogs("flytetest.server", level="ERROR"):
            reply = _execute_run_tool(
                body,
                target_name="braker3_annotation_workflow",
                pipeline_family="annotation",
            )

        self._assert_decline_base(
            reply,
            target="braker3_annotation_workflow",
            pipeline_family="annotation",
        )
        self.assertEqual(len(reply["limitations"]), 1)
        self.assertIn("missing-run", reply["limitations"][0])
        next_steps = reply["next_steps"]
        self.assertTrue(
            any("list_available_bindings" in step for step in next_steps)
        )
        self.assertTrue(
            any("durable_asset_index.json" in step for step in next_steps)
        )

    def test_execute_run_tool_translates_unknown_output_name(self) -> None:
        """UnknownOutputNameError → PlanDecline listing the known outputs on the run."""

        def body() -> dict[str, object]:
            raise UnknownOutputNameError(
                run_id="run-123",
                output_name="bogus",
                known_outputs=("results_dir", "summary_json"),
            )

        with self.assertNoLogs("flytetest.server", level="ERROR"):
            reply = _execute_run_tool(
                body,
                target_name="busco_assess_proteins",
                pipeline_family="annotation",
            )

        self._assert_decline_base(
            reply,
            target="busco_assess_proteins",
            pipeline_family="annotation",
        )
        next_steps_blob = " | ".join(reply["next_steps"])
        self.assertIn("'run-123'", next_steps_blob)
        self.assertIn("results_dir", next_steps_blob)
        self.assertIn("summary_json", next_steps_blob)

    def test_execute_run_tool_translates_manifest_not_found(self) -> None:
        """ManifestNotFoundError → PlanDecline pointing at list_available_bindings."""

        def body() -> dict[str, object]:
            raise ManifestNotFoundError("/nope/run_manifest.json")

        with self.assertNoLogs("flytetest.server", level="ERROR"):
            reply = _execute_run_tool(
                body,
                target_name="braker3_annotation_workflow",
                pipeline_family="annotation",
            )

        self._assert_decline_base(
            reply,
            target="braker3_annotation_workflow",
            pipeline_family="annotation",
        )
        self.assertIn("/nope/run_manifest.json", reply["limitations"][0])
        next_steps_blob = " | ".join(reply["next_steps"])
        self.assertIn("list_available_bindings", next_steps_blob)
        self.assertIn("readable", next_steps_blob)

    def test_execute_run_tool_translates_binding_path_missing(self) -> None:
        """BindingPathMissingError → same decline shape as ManifestNotFoundError."""

        def body() -> dict[str, object]:
            raise BindingPathMissingError("/data/missing.fa")

        with self.assertNoLogs("flytetest.server", level="ERROR"):
            reply = _execute_run_tool(
                body,
                target_name="exonerate_align_chunk",
                pipeline_family="annotation",
            )

        self._assert_decline_base(
            reply,
            target="exonerate_align_chunk",
            pipeline_family="annotation",
        )
        self.assertIn("/data/missing.fa", reply["limitations"][0])
        next_steps_blob = " | ".join(reply["next_steps"])
        self.assertIn("list_available_bindings", next_steps_blob)

    def test_execute_run_tool_translates_binding_type_mismatch(self) -> None:
        """BindingTypeMismatchError → decline with the §7 type-compatibility wording."""

        def body() -> dict[str, object]:
            raise BindingTypeMismatchError(
                binding_key="ReadSet",
                resolved_type="VariantCallSet",
                source="$ref run_id=gatk-run-42 output_name=variant_calls",
            )

        with self.assertNoLogs("flytetest.server", level="ERROR"):
            reply = _execute_run_tool(
                body,
                target_name="braker3_annotation_workflow",
                pipeline_family="annotation",
            )

        self._assert_decline_base(
            reply,
            target="braker3_annotation_workflow",
            pipeline_family="annotation",
        )
        self.assertEqual(
            reply["limitations"],
            (
                "Binding key 'ReadSet' expected a ReadSet but source "
                "'$ref run_id=gatk-run-42 output_name=variant_calls' "
                "produces 'VariantCallSet'.",
            ),
        )
        self.assertEqual(
            reply["next_steps"],
            (
                "Pick a $ref / $manifest whose producing entry declares "
                "'ReadSet' in produced_planner_types.",
                "Call list_available_bindings(<target>) for compatible prior-run outputs.",
                "Or use the raw-path form if you explicitly want to reinterpret the file.",
            ),
        )

    def test_execute_run_tool_propagates_non_resolution_exception(self) -> None:
        """Infrastructure failures propagate AND emit one ERROR log line."""

        def body() -> dict[str, object]:
            raise OSError("disk full")

        with self.assertLogs("flytetest.server", level="ERROR") as log_ctx:
            with self.assertRaises(OSError):
                _execute_run_tool(
                    body,
                    target_name="braker3_annotation_workflow",
                    pipeline_family="annotation",
                )

        self.assertEqual(len(log_ctx.records), 1)
        record = log_ctx.records[0]
        self.assertEqual(record.levelname, "ERROR")
        message = record.getMessage()
        self.assertIn("Uncaught exception in run tool", message)
        self.assertIn("tool_name=braker3_annotation_workflow", message)
        self.assertIn("pipeline_family=annotation", message)
        self.assertIsNotNone(record.exc_info)

    # ------------------------------------------------------------------
    # Step 20: structured decline routing
    # ------------------------------------------------------------------

    def _write_durable_index(
        self,
        run_dir: Path,
        *,
        run_id: str,
        workflow_name: str,
        output_name: str,
        produced_type: str,
    ) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        asset_path = run_dir / output_name
        asset_path.mkdir(exist_ok=True)
        manifest_path = asset_path / "run_manifest.json"
        manifest_path.write_text("{}\n")
        run_record_path = run_dir / "local_run_record.json"
        run_record_path.write_text("{}\n")
        payload = {
            "schema_version": "durable-asset-index-v1",
            "run_id": run_id,
            "workflow_name": workflow_name,
            "entries": [
                {
                    "schema_version": "durable-asset-index-v1",
                    "run_id": run_id,
                    "workflow_name": workflow_name,
                    "output_name": output_name,
                    "node_name": output_name,
                    "asset_path": str(asset_path),
                    "manifest_path": str(manifest_path),
                    "created_at": "2026-04-20T00:00:00Z",
                    "run_record_path": str(run_record_path),
                    "produced_type": produced_type,
                },
            ],
        }
        (run_dir / "durable_asset_index.json").write_text(json.dumps(payload))

    def test_limitation_reply_populates_all_three_channels(self) -> None:
        """Decline for BRAKER3 with no inputs returns bundles, prior runs, and next_steps."""
        from flytetest import bundles as bundles_mod
        from flytetest.bundles import BUNDLES, ResourceBundle

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Populate bundle paths so _check_bundle_availability sees every file.
            genome = tmp_path / "genome.fa"
            rnaseq = tmp_path / "rnaseq.bam"
            proteins = tmp_path / "proteins.fa"
            sif = tmp_path / "braker3.sif"
            for p in (genome, rnaseq, proteins, sif):
                p.write_text("")

            fake = ResourceBundle(
                name="braker3_small_eukaryote_test",
                description="Test fixture BRAKER3 bundle.",
                pipeline_family="annotation",
                bindings={
                    "ReferenceGenome": {"fasta_path": str(genome)},
                    "TranscriptEvidenceSet": {"bam_path": str(rnaseq)},
                    "ProteinEvidenceSet": {"protein_fasta_path": str(proteins)},
                },
                inputs={"braker_species": "demo_species"},
                runtime_images={"braker_sif": str(sif)},
                tool_databases={},
                applies_to=("ab_initio_annotation_braker3",),
            )
            patched_bundles = {fake.name: fake}
            run_history = tmp_path / "runs"
            self._write_durable_index(
                run_history / "2026-04-20T00-00-00Z-demo",
                run_id="2026-04-20T00-00-00Z-demo",
                workflow_name="transcript_evidence_generation",
                output_name="reads",
                produced_type="TranscriptEvidenceSet",
            )

            with patch.object(bundles_mod, "BUNDLES", patched_bundles):
                decline = _limitation_reply(
                    "ab_initio_annotation_braker3",
                    "BRAKER3 requires at least one evidence input "
                    "(ReadSet or ProteinEvidenceSet).",
                    run_history_root=run_history,
                )

        self.assertFalse(decline.supported)
        self.assertEqual(decline.target, "ab_initio_annotation_braker3")
        self.assertEqual(decline.pipeline_family, "annotation")
        self.assertEqual(len(decline.suggested_bundles), 1)
        self.assertEqual(decline.suggested_bundles[0].name, "braker3_small_eukaryote_test")
        self.assertTrue(decline.suggested_bundles[0].available)
        self.assertEqual(len(decline.suggested_prior_runs), 1)
        self.assertEqual(
            decline.suggested_prior_runs[0].produced_type, "TranscriptEvidenceSet"
        )
        # next_steps references both channels plus generic recovery.
        joined = " | ".join(decline.next_steps)
        self.assertIn("braker3_small_eukaryote_test", joined)
        self.assertIn("$ref", joined)
        self.assertIn("list_available_bindings", joined)

    def test_limitation_reply_without_available_bundle_only_populates_next_steps(
        self,
    ) -> None:
        """When no bundle is available, suggested_bundles stays empty but next_steps is not."""
        from flytetest import bundles as bundles_mod
        from flytetest.bundles import BUNDLES, ResourceBundle

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake = ResourceBundle(
                name="braker3_missing_paths",
                description="Bundle whose backing data is absent.",
                pipeline_family="annotation",
                bindings={
                    "ReferenceGenome": {"fasta_path": str(tmp_path / "missing.fa")},
                },
                inputs={},
                runtime_images={},
                tool_databases={},
                applies_to=("ab_initio_annotation_braker3",),
            )
            patched_bundles = {fake.name: fake}

            with patch.object(bundles_mod, "BUNDLES", patched_bundles):
                decline = _limitation_reply(
                    "ab_initio_annotation_braker3",
                    "BRAKER3 requires at least one evidence input.",
                    run_history_root=tmp_path / "empty_runs",
                )

        self.assertEqual(decline.suggested_bundles, ())
        self.assertEqual(decline.suggested_prior_runs, ())
        self.assertGreater(len(decline.next_steps), 0)
        joined = " | ".join(decline.next_steps)
        self.assertIn("list_available_bindings", joined)

    def test_limitation_reply_prior_run_hint_contains_ref_shape(self) -> None:
        """SuggestedPriorRun.hint should echo the $ref binding grammar."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_history = tmp_path / "runs"
            self._write_durable_index(
                run_history / "run-alpha",
                run_id="run-alpha",
                workflow_name="transcript_evidence_generation",
                output_name="reads",
                produced_type="TranscriptEvidenceSet",
            )
            decline = _limitation_reply(
                "ab_initio_annotation_braker3",
                "Missing required evidence inputs.",
                run_history_root=run_history,
            )

        self.assertEqual(len(decline.suggested_prior_runs), 1)
        hint = decline.suggested_prior_runs[0].hint
        self.assertIn("$ref", hint)
        self.assertIn("'run_id': 'run-alpha'", hint)
        self.assertIn("'output_name': 'reads'", hint)
        self.assertIn("'TranscriptEvidenceSet'", hint)

    def test_unsupported_target_reply_returns_empty_recovery_channels(self) -> None:
        """Unregistered target names can't suggest bundles or prior runs."""
        decline = _unsupported_target_reply(
            "not_a_real_workflow",
            ("ab_initio_annotation_braker3", "protein_evidence_alignment"),
            kind="workflow",
        )
        self.assertFalse(decline.supported)
        self.assertEqual(decline.target, "not_a_real_workflow")
        self.assertEqual(decline.pipeline_family, "")
        self.assertEqual(decline.suggested_bundles, ())
        self.assertEqual(decline.suggested_prior_runs, ())
        joined = " | ".join(decline.next_steps)
        self.assertIn("list_entries", joined)


class RunTaskReshapeTests(TestCase):
    """Tests for the Step 21 reshape of ``run_task`` (§2 / §3b / §3g / §3i)."""

    def _valid_fastqc_call(self, **kw: object) -> dict[str, object]:
        return run_task(
            "fastqc",
            inputs={"left": "R1.fastq.gz", "right": "R2.fastq.gz"},
            source_prompt="FastQC smoke via run_task reshape.",
            **kw,
        )

    def test_bundle_spread_call_succeeds(self) -> None:
        """A bundle-style spread with typed bindings and scalar inputs succeeds."""

        class _FakeResult:
            def download_sync(self) -> str:
                return "/tmp/fake_result"

        bundle_like = {
            "bindings": {},
            "inputs": {"annotation_gff3": "ann.gff3", "genome_fasta": "g.fa"},
        }
        with patch(
            "flytetest.tasks.filtering.gffread_proteins",
            return_value=_FakeResult(),
        ):
            payload = run_task(
                "gffread_proteins",
                source_prompt="Spread bundle into run_task.",
                **bundle_like,
            )
        self.assertTrue(payload["supported"])
        self.assertEqual(payload["task_name"], "gffread_proteins")

    def test_unknown_binding_type_declines(self) -> None:
        payload = run_task(
            "fastqc",
            bindings={"NotARealType": {}},
        )
        self.assertFalse(payload["supported"])
        self.assertIn("Unknown binding types", payload["limitations"][0])

    def test_missing_scalar_declines(self) -> None:
        payload = run_task("fastqc", inputs={"left": "R1.fastq.gz"})
        self.assertFalse(payload["supported"])
        self.assertIn("Missing required inputs", payload["limitations"][0])

    def test_freeze_writes_artifact_file(self) -> None:
        """Every reshaped run_task call freezes a WorkflowSpec artifact first."""
        payload = self._valid_fastqc_call(dry_run=True)
        self.assertTrue(payload["supported"])
        artifact_path = Path(payload["artifact_path"])
        self.assertTrue(artifact_path.exists(), f"artifact missing: {artifact_path}")
        self.assertTrue(artifact_path.name.endswith(".json"))
        self.assertTrue(payload["recipe_id"].endswith("-fastqc"))

    def test_outputs_dict_keyed_by_registry_names(self) -> None:
        """Outputs reply is a named dict — no positional ``output_paths`` list."""

        class _FakeResult:
            def download_sync(self) -> str:
                return "/tmp/fake_fastqc_dir"

        with patch("flytetest.tasks.qc.fastqc", return_value=_FakeResult()):
            payload = self._valid_fastqc_call()
        self.assertTrue(payload["supported"])
        self.assertIsInstance(payload["outputs"], dict)
        self.assertIn("qc_dir", payload["outputs"])
        self.assertNotIn("output_paths", payload)

    def test_empty_source_prompt_appends_advisory(self) -> None:
        payload = run_task(
            "fastqc",
            inputs={"left": "R1.fastq.gz", "right": "R2.fastq.gz"},
            source_prompt="",
            dry_run=True,
        )
        self.assertTrue(payload["supported"])
        joined = " | ".join(payload["limitations"])
        self.assertIn("No source_prompt", joined)

    def test_dry_run_writes_artifact_but_skips_execution(self) -> None:
        """``dry_run=True`` returns a DryRunReply and writes no run_record."""
        payload = self._valid_fastqc_call(dry_run=True)
        self.assertTrue(payload["supported"])
        self.assertIn("resolved_environment", payload)
        self.assertNotIn("run_record_path", payload)
        artifact_path = Path(payload["artifact_path"])
        self.assertTrue(artifact_path.exists())
        # No run_record is produced for dry_run.
        run_record_candidates = list(artifact_path.parent.rglob("local_run_record.json"))
        recipe_id = payload["recipe_id"]
        for candidate in run_record_candidates:
            self.assertNotIn(recipe_id, str(candidate))

    def test_dry_run_artifact_chains_to_run_local_recipe(self) -> None:
        """The frozen artifact from a dry-run call can be executed unchanged."""
        from flytetest.server import _run_local_recipe_impl

        dry_reply = self._valid_fastqc_call(dry_run=True)
        artifact_path = Path(dry_reply["artifact_path"])
        bytes_before = artifact_path.read_bytes()

        class _FakeResult:
            def download_sync(self) -> str:
                return "/tmp/chained_fastqc"

        with patch("flytetest.tasks.qc.fastqc", return_value=_FakeResult()):
            chained = _run_local_recipe_impl(str(artifact_path))

        self.assertTrue(chained["supported"])
        # The artifact was not rewritten by the chained execution.
        self.assertEqual(bytes_before, artifact_path.read_bytes())

    def test_local_executor_non_zero_exit_surfaces_as_failed(self) -> None:
        """A task handler that raises surfaces as supported=True, status=failed."""

        def _boom(**_kw: object) -> object:
            raise RuntimeError("synthetic tool failure")

        with patch("flytetest.tasks.qc.fastqc", side_effect=_boom):
            payload = self._valid_fastqc_call()
        self.assertTrue(payload["supported"])
        self.assertEqual(payload["execution_status"], "failed")


class RunWorkflowReshapeTests(TestCase):
    """Tests for the Step 22 reshape of ``run_workflow`` (§3 / §3b / §3g / §3i)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp_root = Path(self._tmp.name)
        self._genome_path = tmp_root / "genome.fa"
        self._genome_path.write_text(">chr1\nACGT\n")
        self._protein_path = tmp_root / "proteins.fa"
        self._protein_path.write_text(">prot1\nMK\n")
        self._BRAKER_MINIMAL_INPUTS = {
            "genome": str(self._genome_path),
            "braker_species": "small_eukaryote",
        }
        self._PROTEIN_INPUTS = {
            "genome": str(self._genome_path),
            "protein_fastas": [str(self._protein_path)],
            "proteins_per_chunk": 250,
        }
        self._REF_BINDING = {"fasta_path": str(self._genome_path)}
        self._PROTEIN_BINDING = {
            "source_protein_fastas": [str(self._protein_path)],
        }
        self._TRANSCRIPT_BINDING = {
            "reference_genome": dict(self._REF_BINDING),
        }
        self._BRAKER_BINDINGS = {
            "ReferenceGenome": dict(self._REF_BINDING),
            "ProteinEvidenceSet": dict(self._PROTEIN_BINDING),
            "TranscriptEvidenceSet": dict(self._TRANSCRIPT_BINDING),
        }

    @staticmethod
    def _fake_direct() -> object:
        """Return a fake ``_run_workflow_direct`` returning a successful payload."""

        def _runner(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
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
                "output_paths": ["/tmp/fake_protein_results"],
                "limitations": [],
            }

        return _runner

    def _protein_bindings(self) -> dict[str, dict[str, object]]:
        return {
            "ReferenceGenome": dict(self._REF_BINDING),
            "ProteinEvidenceSet": dict(self._PROTEIN_BINDING),
        }

    # -- Bundle spread symmetry -------------------------------------------------

    def test_bundle_spread_call_succeeds(self) -> None:
        """A bundle-shaped dict spreads into run_workflow exactly like run_task."""
        bundle_like = {
            "bindings": dict(self._BRAKER_BINDINGS),
            "inputs": {
                **self._BRAKER_MINIMAL_INPUTS,
                "protein_fasta_path": str(self._protein_path),
            },
        }
        payload = run_workflow(
            SUPPORTED_WORKFLOW_NAME,
            source_prompt="Bundle spread into run_workflow.",
            dry_run=True,
            **bundle_like,
        )
        self.assertTrue(payload["supported"], msg=payload.get("limitations"))
        self.assertEqual(payload["workflow_name"], SUPPORTED_WORKFLOW_NAME)

    # -- BRAKER3 evidence guard -------------------------------------------------

    def test_braker3_accepts_typed_protein_evidence_binding(self) -> None:
        payload = run_workflow(
            SUPPORTED_WORKFLOW_NAME,
            bindings=dict(self._BRAKER_BINDINGS),
            inputs=self._BRAKER_MINIMAL_INPUTS,
            source_prompt="BRAKER3 via typed ProteinEvidenceSet binding.",
            dry_run=True,
        )
        self.assertTrue(payload["supported"], msg=payload.get("limitations"))

    def test_braker3_accepts_legacy_scalar_protein_fasta_path(self) -> None:
        payload = run_workflow(
            SUPPORTED_WORKFLOW_NAME,
            bindings=dict(self._BRAKER_BINDINGS),
            inputs={
                **self._BRAKER_MINIMAL_INPUTS,
                "protein_fasta_path": str(self._protein_path),
            },
            source_prompt="BRAKER3 via legacy scalar protein_fasta_path.",
            dry_run=True,
        )
        self.assertTrue(payload["supported"], msg=payload.get("limitations"))

    def test_braker3_without_evidence_declines(self) -> None:
        payload = run_workflow(
            SUPPORTED_WORKFLOW_NAME,
            inputs=self._BRAKER_MINIMAL_INPUTS,
            source_prompt="BRAKER3 with no evidence.",
        )
        self.assertFalse(payload["supported"])
        self.assertIn(
            "BRAKER3 requires at least one evidence input",
            payload["limitations"][0],
        )

    # -- Validation declines ----------------------------------------------------

    def test_unknown_binding_type_declines(self) -> None:
        payload = run_workflow(
            SUPPORTED_PROTEIN_WORKFLOW_NAME,
            bindings={"NotARealType": {}},
            inputs=self._PROTEIN_INPUTS,
        )
        self.assertFalse(payload["supported"])
        self.assertIn("Unknown binding types", payload["limitations"][0])

    # -- Freeze + named outputs + advisories ------------------------------------

    def test_freeze_writes_artifact_file(self) -> None:
        payload = run_workflow(
            SUPPORTED_PROTEIN_WORKFLOW_NAME,
            bindings=self._protein_bindings(),
            inputs=self._PROTEIN_INPUTS,
            source_prompt="Protein evidence dry-run freeze check.",
            dry_run=True,
        )
        self.assertTrue(payload["supported"], msg=payload.get("limitations"))
        artifact_path = Path(payload["artifact_path"])
        self.assertTrue(artifact_path.exists(), f"artifact missing: {artifact_path}")
        self.assertTrue(
            payload["recipe_id"].endswith(f"-{SUPPORTED_PROTEIN_WORKFLOW_NAME}")
        )

    def test_outputs_dict_keyed_by_registry_names(self) -> None:
        with patch(
            "flytetest.server._run_workflow_direct",
            side_effect=self._fake_direct(),
        ):
            payload = run_workflow(
                SUPPORTED_PROTEIN_WORKFLOW_NAME,
                bindings=self._protein_bindings(),
                inputs=self._PROTEIN_INPUTS,
                source_prompt="Protein evidence named-outputs check.",
            )
        self.assertTrue(payload["supported"], msg=payload.get("limitations"))
        self.assertIsInstance(payload["outputs"], dict)
        self.assertIn("results_dir", payload["outputs"])
        self.assertNotIn("output_paths", payload)

    def test_empty_source_prompt_appends_advisory(self) -> None:
        payload = run_workflow(
            SUPPORTED_PROTEIN_WORKFLOW_NAME,
            bindings=self._protein_bindings(),
            inputs=self._PROTEIN_INPUTS,
            source_prompt="",
            dry_run=True,
        )
        self.assertTrue(payload["supported"])
        joined = " | ".join(payload["limitations"])
        self.assertIn("No source_prompt", joined)

    # -- dry_run + chained execution --------------------------------------------

    def test_dry_run_writes_artifact_but_skips_execution(self) -> None:
        payload = run_workflow(
            SUPPORTED_PROTEIN_WORKFLOW_NAME,
            bindings=self._protein_bindings(),
            inputs=self._PROTEIN_INPUTS,
            source_prompt="dry-run skip-exec check.",
            dry_run=True,
        )
        self.assertTrue(payload["supported"])
        self.assertIn("resolved_environment", payload)
        self.assertNotIn("run_record_path", payload)
        artifact_path = Path(payload["artifact_path"])
        self.assertTrue(artifact_path.exists())
        recipe_id = payload["recipe_id"]
        for candidate in artifact_path.parent.rglob("local_run_record.json"):
            self.assertNotIn(recipe_id, str(candidate))

    def test_dry_run_artifact_chains_to_run_local_recipe(self) -> None:
        """Frozen artifact from a dry-run call executes unchanged through run_local_recipe."""
        from flytetest.server import _run_local_recipe_impl

        dry_reply = run_workflow(
            SUPPORTED_PROTEIN_WORKFLOW_NAME,
            bindings=self._protein_bindings(),
            inputs=self._PROTEIN_INPUTS,
            source_prompt="Chained dry-run then run_local_recipe.",
            dry_run=True,
        )
        self.assertTrue(dry_reply["supported"], msg=dry_reply.get("limitations"))
        artifact_path = Path(dry_reply["artifact_path"])
        bytes_before = artifact_path.read_bytes()

        with patch(
            "flytetest.server._run_workflow_direct",
            side_effect=self._fake_direct(),
        ):
            chained = _run_local_recipe_impl(str(artifact_path))

        self.assertTrue(chained["supported"])
        self.assertEqual(bytes_before, artifact_path.read_bytes())

    # -- Local non-zero exit ----------------------------------------------------

    def test_local_executor_non_zero_exit_surfaces_as_failed(self) -> None:
        def _boom(workflow_name: str, inputs: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("synthetic workflow failure")

        with patch("flytetest.server._run_workflow_direct", side_effect=_boom):
            payload = run_workflow(
                SUPPORTED_PROTEIN_WORKFLOW_NAME,
                bindings=self._protein_bindings(),
                inputs=self._PROTEIN_INPUTS,
                source_prompt="Workflow local failure.",
            )
        self.assertTrue(payload["supported"])
        self.assertEqual(payload["execution_status"], "failed")


class StagingPreflightServerTests(TestCase):
    """Step 23: server-level staging preflight — replay after staging failure.

    These tests keep the current contract explicit and document the pre-submission
    staging gate as observed through the server's run_slurm_recipe surface.
"""

    def test_staging_failure_leaves_artifact_on_disk_for_replay(self) -> None:
        """After a staging-failure rejection the frozen artifact must stay on
        disk so the scientist can fix the missing path and replay via
        run_slurm_recipe(artifact_path=...).

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        sbatch_calls: list[list[str]] = []

        def fake_sbatch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            sbatch_calls.append(list(args))
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="Submitted batch job 88001\n", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            missing_db = tmp_path / "missing_busco_db"
            valid_sif = tmp_path / "busco.sif"
            valid_sif.write_bytes(b"fake-sif")

            # Build a Slurm artifact pointing at a non-existent tool_database.
            # BUSCO requires manifest_sources (result bundle) and runtime_bindings.
            result_dir = tmp_path / "repeat_filter_results_staging"
            result_dir.mkdir()
            (result_dir / "run_manifest.json").write_text(
                json.dumps({
                    "workflow": "annotation_repeat_filtering",
                    "assumptions": [],
                    "inputs": {"reference_genome": "data/braker3/reference/genome.fa"},
                    "outputs": {
                        "all_repeats_removed_gff3": str(result_dir / "all_repeats_removed.gff3"),
                        "final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                    },
                }, indent=2)
            )
            typed_plan = plan_typed_request(
                biological_goal="annotation_qc_busco",
                target_name="annotation_qc_busco",
                source_prompt="staging replay test",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={"cpu": 4, "memory": "16Gi", "partition": "batch", "walltime": "01:00:00"},
                execution_profile="slurm",
                # Override both registry defaults: bad db path, valid sif path.
                runtime_images={"busco_sif": str(valid_sif)},
                tool_databases={"busco_lineage_dir": str(missing_db)},
            )
            artifact = artifact_from_typed_plan(typed_plan, created_at="2026-04-21T00:00:00Z")
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")

            # First submission: staging fails because the path doesn't exist.
            # Provide shared_fs_roots to trigger the staging gate.
            from flytetest.spec_executor import SlurmWorkflowSpecExecutor as _Exec
            staged_result = _Exec(
                run_root=tmp_path / "runs",
                repo_root=tmp_path,
                sbatch_runner=fake_sbatch,
                command_available=lambda cmd: cmd == "sbatch",
            ).submit(artifact_path, shared_fs_roots=(tmp_path,))

            self.assertFalse(staged_result.supported)
            self.assertEqual(sbatch_calls, [], "sbatch must not be called when staging fails")
            self.assertIn("busco_lineage_dir", str(staged_result.limitations))
            # Frozen artifact must still exist so the scientist can replay.
            self.assertTrue(artifact_path.exists(), "artifact must remain on disk after staging failure")

            # Fix the path by creating the missing directory.
            missing_db.mkdir()

            # Replay via run_slurm_recipe (no shared_fs_roots → staging skipped → sbatch called).
            result_2 = _run_slurm_recipe_impl(
                str(artifact_path),
                run_dir=tmp_path / "runs2",
                sbatch_runner=fake_sbatch,
                command_available=lambda cmd: cmd == "sbatch",
            )

        self.assertTrue(result_2["supported"])
        self.assertEqual(len(sbatch_calls), 1, "sbatch must be called exactly once after the path is fixed")


class ValidateRunRecipeTests(TestCase):
    """Step 24: validate_run_recipe MCP tool (inspect-before-execute).

    These tests keep the current contract explicit and guard the documented
    behavior against regression.
"""

    def _build_artifact(
        self,
        tmp_path: Path,
        *,
        runtime_images: dict[str, str],
        tool_databases: dict[str, str],
    ) -> "SavedWorkflowSpecArtifact":
        """Build a minimal BUSCO Slurm artifact with controlled staging paths."""
        result_dir = tmp_path / "repeat_filter_results_validate"
        result_dir.mkdir(exist_ok=True)
        # Create the output files so binding validation (path-existence check) passes.
        gff3_path = result_dir / "all_repeats_removed.gff3"
        proteins_path = result_dir / "all_repeats_removed.proteins.fa"
        gff3_path.write_text("##gff-version 3\n")
        proteins_path.write_text(">seq\nACGT\n")
        (result_dir / "run_manifest.json").write_text(
            json.dumps({
                "workflow": "annotation_repeat_filtering",
                "assumptions": [],
                "inputs": {"reference_genome": "data/braker3/reference/genome.fa"},
                "outputs": {
                    "all_repeats_removed_gff3": str(gff3_path),
                    "final_proteins_fasta": str(proteins_path),
                },
            }, indent=2)
        )
        typed_plan = plan_typed_request(
            biological_goal="annotation_qc_busco",
            target_name="annotation_qc_busco",
            source_prompt="validate_run_recipe test",
            manifest_sources=(result_dir,),
            runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
            resource_request={"cpu": 4, "memory": "16Gi", "partition": "batch", "walltime": "01:00:00"},
            execution_profile="slurm",
            runtime_images=runtime_images,
            tool_databases=tool_databases,
        )
        return artifact_from_typed_plan(typed_plan, created_at="2026-04-21T00:00:00Z")

    def test_happy_path_returns_supported_true_with_empty_findings(self) -> None:
        """When all bindings resolve and staging is clean, validate returns supported=True.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sif_path = tmp_path / "busco.sif"
            sif_path.write_bytes(b"fake-sif")
            db_path = tmp_path / "busco_db"
            db_path.mkdir()
            artifact = self._build_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(sif_path)},
                tool_databases={"busco_lineage_dir": str(db_path)},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = validate_run_recipe(
                str(artifact_path),
                execution_profile="slurm",
                shared_fs_roots=[str(tmp_path)],
            )

        self.assertTrue(result["supported"], f"unexpected findings: {result['findings']}")
        self.assertEqual(len(result["findings"]), 0, "happy path must produce no findings")
        self.assertEqual(result["execution_profile"], "slurm")
        self.assertEqual(result["recipe_id"], artifact_path.stem)

    def test_ref_to_unknown_run_id_returns_binding_finding(self) -> None:
        """A $ref binding pointing at a non-existent run_id produces a binding finding.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sif_path = tmp_path / "busco.sif"
            sif_path.write_bytes(b"fake-sif")
            db_path = tmp_path / "busco_db"
            db_path.mkdir()
            artifact = self._build_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(sif_path)},
                tool_databases={"busco_lineage_dir": str(db_path)},
            )
            # Inject a $ref binding that references an unknown run_id.
            artifact_with_ref = replace(
                artifact,
                binding_plan=replace(
                    artifact.binding_plan,
                    explicit_user_bindings={
                        **dict(artifact.binding_plan.explicit_user_bindings),
                        "ReferenceGenome": {"$ref": {"run_id": "nonexistent_run_xyz", "output_name": "reference"}},
                    },
                ),
            )
            artifact_path = save_workflow_spec_artifact(artifact_with_ref, tmp_path / "recipe.json")
            result = validate_run_recipe(
                str(artifact_path),
                execution_profile="local",
            )

        self.assertFalse(result["supported"])
        binding_findings = [f for f in result["findings"] if f["kind"] == "binding"]
        self.assertEqual(len(binding_findings), 1)
        self.assertEqual(binding_findings[0]["key"], "ReferenceGenome")
        self.assertIn("nonexistent_run_xyz", binding_findings[0]["reason"])

    def test_unreachable_container_returns_container_finding(self) -> None:
        """An artifact with a non-existent container image path returns a container finding.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "busco_db"
            db_path.mkdir()
            artifact = self._build_artifact(
                tmp_path,
                runtime_images={"busco_sif": "/nonexistent/path/busco.sif"},
                tool_databases={"busco_lineage_dir": str(db_path)},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = validate_run_recipe(
                str(artifact_path),
                execution_profile="local",
            )

        self.assertFalse(result["supported"])
        container_findings = [f for f in result["findings"] if f["kind"] == "container"]
        self.assertEqual(len(container_findings), 1)
        self.assertEqual(container_findings[0]["key"], "busco_sif")
        self.assertIn("/nonexistent/path/busco.sif", container_findings[0]["path"])

    def test_missing_tool_database_returns_tool_database_finding(self) -> None:
        """An artifact with a non-existent tool_database path returns a tool_database finding.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sif_path = tmp_path / "busco.sif"
            sif_path.write_bytes(b"fake-sif")
            artifact = self._build_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(sif_path)},
                tool_databases={"busco_lineage_dir": str(tmp_path / "missing_db")},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result = validate_run_recipe(
                str(artifact_path),
                execution_profile="local",
            )

        self.assertFalse(result["supported"])
        db_findings = [f for f in result["findings"] if f["kind"] == "tool_database"]
        self.assertEqual(len(db_findings), 1)
        self.assertEqual(db_findings[0]["key"], "busco_lineage_dir")

    def test_idempotent_two_calls_return_identical_findings(self) -> None:
        """Calling validate_run_recipe twice on the same artifact yields identical findings.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sif_path = tmp_path / "busco.sif"
            sif_path.write_bytes(b"fake-sif")
            artifact = self._build_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(sif_path)},
                tool_databases={"busco_lineage_dir": str(tmp_path / "missing_db")},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            result_1 = validate_run_recipe(str(artifact_path), execution_profile="local")
            result_2 = validate_run_recipe(str(artifact_path), execution_profile="local")

        self.assertEqual(result_1["findings"], result_2["findings"], "repeated calls must be idempotent")

    def test_local_profile_no_shared_fs_roots_flags_missing_but_not_shared_fs(self) -> None:
        """local profile without shared_fs_roots flags missing paths but not on-shared-fs issues.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sif_path = tmp_path / "busco.sif"
            sif_path.write_bytes(b"fake-sif")
            # tool_database does not exist — should produce not_found
            artifact = self._build_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(sif_path)},
                tool_databases={"busco_lineage_dir": str(tmp_path / "missing_db")},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            # No shared_fs_roots — local profile
            result = validate_run_recipe(str(artifact_path), execution_profile="local")

        self.assertFalse(result["supported"])
        reasons = [f["reason"] for f in result["findings"]]
        # Missing path IS flagged
        self.assertIn("not_found", reasons)
        # Shared-FS membership NOT flagged
        self.assertNotIn("not_on_shared_fs", reasons)

    def test_slurm_profile_empty_shared_fs_roots_flags_staged_paths(self) -> None:
        """slurm profile with empty shared_fs_roots flags every staged path (no false negatives).

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sif_path = tmp_path / "busco.sif"
            sif_path.write_bytes(b"fake-sif")
            db_path = tmp_path / "busco_db"
            db_path.mkdir()
            # Both paths exist on local FS but are NOT on any declared shared root.
            artifact = self._build_artifact(
                tmp_path,
                runtime_images={"busco_sif": str(sif_path)},
                tool_databases={"busco_lineage_dir": str(db_path)},
            )
            artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "recipe.json")
            # Explicit empty list — no shared roots declared for slurm.
            result = validate_run_recipe(
                str(artifact_path),
                execution_profile="slurm",
                shared_fs_roots=[],
            )

        self.assertFalse(result["supported"])
        reasons = [f["reason"] for f in result["findings"]]
        self.assertIn("not_on_shared_fs", reasons, "existing staged paths must be flagged when no roots declared")
        # Both container and tool_database should be flagged
        kinds = {f["kind"] for f in result["findings"]}
        self.assertIn("container", kinds)
        self.assertIn("tool_database", kinds)


# ---------------------------------------------------------------------------
# Step 25 — Bundle MCP tools
# ---------------------------------------------------------------------------


class ListBundlesTests(TestCase):
    """Tests for the list_bundles MCP tool."""

    def test_returns_all_bundles_with_expected_keys(self) -> None:
        """list_bundles() with no filter returns every seeded bundle."""
        from flytetest.bundles import BUNDLES
        results = list_bundles()
        self.assertEqual(len(results), len(BUNDLES))
        for entry in results:
            for key in ("name", "description", "pipeline_family", "applies_to",
                        "binding_types", "available", "reasons"):
                self.assertIn(key, entry, f"key {key!r} missing from bundle entry")

    def test_filter_by_pipeline_family(self) -> None:
        """list_bundles(pipeline_family='annotation') returns only annotation bundles."""
        from flytetest.bundles import BUNDLES
        results = list_bundles(pipeline_family="annotation")
        self.assertGreater(len(results), 0)
        for entry in results:
            self.assertEqual(entry["pipeline_family"], "annotation")
        expected_count = sum(1 for b in BUNDLES.values() if b.pipeline_family == "annotation")
        self.assertEqual(len(results), expected_count)

    def test_unknown_family_returns_empty_list(self) -> None:
        """list_bundles(pipeline_family='nonexistent') returns an empty list."""
        results = list_bundles(pipeline_family="nonexistent_family_xyz")
        self.assertEqual(results, [])


class LoadBundleTests(TestCase):
    """Tests for the load_bundle MCP tool."""

    def test_happy_path_m18_busco_demo(self) -> None:
        """load_bundle for a known bundle with all paths present returns expected keys."""
        import tempfile
        from unittest.mock import patch
        from flytetest import bundles as bundles_mod
        from flytetest.bundles import ResourceBundle

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sif = tmp_path / "busco.sif"
            sif.write_bytes(b"fake")
            db = tmp_path / "busco_db"
            db.mkdir()
            fasta = tmp_path / "proteins.fa"
            fasta.write_bytes(b"fake")

            fake = ResourceBundle(
                name="m18_busco_demo",
                description="BUSCO demo.",
                pipeline_family="annotation",
                bindings={"QualityAssessmentTarget": {"fasta_path": str(fasta)}},
                inputs={"lineage_dataset": "eukaryota_odb10"},
                runtime_images={"busco_sif": str(sif)},
                tool_databases={"busco_lineage_dir": str(db)},
                applies_to=("annotation_qc_busco",),
            )
            with patch.object(bundles_mod, "BUNDLES", {"m18_busco_demo": fake}):
                result = load_bundle("m18_busco_demo")

        self.assertTrue(result.get("supported"), f"Expected supported=True, got: {result}")
        for key in ("bindings", "inputs", "runtime_images", "tool_databases",
                    "description", "pipeline_family"):
            self.assertIn(key, result, f"key {key!r} missing from load_bundle result")

    def test_known_but_unavailable_bundle_returns_supported_false(self) -> None:
        """load_bundle for a bundle with missing paths returns supported=False with reasons."""
        import tempfile
        from unittest.mock import patch
        from flytetest import bundles as bundles_mod
        from flytetest.bundles import ResourceBundle

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake = ResourceBundle(
                name="m18_busco_demo",
                description="BUSCO demo.",
                pipeline_family="annotation",
                bindings={"QualityAssessmentTarget": {"fasta_path": str(tmp_path / "missing.fa")}},
                inputs={},
                runtime_images={},
                tool_databases={},
                applies_to=("annotation_qc_busco",),
            )
            with patch.object(bundles_mod, "BUNDLES", {"m18_busco_demo": fake}):
                result = load_bundle("m18_busco_demo")

        self.assertFalse(result.get("supported"), f"Expected supported=False, got: {result}")
        self.assertIn("reasons", result)
        self.assertGreater(len(result["reasons"]), 0)

    def test_unknown_bundle_returns_structured_decline_not_key_error(self) -> None:
        """load_bundle('nonexistent') returns a structured decline, not a raw KeyError."""
        result = load_bundle("nonexistent_bundle_xyz")
        self.assertFalse(result.get("supported"), f"Expected supported=False, got: {result}")
        self.assertIn("next_steps", result)
        joined = " ".join(result["next_steps"])
        self.assertIn("list_bundles", joined)

    def test_experiment_loop_smoke(self) -> None:
        """Spreading load_bundle output into run_workflow (dry_run=True) succeeds."""
        import tempfile
        from unittest.mock import patch
        from flytetest import bundles as bundles_mod
        from flytetest.bundles import ResourceBundle

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            genome = tmp_path / "genome.fa"
            proteins = tmp_path / "proteins.fa"
            sif = tmp_path / "braker3.sif"
            for p in (genome, proteins, sif):
                p.write_bytes(b"fake")

            fake = ResourceBundle(
                name="braker3_small_eukaryote",
                description="Test BRAKER3 bundle.",
                pipeline_family="annotation",
                bindings={
                    "ReferenceGenome": {"fasta_path": str(genome)},
                    # TranscriptEvidenceSet requires reference_genome (not bam_path)
                    "TranscriptEvidenceSet": {"reference_genome": {"fasta_path": str(genome)}},
                    "ProteinEvidenceSet": {
                        "reference_genome": {"fasta_path": str(genome)},
                        "protein_fasta_path": str(proteins),
                    },
                },
                inputs={"braker_species": "demo_species"},
                runtime_images={"braker_sif": str(sif)},
                tool_databases={},
                applies_to=("ab_initio_annotation_braker3",),
            )
            with patch.object(bundles_mod, "BUNDLES", {"braker3_small_eukaryote": fake}):
                bundle = load_bundle("braker3_small_eukaryote")

            self.assertTrue(bundle.get("supported"), f"load_bundle failed: {bundle}")
            # run_workflow still requires the legacy scalar 'genome' input even when
            # a ReferenceGenome typed binding is present (the scalar check runs before
            # planner resolution).  Merge it in alongside the bundle inputs.
            merged_inputs = {**bundle["inputs"], "genome": str(genome)}
            result = run_workflow(
                "ab_initio_annotation_braker3",
                bindings=bundle["bindings"],
                inputs=merged_inputs,
                runtime_images=bundle["runtime_images"],
                tool_databases=bundle["tool_databases"],
                source_prompt="smoke test via load_bundle",
                dry_run=True,
            )
        self.assertTrue(result.get("supported", True), f"run_workflow declined: {result}")
        self.assertIn("recipe_id", result)


class VariantCallingMcpDispatchTests(TestCase):
    """Milestone H: verify run_workflow/run_task dispatch recognizes GATK targets (dry_run)."""

    def test_run_workflow_dispatches_germline_short_variant_discovery(self) -> None:
        """run_workflow recognizes germline_short_variant_discovery as a registered workflow target."""
        result = run_workflow(
            "germline_short_variant_discovery",
            bindings={},
            inputs={
                "sample_ids": ["demo"],
                "intervals": ["chr20"],
            },
            dry_run=True,
        )
        self.assertEqual(
            result.get("target"), "germline_short_variant_discovery",
            f"germline_short_variant_discovery not recognized as workflow target: {result}",
        )
        self.assertEqual(
            result.get("pipeline_family"), "variant_calling",
            f"germline_short_variant_discovery not in variant_calling family: {result}",
        )

    def test_run_task_dispatches_create_sequence_dictionary(self) -> None:
        """run_task recognizes create_sequence_dictionary as a registered GATK task."""
        result = run_task(
            "create_sequence_dictionary",
            bindings={},
            inputs={"gatk_sif": ""},
            dry_run=True,
        )
        self.assertIn(
            result.get("candidate_outcome"),
            ("registered_task", "selected"),
            f"create_sequence_dictionary not dispatched as registered task: {result.get('candidate_outcome')}",
        )
