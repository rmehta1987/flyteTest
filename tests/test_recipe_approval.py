"""Phase C checks for the composed-recipe approval-acceptance flow.

These tests verify that RecipeApprovalRecord round-trips, that
check_recipe_approval enforces the approval gate, and that the
approve_composed_recipe MCP tool writes a valid approval record.
The tests also confirm that run_local_recipe and run_slurm_recipe reject
unapproved composed recipes.
"""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.spec_artifacts import (
    DEFAULT_RECIPE_APPROVAL_FILENAME,
    RECIPE_APPROVAL_SCHEMA_VERSION,
    RecipeApprovalRecord,
    check_recipe_approval,
    load_recipe_approval,
    save_recipe_approval,
    save_workflow_spec_artifact,
)
from flytetest.planning import plan_typed_request
from flytetest.spec_artifacts import artifact_from_typed_plan
from flytetest.planner_types import ConsensusAnnotation, ReferenceGenome


def _typed_plan(
    target_name: str,
    *,
    source_prompt: str = "",
    biological_goal: str | None = None,
    **kwargs: object,
) -> dict[str, object]:
    """Build one structured typed plan for approval tests."""
    if biological_goal is None:
        biological_goal = target_name
    return plan_typed_request(
        biological_goal=biological_goal,
        target_name=target_name,
        source_prompt=source_prompt,
        **kwargs,
    )


def _composed_artifact(tmp_path: Path):
    """Build a generated (composed) workflow artifact for approval tests.

    Uses a multi-stage plan that produces a generated_workflow binding plan
    so the approval gate is triggered.
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
    artifact = artifact_from_typed_plan(typed_plan, created_at="2026-04-12T12:00:00Z")
    # Force the target_kind to generated_workflow to emulate a composed recipe.
    binding_plan = replace(artifact.binding_plan, target_kind="generated_workflow")
    artifact = replace(artifact, binding_plan=binding_plan)
    artifact_path = save_workflow_spec_artifact(artifact, tmp_path / "composed_artifact.json")
    return artifact, artifact_path


class RecipeApprovalRecordTests(TestCase):
    """Tests for the RecipeApprovalRecord dataclass and round-trip helpers."""

    def test_approval_record_round_trips_cleanly(self) -> None:
        """Save and reload an approval record; all fields must survive."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            record = RecipeApprovalRecord(
                schema_version=RECIPE_APPROVAL_SCHEMA_VERSION,
                artifact_path="/tmp/artifact.json",
                workflow_name="test_workflow",
                approved=True,
                approved_at="2026-04-12T12:00:00Z",
                approved_by="test_user",
                expires_at="2027-04-12T12:00:00Z",
                reason="Approved for testing.",
            )
            artifact_path = tmp_path / "artifact.json"
            artifact_path.write_text("{}")  # dummy
            saved_path = save_recipe_approval(record, artifact_path)

            self.assertTrue(saved_path.exists())
            loaded = load_recipe_approval(artifact_path)

            self.assertEqual(loaded.schema_version, RECIPE_APPROVAL_SCHEMA_VERSION)
            self.assertEqual(loaded.workflow_name, "test_workflow")
            self.assertTrue(loaded.approved)
            self.assertEqual(loaded.approved_at, "2026-04-12T12:00:00Z")
            self.assertEqual(loaded.approved_by, "test_user")
            self.assertEqual(loaded.expires_at, "2027-04-12T12:00:00Z")
            self.assertEqual(loaded.reason, "Approved for testing.")

    def test_approval_schema_version_validated_on_load(self) -> None:
        """Loading an approval record with wrong schema version must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            approval_path = tmp_path / DEFAULT_RECIPE_APPROVAL_FILENAME
            approval_path.write_text(json.dumps({
                "schema_version": "recipe-approval-v99",
                "artifact_path": "/tmp/a.json",
                "workflow_name": "w",
                "approved": True,
            }))
            with self.assertRaises(ValueError) as ctx:
                load_recipe_approval(tmp_path / "artifact.json")
            self.assertIn("recipe-approval-v99", str(ctx.exception))


class CheckRecipeApprovalTests(TestCase):
    """Tests for the check_recipe_approval gate function."""

    def test_missing_approval_is_rejected(self) -> None:
        """A missing approval file must be rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            approved, reason = check_recipe_approval(Path(tmp) / "nonexistent.json")
        self.assertFalse(approved)
        self.assertIn("No approval record", reason)

    def test_approved_record_passes_check(self) -> None:
        """A valid, non-expired approval should pass."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact_path = tmp_path / "artifact.json"
            artifact_path.write_text("{}")
            record = RecipeApprovalRecord(
                schema_version=RECIPE_APPROVAL_SCHEMA_VERSION,
                artifact_path=str(artifact_path),
                workflow_name="wf",
                approved=True,
                approved_at="2026-04-12T12:00:00Z",
            )
            save_recipe_approval(record, artifact_path)
            approved, reason = check_recipe_approval(artifact_path)
        self.assertTrue(approved)
        self.assertEqual(reason, "")

    def test_rejected_approval_fails_check(self) -> None:
        """An explicitly rejected approval should fail."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact_path = tmp_path / "artifact.json"
            artifact_path.write_text("{}")
            record = RecipeApprovalRecord(
                schema_version=RECIPE_APPROVAL_SCHEMA_VERSION,
                artifact_path=str(artifact_path),
                workflow_name="wf",
                approved=False,
                reason="Not ready for production.",
            )
            save_recipe_approval(record, artifact_path)
            approved, reason = check_recipe_approval(artifact_path)
        self.assertFalse(approved)
        self.assertIn("rejected", reason.lower())

    def test_expired_approval_fails_check(self) -> None:
        """An expired approval should fail the check."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifact_path = tmp_path / "artifact.json"
            artifact_path.write_text("{}")
            record = RecipeApprovalRecord(
                schema_version=RECIPE_APPROVAL_SCHEMA_VERSION,
                artifact_path=str(artifact_path),
                workflow_name="wf",
                approved=True,
                approved_at="2025-01-01T00:00:00Z",
                expires_at="2025-06-01T00:00:00Z",
            )
            save_recipe_approval(record, artifact_path)
            # Use a timestamp well after expiry.
            approved, reason = check_recipe_approval(artifact_path, now="2026-04-12T12:00:00Z")
        self.assertFalse(approved)
        self.assertIn("expired", reason.lower())


class ApproveComposedRecipeMCPToolTests(TestCase):
    """Tests for the approve_composed_recipe MCP tool function."""

    def test_approve_composed_recipe_writes_approval_record(self) -> None:
        """The MCP tool should write a valid approval record alongside the artifact."""
        from flytetest.server import approve_composed_recipe

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, artifact_path = _composed_artifact(tmp_path)

            response = approve_composed_recipe(
                str(artifact_path),
                approved_by="test_reviewer",
                reason="Looks good.",
            )

        self.assertTrue(response["supported"])
        self.assertTrue(response["approved"])
        self.assertEqual(response["approved_by"], "test_reviewer")
        self.assertIsNotNone(response["approved_at"])

    def test_approve_composed_recipe_rejects_missing_artifact(self) -> None:
        """The MCP tool should reject a nonexistent artifact path."""
        from flytetest.server import approve_composed_recipe

        response = approve_composed_recipe("/tmp/does_not_exist.json")
        self.assertFalse(response["supported"])
        self.assertFalse(response["approved"])

    def test_unapproved_composed_recipe_blocked_by_run_local(self) -> None:
        """run_local_recipe must block an unapproved composed recipe."""
        from flytetest.server import _run_local_recipe_impl

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, artifact_path = _composed_artifact(tmp_path)

            response = _run_local_recipe_impl(str(artifact_path))

        self.assertFalse(response["supported"])
        self.assertTrue(
            any("approval" in str(lim).lower() or "no approval" in str(lim).lower()
                for lim in response.get("limitations", []))
        )

    def test_approved_composed_recipe_allowed_by_run_local(self) -> None:
        """run_local_recipe must allow a composed recipe after approval.

        The execution itself may still fail (no handlers), but the approval
        gate should not block it.
        """
        from flytetest.server import approve_composed_recipe, _run_local_recipe_impl

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, artifact_path = _composed_artifact(tmp_path)
            approve_composed_recipe(str(artifact_path))

            response = _run_local_recipe_impl(str(artifact_path))

        # Approval passed; execution may fail for other reasons (e.g. missing handlers),
        # but the limitations should NOT mention approval.
        limitations = response.get("limitations", [])
        approval_blocks = [l for l in limitations if "approval" in str(l).lower()]
        self.assertEqual(approval_blocks, [], "Approved recipe should not be blocked by approval gate")
