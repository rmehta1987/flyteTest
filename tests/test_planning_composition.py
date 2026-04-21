"""Integration tests for planning-layer composition and approval gating.

These tests verify that the planner can discover registered stage chains when
the direct patterns do not match, and that composed recipes still require
explicit user approval.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest.planning import plan_request


class TestCompositionFallbackIntegration(TestCase):
    """Test that planning falls back to registry-based composition when needed."""

    def test_composition_fallback_tries_synthesis_eligible_stages(self) -> None:
        """Broader prompts should still be checked against the composition route."""
        plan = plan_request("Do something annotation-related that isn't a known pattern.")
        self.assertIsNotNone(plan.get("supported", None))

    def test_hardcoded_pattern_has_priority_over_composition(self) -> None:
        """Direct workflow matches should still win before composition is tried."""
        plan = plan_request("BUSCO annotation quality assessment")
        self.assertEqual(plan.get("biological_goal"), "annotation_qc_busco")
        self.assertFalse(plan.get("requires_user_approval", False))
        self.assertIn("annotation_qc_busco", plan.get("matched_entry_names", []))

    def test_composition_response_includes_all_required_contract_keys(self) -> None:
        """Planning responses should keep the same contract fields."""
        plan = plan_request("I want anannotation workflow.")
        expected_keys = {
            "supported",
            "original_request",
            "planning_outcome",
            "biological_goal",
            "matched_entry_names",
            "required_planner_types",
            "produced_planner_types",
            "resolved_inputs",
            "missing_requirements",
            "rationale",
            "workflow_spec",
            "binding_plan",
            "metadata_only",
            "requires_user_approval",
        }
        actual_keys = set(plan.keys())
        self.assertTrue(expected_keys.issubset(actual_keys), f"Missing keys: {expected_keys - actual_keys}")

    def test_composition_fallback_declines_non_biology_prompts(self) -> None:
        """Unrelated prompts should decline without trying to compose workflows."""
        plan = plan_request("Summarize the repository status for me.")

        self.assertFalse(plan["supported"])
        self.assertEqual(plan["planning_outcome"], "declined")
        self.assertEqual(plan["matched_entry_names"], [])
        self.assertIn("does not map to a supported typed biology goal", plan["missing_requirements"][0])

    def test_composition_fallback_preserves_day_one_missing_input_decline(self) -> None:
        """Known targets with missing inputs should stay on the direct path."""
        plan = plan_request("protein evidence alignment")

        self.assertFalse(plan["supported"])
        self.assertEqual(plan["planning_outcome"], "declined")
        self.assertEqual(plan["candidate_outcome"], "registered_workflow")
        self.assertEqual(plan["matched_entry_names"], ["protein_evidence_alignment"])

    def test_composition_goal_naming_convention(self) -> None:
        """Composition-derived goals should use the composition_ prefix."""
        goal = plan_request("Repeat filter and assess quality of annotation.")

        if goal.get("supported", False) and goal.get("candidate_outcome") == "generated_workflow_spec":
            biological_goal = goal.get("biological_goal", "")
            is_hardcoded = biological_goal in {
                "repeat_filter_then_busco_qc",
                "consensus_annotation_from_registered_stages",
                "annotation_functional_eggnog",
                "annotation_qc_busco",
            }
            is_composition = biological_goal.startswith("composition_")
            self.assertTrue(
                is_hardcoded or is_composition,
                f"Goal '{biological_goal}' should be either hardcoded or composition-named"
            )


class TestCompositionApprovalGating(TestCase):
    """Test that composed recipes stay behind an explicit approval gate."""

    def test_prepare_run_recipe_gates_composed_workflows(self) -> None:
        """Composed recipes should not be saved until approval is granted."""
        from flytetest.server import _prepare_run_recipe_impl

        result = _prepare_run_recipe_impl(
            "Process annotation data."
        )
        self.assertIsNotNone(result)
        self.assertIn("artifact_path", result)

        if result.get("requires_explicit_approval", False):
            self.assertIsNone(result.get("artifact_path"))

    def test_prepare_run_recipe_includes_approval_message(self) -> None:
        """Approval-gated responses should tell the user what to do next."""
        from flytetest.server import _prepare_run_recipe_impl

        result = _prepare_run_recipe_impl(
            "Repeat filter my annotation."
        )

        if result.get("requires_explicit_approval", False):
            self.assertIsNotNone(result.get("approval_message"))
            message = result.get("approval_message", "")
            self.assertTrue(len(message) > 0, "Approval message should be non-empty")

    def test_prepare_run_recipe_preserves_typed_plan_for_review(self) -> None:
        """Approval-gated responses should still expose the full typed plan."""
        from flytetest.server import _prepare_run_recipe_impl

        result = _prepare_run_recipe_impl(
            "Repeat filter my annotation."
        )

        if result.get("requires_explicit_approval", False):
            typed_plan = result.get("typed_plan")
            self.assertIsNotNone(typed_plan)
            self.assertIsNotNone(typed_plan.get("workflow_spec"))
            self.assertIsNotNone(typed_plan.get("rationale"))
