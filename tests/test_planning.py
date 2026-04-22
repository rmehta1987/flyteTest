"""Planner contract checks for the narrow FLyteTest MCP showcase.

    These tests freeze the current planner subset while the broader `realtime`
    architecture lands behind compatibility seams.
"""

from __future__ import annotations

from dataclasses import replace
import json
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

from flytetest.mcp_replies import PlanDecline, PlanSuccess
from flytetest.planner_types import (
    AnnotationEvidenceSet,
    ConsensusAnnotation,
    ProteinEvidenceSet,
    QualityAssessmentTarget,
    ReadSet,
    ReferenceGenome,
    TranscriptEvidenceSet,
)
from flytetest.planning import (
    plan_request,
    plan_request_reshape,
    plan_typed_request,
    split_entry_inputs,
    supported_entry_parameters,
)
from flytetest.registry import get_entry


def _repeat_filter_manifest_dir(base_dir: Path, name: str) -> Path:
    """Create one synthetic repeat-filter manifest directory for BUSCO planning tests.

    Args:
        base_dir: Temporary root used to stage the manifest directory.
        name: Directory name that identifies this synthetic bundle.

    Returns:
        The staged repeat-filter result directory.
    """
    result_dir = base_dir / name
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


def _eggnog_manifest_dir(base_dir: Path, name: str) -> Path:
    """Create one synthetic EggNOG manifest directory for AGAT planning tests.

    Args:
        base_dir: Temporary root used to stage the manifest directory.
        name: Directory name that identifies this synthetic bundle.

    Returns:
        The staged EggNOG result directory.
    """
    result_dir = base_dir / name
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


def _agat_conversion_manifest_dir(base_dir: Path, name: str) -> Path:
    """Create one synthetic AGAT conversion manifest directory for cleanup planning tests.

    Args:
        base_dir: Temporary root used to stage the manifest directory.
        name: Directory name that identifies this synthetic bundle.

    Returns:
        The staged AGAT conversion result directory.
    """
    result_dir = base_dir / name
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


def _patched_planning_entry(entry_name: str, execution_defaults: dict[str, object]):
    """Return a patcher that swaps one planning entry for a customized copy."""
    original_entry = get_entry(entry_name)
    patched_entry = replace(
        original_entry,
        compatibility=replace(
            original_entry.compatibility,
            execution_defaults=execution_defaults,
        ),
    )

    def _patched_get_entry(name: str):
        if name == entry_name:
            return patched_entry
        return get_entry(name)

    return patch("flytetest.planning.get_entry", side_effect=_patched_get_entry)


def _typed_plan(
    target_name: str,
    *,
    biological_goal: str | None = None,
    source_prompt: str = "",
    **kwargs: object,
) -> dict[str, object]:
    """Build one structured typed plan in the Step 16 shape."""
    if biological_goal is None:
        try:
            entry = get_entry(target_name)
        except KeyError:
            biological_goal = target_name
        else:
            biological_goal = entry.compatibility.biological_stage or target_name
    return plan_typed_request(
        biological_goal=biological_goal,
        target_name=target_name,
        source_prompt=source_prompt,
        **kwargs,
    )


class PlanningTests(TestCase):
    """Compatibility checks for the current planner-facing showcase behavior.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_typed_plan_resolves_direct_registered_workflow(self) -> None:
        """Select a registered workflow through planner types and resolver bindings.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        protein_evidence = ProteinEvidenceSet(
            reference_genome=reference_genome,
            source_protein_fastas=(Path("data/braker3/protein_data/fastas/proteins.fa"),),
        )

        payload = _typed_plan(
            "protein_evidence_alignment",
            explicit_bindings={
                "ReferenceGenome": reference_genome,
                "ProteinEvidenceSet": protein_evidence,
            },
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "protein_evidence_alignment")
        self.assertEqual(payload["matched_entry_names"], ["protein_evidence_alignment"])
        self.assertEqual(payload["required_planner_types"], ["ReferenceGenome", "ProteinEvidenceSet"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["workflow_spec"]["replay_metadata"]["selection_mode"], "registered_workflow")
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_builds_registered_stage_composition(self) -> None:
        """Represent an EVM consensus request as reviewed registered workflow stages.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        transcript_evidence = TranscriptEvidenceSet(
            reference_genome=reference_genome,
            pasa_assemblies_gff3_path=Path("results/pasa/pasa_assemblies.gff3"),
        )
        protein_evidence = ProteinEvidenceSet(
            reference_genome=reference_genome,
            evm_ready_gff3_path=Path("results/protein/proteins.gff3"),
        )
        annotation_evidence = AnnotationEvidenceSet(
            reference_genome=reference_genome,
            transcript_evidence=transcript_evidence,
            protein_evidence=protein_evidence,
            ab_initio_predictions_gff3_path=Path("results/braker/braker.gff3"),
        )

        payload = _typed_plan(
            "consensus_annotation_from_registered_stages",
            explicit_bindings={
                "TranscriptEvidenceSet": transcript_evidence,
                "ProteinEvidenceSet": protein_evidence,
                "AnnotationEvidenceSet": annotation_evidence,
            },
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_stage_composition")
        self.assertEqual(
            payload["matched_entry_names"],
            ["consensus_annotation_evm_prep", "consensus_annotation_evm"],
        )
        self.assertEqual(payload["workflow_spec"]["replay_metadata"]["selection_mode"], "registered_stage_composition")
        self.assertEqual([node["reference_name"] for node in payload["workflow_spec"]["nodes"]], payload["matched_entry_names"])
        self.assertEqual(payload["workflow_spec"]["edges"][0]["target_input"], "evm_prep_results")

    def test_typed_plan_builds_generated_workflow_spec_preview(self) -> None:
        """Represent a not-yet-checked-in multi-stage request as a metadata-only spec preview.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        consensus_annotation = ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=Path("results/evm/evm.out.gff3"),
        )

        payload = _typed_plan(
            "repeat_filter_then_busco_qc",
            explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "generated_workflow_spec")
        self.assertEqual(payload["candidate_outcome"], "generated_workflow_spec")
        self.assertEqual(payload["missing_requirements"], [])
        self.assertIn("repeatmasker_out", payload["runtime_requirements"][0])
        self.assertIn("repeatmasker_out", payload["binding_plan"]["unresolved_requirements"][0])
        self.assertEqual(
            payload["workflow_spec"]["generated_entity_record"]["generated_entity_id"],
            "generated::repeat_filter_then_busco_qc::preview",
        )
        self.assertEqual(payload["binding_plan"]["target_kind"], "generated_workflow")

    def test_typed_plan_accepts_serialized_quality_assessment_target_binding(self) -> None:
        """Resolve BUSCO from an explicit serialized quality target plus runtime bindings.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        target = QualityAssessmentTarget(
            source_result_dir=Path("results/repeat_filter_20260407_120000"),
            source_manifest_path=Path("results/repeat_filter_20260407_120000/run_manifest.json"),
            annotation_gff3_path=Path("results/repeat_filter_20260407_120000/all_repeats_removed.gff3"),
            proteins_fasta_path=Path("results/repeat_filter_20260407_120000/all_repeats_removed.proteins.fa"),
        )

        payload = _typed_plan(
            "annotation_qc_busco",
            explicit_bindings={"QualityAssessmentTarget": target.to_dict()},
            runtime_bindings={
                "busco_lineages_text": "embryophyta_odb10",
                "busco_sif": "busco.sif",
                "busco_cpu": 12,
            },
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_qc_busco")
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(
            payload["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(target.source_result_dir),
        )
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {
                "busco_lineages_text": "embryophyta_odb10",
                "busco_sif": "busco.sif",
                "busco_cpu": 12,
            },
        )

    def test_typed_plan_resolves_busco_from_manifest_sources(self) -> None:
        """Resolve BUSCO from a repeat-filter manifest source without guessing.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")

            payload = _typed_plan(
                "annotation_qc_busco",
                manifest_sources=(result_dir,),
                runtime_bindings={
                    "busco_lineages_text": "embryophyta_odb10",
                    "busco_cpu": 12,
                },
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["biological_goal"], "annotation_qc_busco")
        self.assertEqual(
            payload["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(result_dir),
        )
        self.assertEqual(
            payload["binding_plan"]["manifest_derived_paths"]["QualityAssessmentTarget"]["label"],
            str(result_dir / "run_manifest.json"),
        )
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {
                "busco_lineages_text": "embryophyta_odb10",
                "busco_cpu": 12,
            },
        )

    def test_typed_plan_freezes_resource_policy_from_prompt_and_caller_inputs(self) -> None:
        """Persist structured resource and runtime-image policy in the binding plan.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")

            payload = _typed_plan(
                "annotation_qc_busco",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={"cpu": "12", "memory": "64Gi", "partition": "short", "walltime": "02:00:00"},
                execution_profile="local",
                runtime_image={"apptainer_image": "busco.sif"},
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["execution_profile"], "local")
        self.assertEqual(payload["resource_spec"]["cpu"], "12")
        self.assertEqual(payload["resource_spec"]["memory"], "64Gi")
        self.assertEqual(payload["resource_spec"]["partition"], "short")
        self.assertEqual(payload["resource_spec"]["walltime"], "02:00:00")
        self.assertEqual(payload["runtime_image"]["apptainer_image"], "busco.sif")
        self.assertEqual(payload["binding_plan"]["execution_profile"], "local")
        self.assertEqual(payload["binding_plan"]["resource_spec"], payload["resource_spec"])
        self.assertEqual(payload["binding_plan"]["runtime_image"], payload["runtime_image"])

    def test_typed_plan_accepts_slurm_execution_profile(self) -> None:
        """Freeze Slurm resource policy for later submission without running it.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")

            payload = _typed_plan(
                "annotation_qc_busco",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                resource_request={"partition": "batch"},
                execution_profile="slurm",
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["candidate_outcome"], "registered_workflow")
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["execution_profile"], "slurm")
        self.assertEqual(payload["binding_plan"]["execution_profile"], "slurm")
        self.assertEqual(payload["resource_spec"]["execution_class"], "slurm")
        self.assertEqual(payload["resource_spec"]["account"], "rcc-staff")

    def test_typed_plan_prepares_m18_busco_fixture_task(self) -> None:
        """Freeze the M18 BUSCO fixture as a registered task recipe."""
        payload = _typed_plan(
            "busco_assess_proteins",
            explicit_bindings={},
            runtime_bindings={
                "proteins_fasta": "data/busco/test_data/eukaryota/genome.fna",
                "lineage_dataset": "auto-lineage",
                "busco_mode": "geno",
                "busco_cpu": 2,
                "busco_sif": "data/images/busco_v6.0.0_cv1.sif",
            },
            resource_request={
                "cpu": "2",
                "account": "rcc-staff",
                "partition": "caslake",
                "memory": "8Gi",
                "walltime": "00:10:00",
            },
            execution_profile="slurm",
            runtime_image={"apptainer_image": "data/images/busco_v6.0.0_cv1.sif"},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["candidate_outcome"], "registered_task")
        self.assertEqual(payload["biological_goal"], "busco_assess_proteins")
        self.assertEqual(payload["execution_profile"], "slurm")
        self.assertEqual(payload["resource_spec"]["cpu"], "2")
        self.assertEqual(payload["resource_spec"]["memory"], "8Gi")
        self.assertEqual(payload["binding_plan"]["runtime_bindings"]["proteins_fasta"], "data/busco/test_data/eukaryota/genome.fna")
        self.assertEqual(payload["binding_plan"]["runtime_bindings"]["lineage_dataset"], "auto-lineage")
        self.assertEqual(payload["binding_plan"]["runtime_bindings"]["busco_mode"], "geno")
        self.assertEqual(payload["binding_plan"]["runtime_bindings"]["busco_cpu"], 2)
        self.assertEqual(payload["binding_plan"]["runtime_bindings"]["busco_sif"], "data/images/busco_v6.0.0_cv1.sif")

    def test_typed_plan_uses_entry_execution_defaults_when_no_override_provided(self) -> None:
        """Freeze entry execution_defaults into the plan when no bundle or kwarg overrides exist."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")

            payload = _typed_plan(
                "annotation_qc_busco",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "eukaryota_odb10"},
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["runtime_images"], {"busco_sif": "data/images/busco_v6.0.0_cv1.sif"})
        self.assertEqual(
            payload["tool_databases"],
            {"busco_lineage_dir": "data/busco/lineages/eukaryota_odb10"},
        )
        self.assertEqual(payload["resource_spec"]["module_loads"], ["python/3.11.9", "apptainer/1.4.1"])
        self.assertEqual(
            payload["workflow_spec"]["tool_databases"],
            {"busco_lineage_dir": "data/busco/lineages/eukaryota_odb10"},
        )
        self.assertEqual(
            payload["workflow_spec"]["replay_metadata"]["resolved_environment"]["runtime_images"],
            {"busco_sif": "data/images/busco_v6.0.0_cv1.sif"},
        )
        self.assertEqual(
            payload["binding_plan"]["runtime_image"]["apptainer_image"],
            "data/images/busco_v6.0.0_cv1.sif",
        )

    def test_typed_plan_bundle_override_wins_over_entry_defaults(self) -> None:
        """Bundle-level overrides beat entry defaults for environment metadata."""
        execution_defaults = {
            "profile": "local",
            "result_manifest": "run_manifest.json",
            "resources": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
            "slurm_resource_hints": {"cpu": "16", "memory": "64Gi", "walltime": "04:00:00"},
            "runtime_images": {"busco_sif": "/entry/busco.sif"},
            "tool_databases": {"busco_lineage_dir": "/entry/lineage"},
            "module_loads": ("entry/python", "entry/apptainer"),
            "env_vars": {"TMPDIR": "/entry/tmp"},
        }
        bundle_overrides = {
            "runtime_images": {"busco_sif": "/bundle/busco.sif"},
            "tool_databases": {"busco_lineage_dir": "/bundle/lineage"},
            "module_loads": ("bundle/python", "bundle/apptainer"),
            "env_vars": {"TMPDIR": "/bundle/tmp"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")
            with _patched_planning_entry("annotation_qc_busco", execution_defaults):
                payload = _typed_plan(
                    "annotation_qc_busco",
                    manifest_sources=(result_dir,),
                    runtime_bindings={"busco_lineages_text": "eukaryota_odb10"},
                    bundle_overrides=bundle_overrides,
                )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["runtime_images"], {"busco_sif": "/bundle/busco.sif"})
        self.assertEqual(payload["tool_databases"], {"busco_lineage_dir": "/bundle/lineage"})
        self.assertEqual(payload["resource_spec"]["module_loads"], ["bundle/python", "bundle/apptainer"])
        self.assertEqual(payload["env_vars"], {"TMPDIR": "/bundle/tmp"})

    def test_typed_plan_explicit_environment_kwargs_win_over_entry_and_bundle_defaults(self) -> None:
        """Per-call runtime_images and tool_databases override both entry and bundle defaults."""
        execution_defaults = {
            "profile": "local",
            "result_manifest": "run_manifest.json",
            "resources": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
            "runtime_images": {"busco_sif": "/entry/busco.sif"},
            "tool_databases": {"busco_lineage_dir": "/entry/lineage"},
            "module_loads": ("entry/python",),
            "env_vars": {"TMPDIR": "/entry/tmp"},
        }
        bundle_overrides = {
            "runtime_images": {"busco_sif": "/bundle/busco.sif"},
            "tool_databases": {"busco_lineage_dir": "/bundle/lineage"},
            "module_loads": ("bundle/python",),
            "env_vars": {"TMPDIR": "/bundle/tmp"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")
            with _patched_planning_entry("annotation_qc_busco", execution_defaults):
                payload = _typed_plan(
                    "annotation_qc_busco",
                    manifest_sources=(result_dir,),
                    runtime_bindings={"busco_lineages_text": "eukaryota_odb10"},
                    bundle_overrides=bundle_overrides,
                    runtime_images={"busco_sif": "/kwarg/busco.sif"},
                    tool_databases={"busco_lineage_dir": "/kwarg/lineage"},
                )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["runtime_images"], {"busco_sif": "/kwarg/busco.sif"})
        self.assertEqual(payload["tool_databases"], {"busco_lineage_dir": "/kwarg/lineage"})
        self.assertEqual(payload["resource_spec"]["module_loads"], ["bundle/python"])
        self.assertEqual(payload["env_vars"], {"TMPDIR": "/bundle/tmp"})

    def test_typed_plan_layers_execution_defaults_with_expected_fallback_order(self) -> None:
        """Kwarg, bundle, and entry layers resolve per key in the documented order."""
        execution_defaults = {
            "profile": "local",
            "result_manifest": "run_manifest.json",
            "resources": {"cpu": "16", "memory": "64Gi", "execution_class": "local"},
            "runtime_images": {"busco_sif": "/entry/busco.sif"},
            "tool_databases": {"busco_lineage_dir": "/entry/lineage"},
            "module_loads": ("entry/python",),
            "env_vars": {"TMPDIR": "/entry/tmp"},
        }
        bundle_overrides = {
            "runtime_images": {"busco_sif": "/bundle/busco.sif"},
            "tool_databases": {"busco_lineage_dir": "/bundle/lineage"},
            "module_loads": ("bundle/python",),
            "env_vars": {"TMPDIR": "/bundle/tmp"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")
            with _patched_planning_entry("annotation_qc_busco", execution_defaults):
                payload = _typed_plan(
                    "annotation_qc_busco",
                    manifest_sources=(result_dir,),
                    runtime_bindings={"busco_lineages_text": "eukaryota_odb10"},
                    bundle_overrides=bundle_overrides,
                    runtime_images={"busco_sif": "/kwarg/busco.sif"},
                    resource_request={"module_loads": ["caller/python", "caller/apptainer"]},
                )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["runtime_images"], {"busco_sif": "/kwarg/busco.sif"})
        self.assertEqual(payload["tool_databases"], {"busco_lineage_dir": "/bundle/lineage"})
        self.assertEqual(payload["resource_spec"]["module_loads"], ["caller/python", "caller/apptainer"])
        self.assertEqual(payload["env_vars"], {"TMPDIR": "/bundle/tmp"})
        self.assertEqual(
            payload["workflow_spec"]["replay_metadata"]["resolved_environment"],
            {
                "runtime_images": {"busco_sif": "/kwarg/busco.sif"},
                "tool_databases": {"busco_lineage_dir": "/bundle/lineage"},
                "module_loads": ["caller/python", "caller/apptainer"],
                "env_vars": {"TMPDIR": "/bundle/tmp"},
            },
        )

    def test_typed_plan_reports_ambiguous_busco_manifest_sources(self) -> None:
        """Decline BUSCO planning when multiple manifests could satisfy the QC target.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dirs = (
                _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results_a"),
                _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results_b"),
            )

            payload = _typed_plan(
                "annotation_qc_busco",
                manifest_sources=result_dirs,
            )

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "declined")
        self.assertEqual(payload["candidate_outcome"], "registered_workflow")
        self.assertIn("choose one explicitly", payload["missing_requirements"][0])

    def test_typed_plan_resolves_eggnog_from_busco_manifest_source(self) -> None:
        """Use a BUSCO manifest to recover the repeat-filter boundary for EggNOG.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repeat_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")
            busco_dir = tmp_path / "busco_results"
            busco_dir.mkdir()
            (busco_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow": "annotation_qc_busco",
                        "source_bundle": {"repeat_filter_results": str(repeat_dir)},
                        "outputs": {
                            "final_proteins_fasta": str(busco_dir / "all_repeats_removed.proteins.fa"),
                            "busco_summary_tsv": str(busco_dir / "busco_summary.tsv"),
                        },
                    },
                    indent=2,
                )
            )

            payload = _typed_plan(
                "annotation_functional_eggnog",
                manifest_sources=(busco_dir,),
                runtime_bindings={"eggnog_data_dir": "/db/eggnog", "eggnog_database": "Diptera"},
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_names"], ["annotation_functional_eggnog"])
        self.assertEqual(
            payload["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(repeat_dir),
        )
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {"eggnog_data_dir": "/db/eggnog", "eggnog_database": "Diptera"},
        )

    def test_typed_plan_resolves_agat_targets_from_manifest_sources(self) -> None:
        """Resolve AGAT statistics/conversion and cleanup from compatible manifests.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eggnog_dir = _eggnog_manifest_dir(tmp_path, "eggnog_results")
            conversion_dir = _agat_conversion_manifest_dir(tmp_path, "agat_conversion_results")

            conversion = _typed_plan(
                "annotation_postprocess_agat_conversion",
                manifest_sources=(eggnog_dir,),
                runtime_bindings={"agat_sif": "agat.sif"},
            )
            cleanup = _typed_plan(
                "annotation_postprocess_agat_cleanup",
                manifest_sources=(conversion_dir,),
            )

        self.assertTrue(conversion["supported"])
        self.assertTrue(cleanup["supported"])
        self.assertEqual(conversion["matched_entry_names"], ["annotation_postprocess_agat_conversion"])
        self.assertEqual(cleanup["matched_entry_names"], ["annotation_postprocess_agat_cleanup"])
        self.assertEqual(
            conversion["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(eggnog_dir),
        )
        self.assertEqual(
            cleanup["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(conversion_dir),
        )

    def test_typed_plan_selects_eggnog_functional_annotation(self) -> None:
        """Represent post-BUSCO functional annotation as a registered EggNOG workflow.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        target = QualityAssessmentTarget(
            annotation_gff3_path=Path("results/repeat_filter/all_repeats_removed.eggnog.gff3"),
            proteins_fasta_path=Path("results/repeat_filter/all_repeats_removed.proteins.fa"),
        )

        payload = _typed_plan(
            "annotation_functional_eggnog",
            explicit_bindings={"QualityAssessmentTarget": target},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_functional_eggnog")
        self.assertEqual(payload["matched_entry_names"], ["annotation_functional_eggnog"])
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_selects_agat_post_processing(self) -> None:
        """Represent post-EggNOG AGAT statistics as a registered workflow.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        target = QualityAssessmentTarget(
            annotation_gff3_path=Path("results/eggnog/all_repeats_removed.eggnog.gff3"),
        )

        payload = _typed_plan(
            "annotation_postprocess_agat",
            explicit_bindings={"QualityAssessmentTarget": target},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_postprocess_agat")
        self.assertEqual(payload["matched_entry_names"], ["annotation_postprocess_agat"])
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_selects_agat_conversion(self) -> None:
        """Represent post-EggNOG AGAT conversion as a registered workflow.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        target = QualityAssessmentTarget(
            annotation_gff3_path=Path("results/eggnog/all_repeats_removed.eggnog.gff3"),
        )

        payload = _typed_plan(
            "annotation_postprocess_agat_conversion",
            explicit_bindings={"QualityAssessmentTarget": target},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_postprocess_agat_conversion")
        self.assertEqual(payload["matched_entry_names"], ["annotation_postprocess_agat_conversion"])
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_selects_agat_cleanup(self) -> None:
        """Represent post-conversion AGAT cleanup as a registered workflow.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        target = QualityAssessmentTarget(
            annotation_gff3_path=Path("results/agat/all_repeats_removed.agat.gff3"),
        )

        payload = _typed_plan(
            "annotation_postprocess_agat_cleanup",
            explicit_bindings={"QualityAssessmentTarget": target},
        )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "registered_workflow")
        self.assertEqual(payload["biological_goal"], "annotation_postprocess_agat_cleanup")
        self.assertEqual(payload["matched_entry_names"], ["annotation_postprocess_agat_cleanup"])
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertEqual(payload["missing_requirements"], [])
        self.assertEqual(payload["binding_plan"]["target_kind"], "workflow")

    def test_typed_plan_reports_missing_inputs_without_guessing(self) -> None:
        """Decline a recognized typed goal when resolver sources cannot satisfy it.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = _typed_plan("annotation_qc_busco")

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "declined")
        self.assertEqual(payload["candidate_outcome"], "registered_workflow")
        self.assertEqual(payload["required_planner_types"], ["QualityAssessmentTarget"])
        self.assertIn("No QualityAssessmentTarget", payload["missing_requirements"][0])

    def test_typed_plan_warns_when_source_prompt_is_empty(self) -> None:
        """Structured planning should flag when no original prompt provenance is supplied."""
        payload = _typed_plan("annotation_qc_busco")

        self.assertIn("No source_prompt was supplied", payload["limitations"][0])

    def test_typed_plan_declines_unsupported_biology(self) -> None:
        """Reject unsupported biology instead of inventing registry entries.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        payload = plan_request("Run SNP variant calling and emit a VCF.")

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "declined")
        self.assertEqual(payload["matched_entry_names"], [])
        self.assertIn("does not map to a supported typed biology goal", payload["missing_requirements"][0])

    def test_supported_entry_parameters_match_current_workflow_signature(self) -> None:
        """Treat the current BRAKER3 showcase workflow signature as compatibility-critical.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        parameters = supported_entry_parameters("ab_initio_annotation_braker3")

        self.assertEqual(
            [(parameter.name, parameter.required) for parameter in parameters],
            [
                ("genome", True),
                ("rnaseq_bam_path", False),
                ("protein_fasta_path", False),
                ("braker_species", False),
                ("braker3_sif", False),
            ],
        )

    def test_split_entry_inputs_preserves_required_and_optional_groups(self) -> None:
        """Expose the current protein-evidence planner grouping without changing task signatures.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        required_inputs, optional_inputs = split_entry_inputs("protein_evidence_alignment")

        self.assertEqual([field.name for field in required_inputs], ["genome", "protein_fastas"])
        self.assertEqual(
            [field.name for field in optional_inputs],
            ["proteins_per_chunk", "exonerate_sif", "exonerate_model"],
        )

    def test_plan_request_matches_exact_biological_stage_with_structured_inputs(self) -> None:
        """Free-text preview still works when the request matches one biological_stage exactly."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")

            payload = plan_request(
                "BUSCO annotation quality assessment",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
            )

        self.assertTrue(payload["supported"])
        self.assertEqual(payload["matched_entry_names"], ["annotation_qc_busco"])
        self.assertEqual(payload["candidate_outcome"], "registered_workflow")
        self.assertEqual(
            payload["resolved_inputs"]["QualityAssessmentTarget"]["source_result_dir"],
            str(result_dir),
        )
        self.assertEqual(
            payload["binding_plan"]["runtime_bindings"],
            {"busco_lineages_text": "embryophyta_odb10"},
        )

    def test_plan_request_declines_old_prompt_path_flow_cleanly(self) -> None:
        """Free-text preview no longer extracts local paths or downstream intent from prose."""
        payload = plan_request(
            "Run protein evidence alignment with genome /tmp/genome.fa and protein evidence /tmp/proteins.fa."
        )

        self.assertFalse(payload["supported"])
        self.assertEqual(payload["planning_outcome"], "declined")
        self.assertEqual(payload["matched_entry_names"], [])
        self.assertIn("does not map to a supported typed biology goal", payload["missing_requirements"][0])

    def test_plan_request_reshape_single_entry_match_skips_freeze(self) -> None:
        """Single-entry matches return a no-freeze PlanSuccess that re-issues run_workflow."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result_dir = _repeat_filter_manifest_dir(tmp_path, "repeat_filter_results")
            recipe_dir = tmp_path / "specs"

            reply = plan_request_reshape(
                "BUSCO annotation quality assessment",
                manifest_sources=(result_dir,),
                runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                recipe_dir=recipe_dir,
            )

            self.assertIsInstance(reply, PlanSuccess)
            assert isinstance(reply, PlanSuccess)  # narrow for mypy/tests
            self.assertTrue(reply.supported)
            self.assertEqual(reply.target, "annotation_qc_busco")
            self.assertFalse(reply.requires_user_approval)
            self.assertEqual(reply.composition_stages, ())
            self.assertEqual(reply.artifact_path, "")
            self.assertFalse(recipe_dir.exists())

            suggested = reply.suggested_next_call
            self.assertEqual(suggested["tool"], "run_workflow")
            kwargs = suggested["kwargs"]
            self.assertEqual(kwargs["workflow_name"], "annotation_qc_busco")
            self.assertEqual(kwargs["source_prompt"], "BUSCO annotation quality assessment")
            self.assertIn("QualityAssessmentTarget", kwargs["bindings"])
            self.assertEqual(kwargs["inputs"]["busco_lineages_text"], "embryophyta_odb10")

    def test_plan_request_reshape_composed_request_freezes_artifact(self) -> None:
        """Composed DAGs freeze a WorkflowSpec artifact and point at approve_composed_recipe."""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        reads = ReadSet(
            sample_id="sample1",
            left_reads_path=Path("data/reads/r1.fastq.gz"),
            right_reads_path=Path("data/reads/r2.fastq.gz"),
        )

        with tempfile.TemporaryDirectory() as tmp:
            recipe_dir = Path(tmp) / "specs"
            reply = plan_request_reshape(
                "chain annotation repeat filtering with BUSCO quality workflow processing",
                explicit_bindings={"ReferenceGenome": reference_genome, "ReadSet": reads},
                recipe_dir=recipe_dir,
                created_at="2026-04-20T00:00:00Z",
            )

            self.assertIsInstance(reply, PlanSuccess)
            assert isinstance(reply, PlanSuccess)
            self.assertTrue(reply.supported)
            self.assertTrue(reply.requires_user_approval)
            self.assertTrue(reply.target.startswith("composed-"))
            self.assertGreaterEqual(len(reply.composition_stages), 2)

            artifact_path = reply.artifact_path
            self.assertNotEqual(artifact_path, "")
            frozen = Path(artifact_path)
            self.assertTrue(frozen.exists())
            self.assertEqual(frozen.parent, recipe_dir)

            suggested = reply.suggested_next_call
            self.assertEqual(suggested["tool"], "approve_composed_recipe")
            self.assertEqual(suggested["kwargs"], {"artifact_path": artifact_path})
            self.assertTrue(any("approve_composed_recipe" in line for line in reply.limitations))

    def test_plan_request_reshape_unsupported_request_returns_plan_decline(self) -> None:
        """Requests the planner cannot route return a PlanDecline with §10 recovery channels."""
        with tempfile.TemporaryDirectory() as tmp:
            recipe_dir = Path(tmp) / "specs"
            reply = plan_request_reshape(
                "Run variant calling for SNV detection on these reads.",
                recipe_dir=recipe_dir,
            )

            self.assertIsInstance(reply, PlanDecline)
            assert isinstance(reply, PlanDecline)
            self.assertFalse(reply.supported)
            self.assertFalse(recipe_dir.exists())
            self.assertGreater(len(reply.suggested_bundles), 0)
            for bundle in reply.suggested_bundles:
                self.assertTrue(bundle.available)
            self.assertEqual(reply.suggested_prior_runs, ())
            self.assertGreater(len(reply.next_steps), 0)
