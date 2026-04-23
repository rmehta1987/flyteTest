"""Serialization regression fixtures for all three serialization layers.

These tests lock the current behavior of PlannerSerializable, SpecSerializable,
and ManifestSerializable before any rewiring in A1-A4.  Expected dicts are
hardcoded intentionally — a diff in the expected value is a breaking change.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

from flytetest.planner_types import ReferenceGenome as PlannerReferenceGenome
from flytetest.planner_types import ReadSet
from flytetest.specs import (
    DeterministicExecutionContract,
    ResourceSpec,
    RuntimeImageSpec,
    TaskSpec,
    TypedFieldSpec,
)
from flytetest.types.assets import (
    AssetToolProvenance,
    Braker3InputBundleAsset,
    Braker3NormalizedGff3Asset,
    Braker3RawRunResultAsset,
    Braker3ResultBundle,
    ReferenceGenome as AssetReferenceGenome,
)


# ---------------------------------------------------------------------------
# Spec layer
# ---------------------------------------------------------------------------


class TestSpecLayerRegression(unittest.TestCase):
    """Snapshot tests for SpecSerializable (specs.py).

    The spec layer handles: Path, tuple, dict recursion, and nested
    dataclasses.  It does NOT use to_dict() fallback on nested dataclasses.
    """

    def _make_task_spec(self) -> TaskSpec:
        return TaskSpec(
            name="run_braker3",
            biological_stage="ab_initio_annotation",
            description="Run BRAKER3 ab initio annotation",
            inputs=(
                TypedFieldSpec(
                    name="genome",
                    type_name="Path",
                    description="Input genome FASTA",
                ),
                TypedFieldSpec(
                    name="species",
                    type_name="str",
                    description="Species name for AUGUSTUS training",
                    required=True,
                    repeated=False,
                    planner_type_names=("ReferenceGenome",),
                ),
            ),
            outputs=(
                TypedFieldSpec(
                    name="braker_gff3",
                    type_name="Path",
                    description="Raw BRAKER3 GFF3 output",
                ),
            ),
            deterministic_execution=DeterministicExecutionContract(
                deterministic=True,
                result_boundary="braker3_raw_output",
                assumptions=("genome and evidence inputs unchanged",),
                limitations=("non-deterministic AUGUSTUS training",),
            ),
            resource_spec=ResourceSpec(cpu="8", memory="64G", partition="normal"),
            runtime_image=RuntimeImageSpec(
                container_image="ghcr.io/example/braker3:latest"
            ),
            supported_execution_profiles=("slurm_standard",),
            compatibility_constraints=("requires AUGUSTUS models",),
        )

    def test_task_spec_serialize_exact_shape(self) -> None:
        """Serialized TaskSpec matches the hardcoded expected dict."""
        spec = self._make_task_spec()
        result = spec.to_dict()
        expected = {
            "name": "run_braker3",
            "biological_stage": "ab_initio_annotation",
            "description": "Run BRAKER3 ab initio annotation",
            "inputs": [
                {
                    "name": "genome",
                    "type_name": "Path",
                    "description": "Input genome FASTA",
                    "required": True,
                    "repeated": False,
                    "planner_type_names": [],
                },
                {
                    "name": "species",
                    "type_name": "str",
                    "description": "Species name for AUGUSTUS training",
                    "required": True,
                    "repeated": False,
                    "planner_type_names": ["ReferenceGenome"],
                },
            ],
            "outputs": [
                {
                    "name": "braker_gff3",
                    "type_name": "Path",
                    "description": "Raw BRAKER3 GFF3 output",
                    "required": True,
                    "repeated": False,
                    "planner_type_names": [],
                }
            ],
            "deterministic_execution": {
                "deterministic": True,
                "result_boundary": "braker3_raw_output",
                "assumptions": ["genome and evidence inputs unchanged"],
                "limitations": ["non-deterministic AUGUSTUS training"],
            },
            "resource_spec": {
                "cpu": "8",
                "memory": "64G",
                "gpu": None,
                "partition": "normal",
                "account": None,
                "walltime": None,
                "execution_class": None,
                "module_loads": [],
                "notes": [],
            },
            "runtime_image": {
                "container_image": "ghcr.io/example/braker3:latest",
                "apptainer_image": None,
                "runtime_assumptions": [],
                "compatibility_notes": [],
            },
            "supported_execution_profiles": ["slurm_standard"],
            "compatibility_constraints": ["requires AUGUSTUS models"],
            "metadata_only": True,
        }
        self.assertEqual(result, expected)

    def test_task_spec_round_trip(self) -> None:
        """from_dict(to_dict(spec)) reproduces field-level equality."""
        spec = self._make_task_spec()
        restored = TaskSpec.from_dict(spec.to_dict())
        self.assertEqual(spec.name, restored.name)
        self.assertEqual(spec.biological_stage, restored.biological_stage)
        self.assertEqual(len(spec.inputs), len(restored.inputs))
        self.assertEqual(spec.inputs[0].name, restored.inputs[0].name)
        self.assertEqual(spec.inputs[0].planner_type_names, restored.inputs[0].planner_type_names)
        self.assertEqual(spec.inputs[1].planner_type_names, restored.inputs[1].planner_type_names)
        self.assertEqual(spec.deterministic_execution.assumptions, restored.deterministic_execution.assumptions)
        self.assertIsNotNone(restored.resource_spec)
        self.assertEqual(spec.resource_spec.cpu, restored.resource_spec.cpu)
        self.assertEqual(spec.resource_spec.module_loads, restored.resource_spec.module_loads)
        self.assertIsNotNone(restored.runtime_image)
        self.assertEqual(spec.runtime_image.container_image, restored.runtime_image.container_image)
        self.assertEqual(spec.supported_execution_profiles, restored.supported_execution_profiles)
        self.assertEqual(spec.metadata_only, restored.metadata_only)

    def test_task_spec_none_optional_serializes_to_none(self) -> None:
        """Optional fields that are None serialize as None and round-trip cleanly."""
        spec = TaskSpec(
            name="minimal",
            biological_stage="stage",
            description="desc",
            inputs=(),
            outputs=(),
            deterministic_execution=DeterministicExecutionContract(),
            resource_spec=None,
            runtime_image=None,
        )
        d = spec.to_dict()
        self.assertIsNone(d["resource_spec"])
        self.assertIsNone(d["runtime_image"])
        restored = TaskSpec.from_dict(d)
        self.assertIsNone(restored.resource_spec)
        self.assertIsNone(restored.runtime_image)

    def test_resource_spec_tuple_fields_serialize_to_lists(self) -> None:
        """Tuple fields in ResourceSpec become JSON lists."""
        rs = ResourceSpec(
            cpu="4",
            module_loads=("python/3.11.9", "apptainer/1.4.1"),
            notes=("HPC note",),
        )
        d = rs.to_dict()
        self.assertEqual(d["module_loads"], ["python/3.11.9", "apptainer/1.4.1"])
        self.assertEqual(d["notes"], ["HPC note"])
        restored = ResourceSpec.from_dict(d)
        self.assertEqual(restored.module_loads, ("python/3.11.9", "apptainer/1.4.1"))
        self.assertEqual(restored.notes, ("HPC note",))


# ---------------------------------------------------------------------------
# Planner layer
# ---------------------------------------------------------------------------


class TestPlannerLayerRegression(unittest.TestCase):
    """Snapshot tests for PlannerSerializable (planner_types.py).

    The planner layer handles: Path, tuple, and nested planner dataclasses.
    It does NOT recurse through plain dicts.
    """

    def _make_reference_genome(self) -> PlannerReferenceGenome:
        return PlannerReferenceGenome(
            fasta_path=Path("/data/genome.fa"),
            organism_name="Homo sapiens",
            assembly_name=None,
            taxonomy_id=9606,
            softmasked_fasta_path=Path("/data/genome.softmasked.fa"),
            annotation_gff3_path=None,
            source_result_dir=None,
            source_manifest_path=None,
            notes=("primary assembly", "GRCh38"),
        )

    def test_reference_genome_serialize_exact_shape(self) -> None:
        """Serialized ReferenceGenome matches hardcoded expected dict."""
        genome = self._make_reference_genome()
        result = genome.to_dict()
        expected = {
            "fasta_path": "/data/genome.fa",
            "organism_name": "Homo sapiens",
            "assembly_name": None,
            "taxonomy_id": 9606,
            "softmasked_fasta_path": "/data/genome.softmasked.fa",
            "annotation_gff3_path": None,
            "source_result_dir": None,
            "source_manifest_path": None,
            "notes": ["primary assembly", "GRCh38"],
        }
        self.assertEqual(result, expected)

    def test_reference_genome_round_trip(self) -> None:
        """from_dict(to_dict(genome)) reproduces field-level equality."""
        genome = self._make_reference_genome()
        restored = PlannerReferenceGenome.from_dict(genome.to_dict())
        self.assertEqual(genome.fasta_path, restored.fasta_path)
        self.assertEqual(genome.organism_name, restored.organism_name)
        self.assertIsNone(restored.assembly_name)
        self.assertEqual(genome.taxonomy_id, restored.taxonomy_id)
        self.assertEqual(genome.softmasked_fasta_path, restored.softmasked_fasta_path)
        self.assertIsNone(restored.annotation_gff3_path)
        self.assertIsNone(restored.source_result_dir)
        self.assertEqual(genome.notes, restored.notes)

    def test_read_set_serialize_exact_shape(self) -> None:
        """Serialized ReadSet matches hardcoded expected dict."""
        rs = ReadSet(
            sample_id="SRR001",
            left_reads_path=Path("/data/SRR001_R1.fastq.gz"),
            right_reads_path=Path("/data/SRR001_R2.fastq.gz"),
            platform="ILLUMINA",
            strandedness=None,
            condition="treated",
            replicate_label=None,
            source_result_dir=None,
            source_manifest_path=None,
            notes=("paired-end RNA-seq",),
        )
        result = rs.to_dict()
        expected = {
            "sample_id": "SRR001",
            "left_reads_path": "/data/SRR001_R1.fastq.gz",
            "right_reads_path": "/data/SRR001_R2.fastq.gz",
            "platform": "ILLUMINA",
            "strandedness": None,
            "condition": "treated",
            "replicate_label": None,
            "source_result_dir": None,
            "source_manifest_path": None,
            "notes": ["paired-end RNA-seq"],
        }
        self.assertEqual(result, expected)

    def test_read_set_round_trip(self) -> None:
        """from_dict(to_dict(read_set)) reproduces field-level equality."""
        rs = ReadSet(
            sample_id="SRR001",
            left_reads_path=Path("/data/SRR001_R1.fastq.gz"),
            right_reads_path=Path("/data/SRR001_R2.fastq.gz"),
        )
        restored = ReadSet.from_dict(rs.to_dict())
        self.assertEqual(rs.sample_id, restored.sample_id)
        self.assertEqual(rs.left_reads_path, restored.left_reads_path)
        self.assertEqual(rs.right_reads_path, restored.right_reads_path)
        self.assertEqual(rs.platform, restored.platform)
        self.assertIsNone(restored.strandedness)

    def test_planner_path_serializes_to_string(self) -> None:
        """Path objects become plain strings in the serialized payload."""
        genome = self._make_reference_genome()
        d = genome.to_dict()
        self.assertIsInstance(d["fasta_path"], str)
        self.assertIsInstance(d["softmasked_fasta_path"], str)

    def test_planner_tuple_serializes_to_list(self) -> None:
        """Tuple fields become JSON lists in the serialized payload."""
        genome = self._make_reference_genome()
        d = genome.to_dict()
        self.assertIsInstance(d["notes"], list)
        self.assertEqual(d["notes"], ["primary assembly", "GRCh38"])

    def test_planner_round_trip_restores_path_objects(self) -> None:
        """Deserialized planner types restore string paths back to Path objects."""
        genome = self._make_reference_genome()
        restored = PlannerReferenceGenome.from_dict(genome.to_dict())
        self.assertIsInstance(restored.fasta_path, Path)
        self.assertIsInstance(restored.softmasked_fasta_path, Path)

    def test_planner_round_trip_restores_tuple_fields(self) -> None:
        """Deserialized planner types restore list payloads back to tuples."""
        genome = self._make_reference_genome()
        restored = PlannerReferenceGenome.from_dict(genome.to_dict())
        self.assertIsInstance(restored.notes, tuple)
        self.assertEqual(restored.notes, ("primary assembly", "GRCh38"))


# ---------------------------------------------------------------------------
# Asset layer
# ---------------------------------------------------------------------------


class TestAssetLayerRegression(unittest.TestCase):
    """Snapshot tests for ManifestSerializable (types/assets.py).

    The asset layer handles: Path, tuple, dict recursion, nested dataclasses
    (with and without to_dict()), and scalar coercion on deserialize.
    """

    def _make_bundle(self) -> Braker3ResultBundle:
        ref = AssetReferenceGenome(
            fasta_path=Path("/tmp/braker3_synth/genome.fa"),
            organism_name=None,
            assembly_name=None,
            taxonomy_id=None,
            softmasked_fasta_path=None,
            annotation_gff3_path=None,
        )
        input_bundle = Braker3InputBundleAsset(
            staged_dir=Path("/fixtures/braker3_results/staged_inputs"),
            genome_fasta_path=Path("/fixtures/braker3_results/staged_inputs/genome/genome.fa"),
            rnaseq_bam_path=Path("/fixtures/braker3_results/staged_inputs/rnaseq_bam/reads.bam"),
            protein_fasta_path=None,
            notes=("staged bundle note",),
        )
        provenance = AssetToolProvenance(
            tool_name="braker3",
            tool_stage="ab_initio_annotation",
            tool_version="3.0.0",
            legacy_asset_name=None,
            source_manifest_key="braker3_result_bundle",
            notes=(),
        )
        return Braker3ResultBundle(
            result_dir=Path("/fixtures/braker3_results"),
            staged_inputs_dir=Path("/fixtures/braker3_results/staged_inputs"),
            raw_run_dir=Path("/fixtures/braker3_results/braker3_raw"),
            normalized_dir=Path("/fixtures/braker3_results/braker3_normalized"),
            braker_gff3_path=Path("/fixtures/braker3_results/braker3_raw/braker_output/braker.gff3"),
            normalized_gff3_path=Path("/fixtures/braker3_results/braker3_normalized/braker3.evm.gff3"),
            reference_genome=ref,
            input_bundle=input_bundle,
            raw_run=None,
            normalized_prediction=None,
            notes=("braker3 result bundle note",),
            provenance=provenance,
        )

    def test_braker3_bundle_serialize_exact_shape(self) -> None:
        """Serialized Braker3ResultBundle matches hardcoded expected dict."""
        bundle = self._make_bundle()
        result = bundle.to_dict()
        expected = {
            "result_dir": "/fixtures/braker3_results",
            "staged_inputs_dir": "/fixtures/braker3_results/staged_inputs",
            "raw_run_dir": "/fixtures/braker3_results/braker3_raw",
            "normalized_dir": "/fixtures/braker3_results/braker3_normalized",
            "braker_gff3_path": "/fixtures/braker3_results/braker3_raw/braker_output/braker.gff3",
            "normalized_gff3_path": "/fixtures/braker3_results/braker3_normalized/braker3.evm.gff3",
            "reference_genome": {
                "fasta_path": "/tmp/braker3_synth/genome.fa",
                "organism_name": None,
                "assembly_name": None,
                "taxonomy_id": None,
                "softmasked_fasta_path": None,
                "annotation_gff3_path": None,
            },
            "input_bundle": {
                "staged_dir": "/fixtures/braker3_results/staged_inputs",
                "genome_fasta_path": "/fixtures/braker3_results/staged_inputs/genome/genome.fa",
                "rnaseq_bam_path": "/fixtures/braker3_results/staged_inputs/rnaseq_bam/reads.bam",
                "protein_fasta_path": None,
                "notes": ["staged bundle note"],
            },
            "raw_run": None,
            "normalized_prediction": None,
            "notes": ["braker3 result bundle note"],
            "provenance": {
                "tool_name": "braker3",
                "tool_stage": "ab_initio_annotation",
                "tool_version": "3.0.0",
                "legacy_asset_name": None,
                "source_manifest_key": "braker3_result_bundle",
                "notes": [],
            },
        }
        self.assertEqual(result, expected)

    def test_braker3_bundle_round_trip(self) -> None:
        """from_dict(to_dict(bundle)) reproduces field-level equality."""
        bundle = self._make_bundle()
        restored = Braker3ResultBundle.from_dict(bundle.to_dict())
        self.assertEqual(bundle.result_dir, restored.result_dir)
        self.assertEqual(bundle.staged_inputs_dir, restored.staged_inputs_dir)
        self.assertEqual(bundle.notes, restored.notes)
        self.assertIsNone(restored.raw_run)
        self.assertIsNone(restored.normalized_prediction)
        self.assertIsNotNone(restored.reference_genome)
        self.assertIsNone(restored.reference_genome.organism_name)
        self.assertEqual(
            restored.reference_genome.fasta_path,
            Path("/tmp/braker3_synth/genome.fa"),
        )
        self.assertIsNotNone(restored.input_bundle)
        self.assertIsNone(restored.input_bundle.protein_fasta_path)
        self.assertEqual(restored.input_bundle.notes, ("staged bundle note",))
        self.assertIsNotNone(restored.provenance)
        self.assertEqual(restored.provenance.tool_name, "braker3")
        self.assertEqual(restored.provenance.tool_version, "3.0.0")
        self.assertEqual(restored.provenance.notes, ())

    def test_asset_tool_provenance_serialize_exact_shape(self) -> None:
        """Serialized AssetToolProvenance matches hardcoded expected dict."""
        prov = AssetToolProvenance(
            tool_name="star",
            tool_stage="rnaseq_alignment",
            tool_version="2.7.10a",
            legacy_asset_name=None,
            source_manifest_key="star_alignment_result",
            notes=("two-pass alignment",),
        )
        result = prov.to_dict()
        expected = {
            "tool_name": "star",
            "tool_stage": "rnaseq_alignment",
            "tool_version": "2.7.10a",
            "legacy_asset_name": None,
            "source_manifest_key": "star_alignment_result",
            "notes": ["two-pass alignment"],
        }
        self.assertEqual(result, expected)

    def test_asset_reload_from_committed_fixture(self) -> None:
        """Braker3ResultBundle.from_dict() loads the committed fixture correctly."""
        fixture_path = FIXTURES_DIR / "run_manifest_regression.json"
        with open(fixture_path) as fh:
            data = json.load(fh)

        bundle = Braker3ResultBundle.from_dict(data)

        # Top-level Path fields
        self.assertEqual(bundle.result_dir, Path("/fixtures/braker3_results"))
        self.assertEqual(bundle.staged_inputs_dir, Path("/fixtures/braker3_results/staged_inputs"))
        self.assertEqual(bundle.raw_run_dir, Path("/fixtures/braker3_results/braker3_raw"))
        self.assertEqual(bundle.normalized_dir, Path("/fixtures/braker3_results/braker3_normalized"))
        self.assertEqual(
            bundle.braker_gff3_path,
            Path("/fixtures/braker3_results/braker3_raw/braker_output/braker.gff3"),
        )
        self.assertEqual(
            bundle.normalized_gff3_path,
            Path("/fixtures/braker3_results/braker3_normalized/braker3.evm.gff3"),
        )

        # notes tuple
        self.assertIsInstance(bundle.notes, tuple)
        self.assertEqual(len(bundle.notes), 1)

        # Nested reference_genome (non-ManifestSerializable dataclass)
        self.assertIsNotNone(bundle.reference_genome)
        self.assertIsInstance(bundle.reference_genome.fasta_path, Path)
        self.assertIsNone(bundle.reference_genome.organism_name)
        self.assertIsNone(bundle.reference_genome.taxonomy_id)

        # Nested input_bundle (non-ManifestSerializable dataclass)
        self.assertIsNotNone(bundle.input_bundle)
        self.assertIsInstance(bundle.input_bundle.staged_dir, Path)
        self.assertIsNone(bundle.input_bundle.protein_fasta_path)
        self.assertIsInstance(bundle.input_bundle.notes, tuple)

        # Nested raw_run with its own nested input_bundle
        self.assertIsNotNone(bundle.raw_run)
        self.assertEqual(bundle.raw_run.species_name, "synthetic_species")
        self.assertIsInstance(bundle.raw_run.output_dir, Path)
        self.assertIsNotNone(bundle.raw_run.input_bundle)
        self.assertIsNone(bundle.raw_run.input_bundle.protein_fasta_path)

        # Nested normalized_prediction with doubly-nested source_run
        self.assertIsNotNone(bundle.normalized_prediction)
        self.assertIsInstance(bundle.normalized_prediction.output_dir, Path)
        self.assertIsNotNone(bundle.normalized_prediction.source_run)
        self.assertEqual(
            bundle.normalized_prediction.source_run.species_name, "synthetic_species"
        )

        # provenance is absent from fixture — must default to None
        self.assertIsNone(bundle.provenance)

    def test_asset_none_optional_round_trips(self) -> None:
        """None Optional fields survive a to_dict/from_dict round-trip."""
        bundle = self._make_bundle()
        # raw_run and normalized_prediction are None in the test bundle
        d = bundle.to_dict()
        self.assertIsNone(d["raw_run"])
        self.assertIsNone(d["normalized_prediction"])
        restored = Braker3ResultBundle.from_dict(d)
        self.assertIsNone(restored.raw_run)
        self.assertIsNone(restored.normalized_prediction)

    def test_asset_path_serializes_to_string(self) -> None:
        """Path objects in asset payloads become plain strings."""
        bundle = self._make_bundle()
        d = bundle.to_dict()
        self.assertIsInstance(d["result_dir"], str)
        self.assertIsInstance(d["braker_gff3_path"], str)
        self.assertIsInstance(d["reference_genome"]["fasta_path"], str)

    def test_asset_tuple_serializes_to_list(self) -> None:
        """Tuple fields in asset payloads become JSON lists."""
        bundle = self._make_bundle()
        d = bundle.to_dict()
        self.assertIsInstance(d["notes"], list)
        self.assertEqual(d["notes"], ["braker3 result bundle note"])
        self.assertIsInstance(d["input_bundle"]["notes"], list)

    def test_asset_round_trip_restores_path_objects(self) -> None:
        """Deserialized asset types restore string paths to Path objects."""
        bundle = self._make_bundle()
        restored = Braker3ResultBundle.from_dict(bundle.to_dict())
        self.assertIsInstance(restored.result_dir, Path)
        self.assertIsInstance(restored.braker_gff3_path, Path)
        self.assertIsInstance(restored.input_bundle.genome_fasta_path, Path)

    def test_asset_round_trip_restores_tuple_fields(self) -> None:
        """Deserialized asset types restore list payloads back to tuples."""
        bundle = self._make_bundle()
        restored = Braker3ResultBundle.from_dict(bundle.to_dict())
        self.assertIsInstance(restored.notes, tuple)
        self.assertIsInstance(restored.input_bundle.notes, tuple)


if __name__ == "__main__":
    unittest.main()
