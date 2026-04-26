"""Coverage for saved replayable workflow-spec artifacts.

    These tests cover metadata persistence and reloads. They do not execute saved
    specs and do not imply general runtime code generation.
"""

from __future__ import annotations

import re
import sys
import tempfile
from datetime import UTC, datetime, timezone
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import json

from flytetest.planner_types import ConsensusAnnotation, ReferenceGenome
from flytetest.planning import plan_typed_request
from flytetest.spec_artifacts import (
    DEFAULT_SPEC_ARTIFACT_FILENAME,
    DURABLE_ASSET_INDEX_SCHEMA_VERSION,
    DEFAULT_DURABLE_ASSET_INDEX_FILENAME,
    SPEC_ARTIFACT_SCHEMA_VERSION,
    DurableAssetRef,
    artifact_from_typed_plan,
    load_durable_asset_index,
    load_workflow_spec_artifact,
    make_recipe_id,
    replayable_spec_pair,
    save_durable_asset_index,
    save_workflow_spec_artifact,
)


def _typed_plan(
    target_name: str,
    *,
    source_prompt: str = "",
    biological_goal: str | None = None,
    **kwargs: object,
) -> dict[str, object]:
    """Build one structured typed plan for artifact tests."""
    if biological_goal is None:
        biological_goal = target_name
    return plan_typed_request(
        biological_goal=biological_goal,
        target_name=target_name,
        source_prompt=source_prompt,
        **kwargs,
    )


class SpecArtifactTests(TestCase):
    """Checks for saving and reloading typed planning artifacts.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_generated_workflow_spec_artifact_round_trips_from_typed_plan(self) -> None:
        """Save and reload a generated spec preview with prompt provenance.
"""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        consensus_annotation = ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=Path("results/evm/evm.out.gff3"),
        )
        prompt = "Create a generated WorkflowSpec for repeat filtering and BUSCO QC."
        typed_plan = _typed_plan(
            "repeat_filter_then_busco_qc",
            source_prompt=prompt,
            explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        )

        artifact = artifact_from_typed_plan(
            typed_plan,
            created_at="2026-04-07T12:00:00Z",
            replay_metadata={"request_id": "test-request"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_path = save_workflow_spec_artifact(artifact, Path(tmp))
            loaded = load_workflow_spec_artifact(Path(tmp))

        self.assertEqual(output_path.name, DEFAULT_SPEC_ARTIFACT_FILENAME)
        self.assertEqual(loaded, artifact)
        self.assertEqual(loaded.schema_version, SPEC_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(loaded.source_prompt, prompt)
        self.assertEqual(loaded.planning_outcome, "generated_workflow_spec")
        self.assertEqual(loaded.referenced_registered_stages, ("annotation_repeat_filtering", "annotation_qc_busco"))
        self.assertIn("repeatmasker_out", loaded.runtime_requirements[0])
        self.assertEqual(loaded.replay_metadata["request_id"], "test-request")

    def test_save_workflow_spec_artifact_creates_missing_parent_directories(self) -> None:
        """Write artifacts into a fresh nested directory without precreating it.
"""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        consensus_annotation = ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=Path("results/evm/evm.out.gff3"),
        )
        typed_plan = _typed_plan(
            "repeat_filter_then_busco_qc",
            source_prompt="Create a generated WorkflowSpec for repeat filtering and BUSCO QC.",
            explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        )
        artifact = artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / ".runtime" / "specs"
            output_path = save_workflow_spec_artifact(artifact, destination)

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.parent, destination)
            self.assertEqual(output_path.name, DEFAULT_SPEC_ARTIFACT_FILENAME)
            self.assertTrue(destination.exists())

    def test_replayable_spec_pair_does_not_reparse_prompt(self) -> None:
        """Reload the saved spec and binding plan directly for future replay work.
"""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        consensus_annotation = ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=Path("results/evm/evm.out.gff3"),
        )
        typed_plan = _typed_plan(
            "repeat_filter_then_busco_qc",
            source_prompt="Create a generated WorkflowSpec for repeat filtering and BUSCO QC.",
            explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        )
        artifact = artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")

        workflow_spec, binding_plan = replayable_spec_pair(artifact)

        self.assertEqual(workflow_spec.name, "repeat_filter_then_busco_qc")
        self.assertEqual([node.reference_name for node in workflow_spec.nodes], ["annotation_repeat_filtering", "annotation_qc_busco"])
        self.assertEqual(binding_plan.target_kind, "generated_workflow")
        self.assertEqual(binding_plan.target_name, "repeat_filter_then_busco_qc")
        self.assertIn("WorkflowSpec and BindingPlan outputs are metadata-only", binding_plan.assumptions[-1])

    def test_declined_typed_plan_cannot_be_saved(self) -> None:
        """Reject transient decline payloads as non-replayable artifacts.
"""
        typed_plan = plan_typed_request(
            biological_goal="variant calling",
            target_name="variant_calling",
        )

        with self.assertRaises(ValueError):
            artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")


class DurableAssetIndexTests(TestCase):
    """Coverage for DurableAssetRef, save_durable_asset_index, and load_durable_asset_index.

    These tests keep the M20b durable-asset model explicit and guard the
    documented index contract against regression.
"""

    def test_durable_asset_ref_round_trips_through_save_load(self) -> None:
        """A DurableAssetRef constructed with known fields must survive a full
        save/load cycle through durable_asset_index.json without losing any field.
"""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_001"
            run_dir.mkdir()
            asset_path = run_dir / "busco_results"
            manifest_path = asset_path / "run_manifest.json"
            run_record_path = run_dir / "local_run_record.json"

            ref = DurableAssetRef(
                schema_version=DURABLE_ASSET_INDEX_SCHEMA_VERSION,
                run_id="20260414T120000Z-select_annotation_qc_busco-abc123",
                workflow_name="select_annotation_qc_busco",
                output_name="results_dir",
                node_name="annotation_qc_busco",
                asset_path=asset_path,
                manifest_path=manifest_path,
                created_at="2026-04-14T12:00:00Z",
                run_record_path=run_record_path,
                produced_type="QualityAssessmentTarget",
            )

            index_path = save_durable_asset_index([ref], run_dir)
            loaded = load_durable_asset_index(run_dir)

        self.assertEqual(index_path.name, DEFAULT_DURABLE_ASSET_INDEX_FILENAME)
        self.assertEqual(len(loaded), 1)
        loaded_ref = loaded[0]
        self.assertEqual(loaded_ref.schema_version, DURABLE_ASSET_INDEX_SCHEMA_VERSION)
        self.assertEqual(loaded_ref.run_id, "20260414T120000Z-select_annotation_qc_busco-abc123")
        self.assertEqual(loaded_ref.workflow_name, "select_annotation_qc_busco")
        self.assertEqual(loaded_ref.output_name, "results_dir")
        self.assertEqual(loaded_ref.node_name, "annotation_qc_busco")
        self.assertEqual(loaded_ref.asset_path, asset_path)
        self.assertEqual(loaded_ref.manifest_path, manifest_path)
        self.assertEqual(loaded_ref.created_at, "2026-04-14T12:00:00Z")
        self.assertEqual(loaded_ref.run_record_path, run_record_path)
        self.assertEqual(loaded_ref.produced_type, "QualityAssessmentTarget")

    def test_load_durable_asset_index_returns_empty_for_missing_file(self) -> None:
        """load_durable_asset_index must return [] without raising when there
        is no durable_asset_index.json in the directory.
"""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_legacy"
            run_dir.mkdir()

            result = load_durable_asset_index(run_dir)

        self.assertEqual(result, [])

    def test_durable_asset_index_schema_version_is_validated(self) -> None:
        """load_durable_asset_index must raise ValueError when schema_version
        does not match the current DURABLE_ASSET_INDEX_SCHEMA_VERSION.
"""
        import json
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_stale"
            run_dir.mkdir()
            index_path = run_dir / DEFAULT_DURABLE_ASSET_INDEX_FILENAME
            stale_payload = {
                "schema_version": "durable-asset-index-v0-stale",
                "run_id": "old-run",
                "workflow_name": "old_wf",
                "entries": [],
            }
            index_path.write_text(json.dumps(stale_payload))

            with self.assertRaises(ValueError) as ctx:
                load_durable_asset_index(run_dir)

        self.assertIn("durable-asset-index-v0-stale", str(ctx.exception))


class ToolDatabasesTests(TestCase):
    """Step-06 tests: WorkflowSpec.tool_databases round-trips and BC defaults."""

    # Minimal plan for constructing artifacts without calling plan_typed_request.
    _WORKFLOW_SPEC_BASE: dict = {
        "name": "test_wf",
        "analysis_goal": "test",
        "inputs": [],
        "outputs": [],
        "nodes": [],
        "edges": [],
        "ordering_constraints": [],
        "fanout_behavior": [],
        "fanin_behavior": [],
        "reusable_registered_refs": [],
        "final_output_bindings": [],
        "default_execution_profile": None,
        "replay_metadata": {},
        "generated_entity_record": None,
        "metadata_only": True,
    }
    _BINDING_PLAN_BASE: dict = {
        "target_name": "test_wf",
        "target_kind": "workflow",
        "explicit_user_bindings": {},
        "resolved_prior_assets": {},
        "manifest_derived_paths": {},
        "execution_profile": None,
        "resource_spec": None,
        "runtime_image": None,
        "runtime_bindings": {},
        "unresolved_requirements": [],
        "assumptions": [],
        "metadata_only": True,
    }
    _ARTIFACT_BASE: dict = {
        "schema_version": SPEC_ARTIFACT_SCHEMA_VERSION,
        "source_prompt": "test prompt",
        "biological_goal": "test_goal",
        "planning_outcome": "supported",
        "candidate_outcome": "supported",
        "referenced_registered_stages": [],
        "assumptions": [],
        "runtime_requirements": [],
        "created_at": "2026-01-01T00:00:00Z",
        "replay_metadata": {},
        "metadata_only": True,
    }

    def _make_artifact_payload(self, tool_databases: dict | None = None) -> dict:
        """Build a minimal SavedWorkflowSpecArtifact payload dict."""
        spec = dict(self._WORKFLOW_SPEC_BASE)
        if tool_databases is not None:
            spec["tool_databases"] = tool_databases
        return {
            **self._ARTIFACT_BASE,
            "workflow_spec": spec,
            "binding_plan": dict(self._BINDING_PLAN_BASE),
        }

    def test_round_trip_with_tool_databases(self) -> None:
        """tool_databases is preserved through save_workflow_spec_artifact + load."""
        payload = self._make_artifact_payload(tool_databases={"busco_lineage_dir": "/x/y"})
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(json.dumps(payload, indent=2) + "\n")
            loaded = load_workflow_spec_artifact(artifact_path)

        self.assertEqual(loaded.workflow_spec.tool_databases, {"busco_lineage_dir": "/x/y"})

    def test_load_old_artifact_without_tool_databases_defaults_to_empty(self) -> None:
        """An artifact JSON that predates tool_databases loads without raising and
        gives an empty dict — the hard constraint against rewriting frozen artifacts."""
        payload = self._make_artifact_payload()          # no tool_databases key
        self.assertNotIn("tool_databases", payload["workflow_spec"])

        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(json.dumps(payload, indent=2) + "\n")
            loaded = load_workflow_spec_artifact(artifact_path)

        self.assertEqual(loaded.workflow_spec.tool_databases, {})

    def test_artifact_from_typed_plan_wires_tool_databases(self) -> None:
        """artifact_from_typed_plan populates workflow_spec.tool_databases from the plan."""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        consensus_annotation = ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=Path("results/evm/evm.out.gff3"),
        )
        typed_plan = _typed_plan(
            "repeat_filter_then_busco_qc",
            source_prompt="Create a generated WorkflowSpec for repeat filtering and BUSCO QC.",
            explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        )
        # Inject tool_databases into the workflow_spec sub-dict (simulates Step 21/22
        # passing the resolved value from the bundle or explicit kwarg).
        typed_plan["workflow_spec"]["tool_databases"] = {"eggnog_db": "/data/eggnog/5.0"}

        artifact = artifact_from_typed_plan(typed_plan, created_at="2026-01-01T00:00:00Z")

        self.assertEqual(
            artifact.workflow_spec.tool_databases,
            {"eggnog_db": "/data/eggnog/5.0"},
        )

    def test_artifact_from_typed_plan_top_level_tool_databases_fallback(self) -> None:
        """Top-level tool_databases in the plan dict fills the gap when absent
        from workflow_spec (§8 fallback wiring)."""
        reference_genome = ReferenceGenome(fasta_path=Path("data/braker3/reference/genome.fa"))
        consensus_annotation = ConsensusAnnotation(
            reference_genome=reference_genome,
            annotation_gff3_path=Path("results/evm/evm.out.gff3"),
        )
        typed_plan = _typed_plan(
            "repeat_filter_then_busco_qc",
            source_prompt="Create a generated WorkflowSpec for repeat filtering and BUSCO QC.",
            explicit_bindings={"ConsensusAnnotation": consensus_annotation},
        )
        # Remove from workflow_spec (simulate old plan format), put at top level.
        typed_plan["workflow_spec"].pop("tool_databases", None)
        typed_plan["tool_databases"] = {"busco_lineage": "/data/busco/lineages/eukaryota_odb10"}

        artifact = artifact_from_typed_plan(typed_plan, created_at="2026-01-01T00:00:00Z")

        self.assertEqual(
            artifact.workflow_spec.tool_databases,
            {"busco_lineage": "/data/busco/lineages/eukaryota_odb10"},
        )


_RECIPE_ID_PATTERN = re.compile(r"^\d{8}T\d{6}\.\d{3}Z-.+$")


class RecipeIdTests(TestCase):
    """Step-07 tests: make_recipe_id format and filesystem integration."""

    def _fixed_now(self, millis: int = 123) -> datetime:
        return datetime(2026, 4, 20, 12, 34, 56, millis * 1000, tzinfo=UTC)

    def test_format_matches_pattern(self) -> None:
        rid = make_recipe_id("exonerate_align_chunk", now=self._fixed_now())
        self.assertRegex(rid, r"^\d{8}T\d{6}\.\d{3}Z-exonerate_align_chunk$")

    def test_format_timestamp_values(self) -> None:
        rid = make_recipe_id("busco_assess_proteins", now=self._fixed_now(42))
        self.assertTrue(rid.startswith("20260420T123456.042Z-"))

    def test_target_name_slug_sanitization(self) -> None:
        rid = make_recipe_id("My Workflow / V2", now=self._fixed_now())
        self.assertRegex(rid, _RECIPE_ID_PATTERN)
        self.assertNotIn(" ", rid)
        self.assertNotIn("/", rid)

    def test_composition_sentinel_prefix(self) -> None:
        target = "composed-annotation_repeat_filtering_to_annotation_qc_busco"
        rid = make_recipe_id(target, now=self._fixed_now())
        self.assertIn("composed-", rid)
        self.assertRegex(rid, _RECIPE_ID_PATTERN)

    def test_distinct_timestamps_produce_distinct_ids(self) -> None:
        rid1 = make_recipe_id("exonerate_align_chunk", now=self._fixed_now(100))
        rid2 = make_recipe_id("exonerate_align_chunk", now=self._fixed_now(200))
        self.assertNotEqual(rid1, rid2)
        self.assertIn(".100Z-", rid1)
        self.assertIn(".200Z-", rid2)

    def test_filesystem_roundtrip(self) -> None:
        """Artifact saved at <recipe_id>.json has recipe_id == artifact_path.stem."""
        from flytetest.specs import BindingPlan, WorkflowSpec
        from flytetest.spec_artifacts import SavedWorkflowSpecArtifact

        rid = make_recipe_id("protein_evidence_alignment", now=self._fixed_now())
        spec = WorkflowSpec(
            name="protein_evidence_alignment",
            analysis_goal="test",
            inputs=(), outputs=(), nodes=(), edges=(),
        )
        artifact = SavedWorkflowSpecArtifact(
            schema_version=SPEC_ARTIFACT_SCHEMA_VERSION,
            workflow_spec=spec,
            binding_plan=BindingPlan(target_name="protein_evidence_alignment", target_kind="task"),
            source_prompt="test",
            biological_goal="test",
            planning_outcome="supported",
            candidate_outcome="supported",
            referenced_registered_stages=(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / f"{rid}.json"
            save_workflow_spec_artifact(artifact, artifact_path)
            loaded = load_workflow_spec_artifact(artifact_path)
            self.assertEqual(artifact_path.stem, rid)
            self.assertEqual(loaded.workflow_spec.name, "protein_evidence_alignment")
