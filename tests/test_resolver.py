"""Synthetic coverage for the first manifest-backed resolver layer.

    These tests cover local input resolution rules without changing the current
    prompt planner or execution paths.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.errors import (
    BindingTypeMismatchError,
    BindingPathMissingError,
    ManifestNotFoundError,
    UnknownOutputNameError,
    UnknownRunIdError,
)
from flytetest.planner_types import ProteinEvidenceSet, QualityAssessmentTarget, ReferenceGenome, TranscriptEvidenceSet
from flytetest.resolver import LocalManifestAssetResolver, _materialize_bindings
from flytetest.spec_artifacts import DURABLE_ASSET_INDEX_SCHEMA_VERSION, DurableAssetRef
from flytetest.types.assets import AbInitioResultBundle, AssetToolProvenance, ProteinEvidenceResultBundle, ProteinReferenceDatasetAsset
from flytetest.planner_types import ReferenceGenome as AssetReferenceGenome


def _write_transcript_evidence_manifest(result_dir: Path) -> Path:
    """Write one transcript-evidence manifest that the planner adapter can read."""
    manifest_path = result_dir / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "workflow": "transcript_evidence_generation",
                "notes_alignment": {"reason": "Both Trinity branches remain visible upstream of PASA."},
                "assumptions": ["Single-sample STAR alignment remains the current simplification."],
                "outputs": {
                    "trinity_denovo_fasta": str(result_dir / "trinity_denovo.Trinity.fasta"),
                    "trinity_gg_fasta": str(result_dir / "trinity_gg.Trinity-GG.fasta"),
                    "stringtie_gtf": str(result_dir / "transcripts.gtf"),
                    "merged_bam": str(result_dir / "merged.bam"),
                },
                "assets": {
                    "reference_genome": {
                        "fasta_path": "data/braker3/reference/genome.fa",
                        "organism_name": "Example organism",
                        "assembly_name": None,
                        "taxonomy_id": None,
                        "softmasked_fasta_path": None,
                        "annotation_gff3_path": None,
                        "notes": [],
                    },
                    "read_pair": {
                        "sample_id": "sampleA",
                        "left_reads_path": "data/transcriptomics/ref-based/reads_1.fq.gz",
                        "right_reads_path": "data/transcriptomics/ref-based/reads_2.fq.gz",
                        "platform": "ILLUMINA",
                        "strandedness": None,
                        "condition": None,
                        "replicate_label": None,
                    },
                },
            },
            indent=2,
        )
    )
    return manifest_path


class ResolverTests(TestCase):
    """Coverage for explicit, manifest-backed, and bundle-backed resolution.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_explicit_binding_wins_over_discovered_sources(self) -> None:
        """Prefer an explicit local planner value over any discovered manifest candidate.
"""
        resolver = LocalManifestAssetResolver()
        explicit_reference = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))

        result = resolver.resolve(
            "ReferenceGenome",
            explicit_bindings={"ReferenceGenome": explicit_reference},
            manifest_sources=(),
        )

        self.assertTrue(result.is_resolved)
        self.assertIs(result.resolved_value, explicit_reference)
        self.assertEqual(result.selected_source.kind, "explicit_binding")

    def test_resolver_can_build_transcript_evidence_from_manifest_path(self) -> None:
        """Resolve transcript evidence from a current manifest-shaped local results directory.
"""
        resolver = LocalManifestAssetResolver()
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "transcript_results"
            result_dir.mkdir()
            (result_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow": "transcript_evidence_generation",
                        "notes_alignment": {"reason": "Both Trinity branches remain visible upstream of PASA."},
                        "assumptions": ["Single-sample STAR alignment remains the current simplification."],
                        "outputs": {
                            "trinity_denovo_fasta": str(result_dir / "trinity_denovo.Trinity.fasta"),
                            "trinity_gg_fasta": str(result_dir / "trinity_gg.Trinity-GG.fasta"),
                            "stringtie_gtf": str(result_dir / "transcripts.gtf"),
                            "merged_bam": str(result_dir / "merged.bam"),
                        },
                        "assets": {
                            "reference_genome": {
                                "fasta_path": "data/braker3/reference/genome.fa",
                                "organism_name": "Example organism",
                                "assembly_name": None,
                                "taxonomy_id": None,
                                "softmasked_fasta_path": None,
                                "annotation_gff3_path": None,
                                "notes": [],
                            },
                            "read_pair": {
                                "sample_id": "sampleA",
                                "left_reads_path": "data/transcriptomics/ref-based/reads_1.fq.gz",
                                "right_reads_path": "data/transcriptomics/ref-based/reads_2.fq.gz",
                                "platform": "ILLUMINA",
                                "strandedness": None,
                                "condition": None,
                                "replicate_label": None,
                            },
                        },
                    },
                    indent=2,
                )
            )

            result = resolver.resolve("TranscriptEvidenceSet", manifest_sources=(result_dir,))

        self.assertTrue(result.is_resolved)
        self.assertIsInstance(result.resolved_value, TranscriptEvidenceSet)
        self.assertEqual(result.selected_source.kind, "manifest")
        self.assertEqual(result.resolved_value.reference_genome.fasta_path, Path("data/braker3/reference/genome.fa"))
        self.assertEqual(result.resolved_value.read_sets[0].sample_id, "sampleA")

    def test_resolver_reports_ambiguity_instead_of_guessing(self) -> None:
        """Return an unresolved ambiguity when more than one candidate is found.
"""
        resolver = LocalManifestAssetResolver()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifests = []
            for index in (1, 2):
                result_dir = tmp_path / f"protein_results_{index}"
                result_dir.mkdir()
                manifest_path = result_dir / "run_manifest.json"
                protein_fasta_path = (
                    "data/braker3/protein_data/fastas/proteins.fa"
                    if index == 1
                    else "data/braker3/protein_data/fastas/proteins_extra.fa"
                )
                manifest_path.write_text(
                    json.dumps(
                        {
                            "workflow": "protein_evidence_alignment",
                            "outputs": {
                                "concatenated_raw_exonerate": str(result_dir / "all_chunks.exonerate.out"),
                                "concatenated_evm_protein_gff3": str(result_dir / "protein_evidence.evm.gff3"),
                            },
                            "assets": {
                                "reference_genome": {
                                    "fasta_path": "data/braker3/reference/genome.fa",
                                    "organism_name": None,
                                    "assembly_name": None,
                                    "taxonomy_id": None,
                                    "softmasked_fasta_path": None,
                                    "annotation_gff3_path": None,
                                    "notes": [],
                                },
                                "protein_reference_dataset": {
                                    "source_fasta_paths": [protein_fasta_path],
                                },
                            },
                        },
                        indent=2,
                    )
                )
                manifests.append(result_dir)

            result = resolver.resolve("ProteinEvidenceSet", manifest_sources=tuple(manifests))

        self.assertFalse(result.is_resolved)
        self.assertEqual(result.candidate_count, 2)
        self.assertIn("choose one explicitly", result.unresolved_requirements[0])

    def test_resolver_reports_missing_when_nothing_matches(self) -> None:
        """Return a missing-input message when no source can satisfy the request.
"""
        resolver = LocalManifestAssetResolver()

        result = resolver.resolve("QualityAssessmentTarget")

        self.assertFalse(result.is_resolved)
        self.assertEqual(result.candidate_count, 0)
        self.assertIn("No QualityAssessmentTarget", result.unresolved_requirements[0])

    def test_resolver_can_use_current_result_bundle_objects(self) -> None:
        """Resolve from current registered-workflow result bundle objects when provided directly.
"""
        resolver = LocalManifestAssetResolver()
        bundle = ProteinEvidenceResultBundle(
            result_dir=Path("results/protein"),
            combined_protein_fasta_path=Path("results/protein/proteins.all.fa"),
            chunk_dir=Path("results/protein/chunks"),
            raw_chunk_root=Path("results/protein/raw"),
            evm_chunk_root=Path("results/protein/evm"),
            concatenated_raw_output_path=Path("results/protein/all_chunks.exonerate.out"),
            concatenated_evm_gff3_path=Path("results/protein/protein_evidence.evm.gff3"),
            reference_genome=AssetReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa")),
            staged_dataset=ProteinReferenceDatasetAsset(
                staged_dir=Path("results/protein/staged"),
                combined_fasta_path=Path("results/protein/staged/proteins.all.fa"),
                source_fasta_paths=(Path("data/braker3/protein_data/fastas/proteins.fa"),),
            ),
        )

        result = resolver.resolve("ProteinEvidenceSet", result_bundles=(bundle,))

        self.assertTrue(result.is_resolved)
        self.assertIsInstance(result.resolved_value, ProteinEvidenceSet)
        self.assertEqual(result.selected_source.kind, "result_bundle")
        self.assertEqual(result.resolved_value.evm_ready_gff3_path, Path("results/protein/protein_evidence.evm.gff3"))

    def test_resolver_accepts_generic_ab_initio_bundle_objects(self) -> None:
        """Resolve generic ab initio bundles without losing legacy compatibility.
"""
        resolver = LocalManifestAssetResolver()
        bundle = AbInitioResultBundle(
            result_dir=Path("results/ab_initio"),
            staged_inputs_dir=Path("results/ab_initio/staged"),
            raw_run_dir=Path("results/ab_initio/raw"),
            normalized_dir=Path("results/ab_initio/normalized"),
            braker_gff3_path=Path("results/ab_initio/raw/braker.gff3"),
            normalized_gff3_path=Path("results/ab_initio/normalized/braker.normalized.gff3"),
            reference_genome=AssetReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa")),
            provenance=AssetToolProvenance(
                tool_name="BRAKER3",
                tool_stage="ab initio annotation",
                legacy_asset_name="Braker3ResultBundle",
            ),
        )

        result = resolver.resolve("AnnotationEvidenceSet", result_bundles=(bundle,))

        self.assertTrue(result.is_resolved)
        self.assertEqual(result.selected_source.bundle_type, "AbInitioResultBundle")
        self.assertEqual(result.resolved_value.ab_initio_predictions_gff3_path, bundle.normalized_gff3_path)
        self.assertIn("BRAKER3", result.resolved_value.notes[0])

    def test_resolver_can_satisfy_downstream_qc_target_from_prior_result_manifest(self) -> None:
        """Resolve a downstream QC target from a prior repeat-filter result bundle manifest.
"""
        resolver = LocalManifestAssetResolver()
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "repeat_filter_results"
            result_dir.mkdir()
            (result_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow": "annotation_repeat_filtering",
                        "assumptions": ["Repeat-filtered outputs are QC-ready."],
                        "inputs": {
                            "reference_genome": "data/braker3/reference/genome.fa",
                        },
                        "outputs": {
                            "all_repeats_removed_gff3": str(result_dir / "all_repeats_removed.gff3"),
                            "final_proteins_fasta": str(result_dir / "all_repeats_removed.proteins.fa"),
                        },
                    },
                    indent=2,
                )
            )

            result = resolver.resolve("QualityAssessmentTarget", manifest_sources=(result_dir,))

        self.assertTrue(result.is_resolved)
        self.assertIsInstance(result.resolved_value, QualityAssessmentTarget)
        self.assertEqual(result.resolved_value.annotation_gff3_path, result_dir / "all_repeats_removed.gff3")
        self.assertEqual(result.resolved_value.proteins_fasta_path, result_dir / "all_repeats_removed.proteins.fa")

    def test_materialize_bindings_raises_binding_path_missing_for_raw_path_form(self) -> None:
        """Raw path bindings should fail with BindingPathMissingError when a path is absent."""
        with self.assertRaises(BindingPathMissingError) as exc_info:
            _materialize_bindings(
                {"ReferenceGenome": {"fasta_path": "/no/such/genome.fa"}},
            )

        self.assertEqual(exc_info.exception.path, "/no/such/genome.fa")
        self.assertIn("ReferenceGenome", str(exc_info.exception))

    def test_materialize_bindings_resolves_raw_path_form(self) -> None:
        """Raw path bindings should materialize directly into planner dataclasses."""
        with tempfile.TemporaryDirectory() as tmp:
            fasta_path = Path(tmp) / "reads.fastq"
            fasta_path.write_text("@r1\nACGT\n+\n!!!!\n")

            materialized = _materialize_bindings(
                {"ReferenceGenome": {"fasta_path": str(fasta_path)}},
            )

        self.assertIsInstance(materialized["ReferenceGenome"], ReferenceGenome)
        self.assertEqual(materialized["ReferenceGenome"].fasta_path, fasta_path)

    def test_materialize_bindings_resolves_manifest_form(self) -> None:
        """Manifest-backed bindings should lower to the same planner dataclass shape."""
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "transcript_results"
            result_dir.mkdir()
            manifest_path = _write_transcript_evidence_manifest(result_dir)

            materialized = _materialize_bindings(
                {
                    "TranscriptEvidenceSet": {
                        "$manifest": str(manifest_path),
                        "output_name": "trinity_denovo_fasta",
                    }
                }
            )

        self.assertIsInstance(materialized["TranscriptEvidenceSet"], TranscriptEvidenceSet)
        self.assertEqual(
            materialized["TranscriptEvidenceSet"].de_novo_transcripts_path,
            result_dir / "trinity_denovo.Trinity.fasta",
        )
        self.assertEqual(materialized["TranscriptEvidenceSet"].read_sets[0].sample_id, "sampleA")

    def test_materialize_bindings_raises_manifest_not_found_for_manifest_form(self) -> None:
        """Manifest-backed bindings should fail with ManifestNotFoundError when the sidecar is absent."""
        with self.assertRaises(ManifestNotFoundError) as exc_info:
            _materialize_bindings(
                {
                    "QualityAssessmentTarget": {
                        "$manifest": "/no/such/run_manifest.json",
                        "output_name": "results_dir",
                    }
                }
            )

        self.assertEqual(exc_info.exception.manifest_path, "/no/such/run_manifest.json")
        self.assertIn("QualityAssessmentTarget", str(exc_info.exception))

    def test_materialize_bindings_raises_unknown_run_id_for_ref_form(self) -> None:
        """Durable-ref bindings should fail with UnknownRunIdError when the run_id is absent."""
        ref = DurableAssetRef(
            schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
            run_id="known-run",
            workflow_name="select_annotation_qc_busco",
            output_name="results_dir",
            node_name="annotation_qc_busco",
            asset_path=Path("/tmp/known-run"),
            manifest_path=Path("/tmp/known-run/run_manifest.json"),
            created_at="2026-04-20T12:00:00Z",
            run_record_path=Path("/tmp/known-run/local_run_record.json"),
            produced_type="QualityAssessmentTarget",
        )

        with self.assertRaises(UnknownRunIdError) as exc_info:
            _materialize_bindings(
                {
                    "QualityAssessmentTarget": {
                        "$ref": {"run_id": "missing-run", "output_name": "results_dir"},
                    }
                },
                durable_index=(ref,),
            )

        self.assertEqual(exc_info.exception.run_id, "missing-run")
        self.assertEqual(exc_info.exception.available_count, 1)
        self.assertIn("QualityAssessmentTarget", str(exc_info.exception))

    def test_materialize_bindings_logs_warning_on_ref_resolution_failure(self) -> None:
        """$ref resolution failures should emit one WARNING with run_id / output_name context."""
        ref = DurableAssetRef(
            schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
            run_id="known-run",
            workflow_name="select_annotation_qc_busco",
            output_name="results_dir",
            node_name="annotation_qc_busco",
            asset_path=Path("/tmp/known-run"),
            manifest_path=Path("/tmp/known-run/run_manifest.json"),
            created_at="2026-04-20T12:00:00Z",
            run_record_path=Path("/tmp/known-run/local_run_record.json"),
            produced_type="QualityAssessmentTarget",
        )

        with self.assertLogs("flytetest.resolver", level="WARNING") as log_ctx:
            with self.assertRaises(UnknownRunIdError):
                _materialize_bindings(
                    {
                        "QualityAssessmentTarget": {
                            "$ref": {"run_id": "missing-run", "output_name": "results_dir"},
                        }
                    },
                    durable_index=(ref,),
                )

        self.assertEqual(len(log_ctx.records), 1)
        record = log_ctx.records[0]
        self.assertEqual(record.levelname, "WARNING")
        message = record.getMessage()
        self.assertIn("$ref binding resolution failed", message)
        self.assertIn("recipe_id=pending", message)
        self.assertIn("missing-run", message)
        self.assertIn("results_dir", message)
        self.assertIn("QualityAssessmentTarget", message)

    def test_materialize_bindings_raises_unknown_output_name_for_ref_form(self) -> None:
        """Durable-ref bindings should fail with UnknownOutputNameError when the output is absent on a known run."""
        ref = DurableAssetRef(
            schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
            run_id="known-run",
            workflow_name="select_annotation_qc_busco",
            output_name="results_dir",
            node_name="annotation_qc_busco",
            asset_path=Path("/tmp/known-run"),
            manifest_path=Path("/tmp/known-run/run_manifest.json"),
            created_at="2026-04-20T12:00:00Z",
            run_record_path=Path("/tmp/known-run/local_run_record.json"),
            produced_type="QualityAssessmentTarget",
        )

        with self.assertRaises(UnknownOutputNameError) as exc_info:
            _materialize_bindings(
                {
                    "QualityAssessmentTarget": {
                        "$ref": {"run_id": "known-run", "output_name": "missing_output"},
                    }
                },
                durable_index=(ref,),
            )

        self.assertEqual(exc_info.exception.run_id, "known-run")
        self.assertEqual(exc_info.exception.output_name, "missing_output")
        self.assertEqual(exc_info.exception.known_outputs, ("results_dir",))
        self.assertIn("QualityAssessmentTarget", str(exc_info.exception))

    def test_materialize_bindings_resolves_ref_form(self) -> None:
        """Durable-ref bindings should resolve through the durable index to a planner dataclass."""
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "transcript_results"
            result_dir.mkdir()
            manifest_path = _write_transcript_evidence_manifest(result_dir)
            ref = DurableAssetRef(
                schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
                run_id="known-run",
                workflow_name="transcript_evidence_generation",
                output_name="results_dir",
                node_name="transcript_evidence_generation",
                asset_path=result_dir,
                manifest_path=manifest_path,
                created_at="2026-04-20T12:00:00Z",
                run_record_path=Path(tmp) / "local_run_record.json",
                produced_type="TranscriptEvidenceSet",
            )

            materialized = _materialize_bindings(
                {
                    "TranscriptEvidenceSet": {
                        "$ref": {"run_id": "known-run", "output_name": "results_dir"},
                    }
                },
                durable_index=(ref,),
            )

        self.assertIsInstance(materialized["TranscriptEvidenceSet"], TranscriptEvidenceSet)
        self.assertEqual(
            materialized["TranscriptEvidenceSet"].genome_guided_transcripts_path,
            result_dir / "trinity_gg.Trinity-GG.fasta",
        )

    def test_materialize_bindings_resolves_mixed_raw_and_ref_forms(self) -> None:
        """A single materialization call may mix raw-path and durable-ref bindings."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fasta_path = tmp_path / "custom_reference.txt"
            fasta_path.write_text("pretend biological data")
            result_dir = tmp_path / "transcript_results"
            result_dir.mkdir()
            manifest_path = _write_transcript_evidence_manifest(result_dir)
            ref = DurableAssetRef(
                schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
                run_id="known-run",
                workflow_name="transcript_evidence_generation",
                output_name="results_dir",
                node_name="transcript_evidence_generation",
                asset_path=result_dir,
                manifest_path=manifest_path,
                created_at="2026-04-20T12:00:00Z",
                run_record_path=tmp_path / "local_run_record.json",
                produced_type="TranscriptEvidenceSet",
            )

            materialized = _materialize_bindings(
                {
                    "ReferenceGenome": {"fasta_path": str(fasta_path)},
                    "TranscriptEvidenceSet": {
                        "$ref": {"run_id": "known-run", "output_name": "results_dir"},
                    },
                },
                durable_index=(ref,),
            )

        self.assertEqual(materialized["ReferenceGenome"].fasta_path, fasta_path)
        self.assertEqual(materialized["TranscriptEvidenceSet"].read_sets[0].sample_id, "sampleA")

    def test_materialize_bindings_raises_type_mismatch_for_ref_form(self) -> None:
        """Durable refs should reject incompatible binding keys before planner construction."""
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "transcript_results"
            result_dir.mkdir()
            manifest_path = _write_transcript_evidence_manifest(result_dir)
            ref = DurableAssetRef(
                schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
                run_id="known-run",
                workflow_name="transcript_evidence_generation",
                output_name="results_dir",
                node_name="transcript_evidence_generation",
                asset_path=result_dir,
                manifest_path=manifest_path,
                created_at="2026-04-20T12:00:00Z",
                run_record_path=Path(tmp) / "local_run_record.json",
                produced_type="TranscriptEvidenceSet",
            )

            with self.assertRaises(BindingTypeMismatchError) as exc_info:
                _materialize_bindings(
                    {
                        "QualityAssessmentTarget": {
                            "$ref": {"run_id": "known-run", "output_name": "results_dir"},
                        }
                    },
                    durable_index=(ref,),
                )

        self.assertEqual(exc_info.exception.binding_key, "QualityAssessmentTarget")
        self.assertEqual(exc_info.exception.resolved_type, "TranscriptEvidenceSet")
        self.assertEqual(exc_info.exception.source, "known-run")

    def test_materialize_bindings_raises_type_mismatch_for_manifest_form(self) -> None:
        """Manifest bindings should reject producers whose declared type does not match the binding key."""
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "transcript_results"
            result_dir.mkdir()
            manifest_path = _write_transcript_evidence_manifest(result_dir)

            with self.assertRaises(BindingTypeMismatchError) as exc_info:
                _materialize_bindings(
                    {
                        "QualityAssessmentTarget": {
                            "$manifest": str(manifest_path),
                            "output_name": "trinity_denovo_fasta",
                        }
                    }
                )

        self.assertEqual(exc_info.exception.binding_key, "QualityAssessmentTarget")
        self.assertEqual(exc_info.exception.resolved_type, "TranscriptEvidenceSet")
        self.assertEqual(exc_info.exception.source, str(manifest_path))

    def test_materialize_bindings_raw_path_escape_hatch_skips_type_check(self) -> None:
        """Raw-path bindings intentionally skip biology-type compatibility checks."""
        with tempfile.TemporaryDirectory() as tmp:
            odd_path = Path(tmp) / "reads.fastq"
            odd_path.write_text("@r1\nACGT\n+\n!!!!\n")

            materialized = _materialize_bindings(
                {"ReferenceGenome": {"fasta_path": str(odd_path)}},
            )

        self.assertEqual(materialized["ReferenceGenome"].fasta_path, odd_path)


class DurableIndexResolverTests(TestCase):
    """M20b checks for durable_index parameter on LocalManifestAssetResolver.resolve().

    These tests verify that a missing manifest source reports a durable-ref
    context limitation rather than failing silently, and that an existing source
    is unaffected by a matching durable ref entry.
"""

    def test_resolver_reports_missing_path_with_durable_ref_context(self) -> None:
        """When a manifest source path is missing but a matching DurableAssetRef
        is in durable_index, resolve() must return an unresolved result whose
        unresolved_requirements mention the run_id and output_name from the ref.
"""
        resolver = LocalManifestAssetResolver()
        with tempfile.TemporaryDirectory() as tmp:
            asset_path = Path(tmp) / "missing_results"
            missing_manifest = asset_path / "run_manifest.json"

            ref = DurableAssetRef(
                schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
                run_id="run-stale-abc123",
                workflow_name="select_annotation_qc_busco",
                output_name="results_dir",
                node_name="annotation_qc_busco",
                asset_path=asset_path,
                manifest_path=missing_manifest,
                created_at="2026-04-14T12:00:00Z",
                run_record_path=asset_path.parent / "local_run_record.json",
                produced_type="QualityAssessmentTarget",
            )

            result = resolver.resolve(
                "QualityAssessmentTarget",
                manifest_sources=(missing_manifest,),
                durable_index=(ref,),
            )

        self.assertFalse(result.is_resolved)
        all_messages = " ".join(result.unresolved_requirements)
        self.assertIn("run-stale-abc123", all_messages)
        self.assertIn("results_dir", all_messages)

    def test_resolver_succeeds_when_durable_ref_path_exists(self) -> None:
        """When a manifest source exists on disk, resolution must succeed
        normally even when a matching DurableAssetRef is also in durable_index.
        The durable ref must not interfere with the happy path.
"""
        resolver = LocalManifestAssetResolver()
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = Path(tmp) / "repeat_filter_results"
            result_dir.mkdir()
            (result_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow": "annotation_repeat_filtering",
                        "assumptions": [],
                        "inputs": {"reference_genome": "data/reference/genome.fa"},
                        "outputs": {
                            "all_repeats_removed_gff3": str(result_dir / "masked.gff3"),
                            "final_proteins_fasta": str(result_dir / "proteins.fa"),
                        },
                    },
                    indent=2,
                )
            )

            ref = DurableAssetRef(
                schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
                run_id="run-live-xyz",
                workflow_name="select_annotation_qc_busco",
                output_name="results_dir",
                node_name="annotation_qc_busco",
                asset_path=result_dir,
                manifest_path=result_dir / "run_manifest.json",
                created_at="2026-04-14T12:00:00Z",
                run_record_path=result_dir.parent / "local_run_record.json",
                produced_type="QualityAssessmentTarget",
            )

            result = resolver.resolve(
                "QualityAssessmentTarget",
                manifest_sources=(result_dir,),
                durable_index=(ref,),
            )

        self.assertTrue(result.is_resolved)
        self.assertIsInstance(result.resolved_value, QualityAssessmentTarget)
