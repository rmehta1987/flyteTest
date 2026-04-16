"""Tests for bounded composition of registered workflows and tasks.

This module exercises the Milestone 15 composition path that turns registry
compatibility metadata into short, reviewable workflow specs.
"""

import unittest
from pathlib import Path

from flytetest.composition import (
    CompositionDeclineReason,
    compose_workflow_path,
    bundle_composition_into_workflow_spec,
    DEFAULT_MAX_COMPOSITION_DEPTH,
)
from flytetest.registry import get_entry


class TestCompositionPathFinding(unittest.TestCase):
    """Test how the planner finds short stage paths from the registry."""

    def test_single_stage_path_with_valid_entry(self) -> None:
        """A valid registered stage should produce at least one path entry."""
        path, decline = compose_workflow_path("annotation_qc_busco")
        self.assertIsNone(decline, f"Composition should succeed, but got: {decline}")
        self.assertGreater(len(path), 0, "Path should not be empty")
        self.assertIn("annotation_qc_busco", path, "BUSCO should be in the path")

    def test_compose_from_repeat_filtering_toward_busco(self) -> None:
        """A stage that already produces the target type should not be extended."""
        path, decline = compose_workflow_path(
            "annotation_repeat_filtering",
            target_output_type="QualityAssessmentTarget",
        )
        self.assertIsNone(decline, f"Composition declined: {decline}")
        self.assertEqual(path, ("annotation_repeat_filtering",))

    def test_compose_repeat_filtering_find_successors(self) -> None:
        """A broader request should extend beyond the starting stage when possible."""
        path, decline = compose_workflow_path("annotation_repeat_filtering")
        self.assertIsNone(decline, f"Composition declined: {decline}")
        self.assertGreater(len(path), 1, "Path should extend beyond just repeat filtering")
        self.assertIn("annotation_repeat_filtering", path)

    def test_compose_with_depth_limit(self) -> None:
        """Composition should stop once it reaches the configured depth."""
        path, decline = compose_workflow_path(
            "annotation_repeat_filtering",
            max_depth=2,
        )
        self.assertIsNone(decline)
        self.assertLessEqual(len(path), 2)

    def test_unsupported_start_entry_declines(self) -> None:
        """Unknown registry entries should decline with a clear reason."""
        path, decline = compose_workflow_path("nonexistent_workflow")
        self.assertEqual(path, ())
        self.assertIsNotNone(decline)
        self.assertEqual(decline.category, "unsupported_stage")
        self.assertIn("not found", decline.message)

    def test_non_synthesis_eligible_entry_declines(self) -> None:
        """Entries that are not allowed to seed composition should decline."""
        try:
            entry = get_entry("consensus_annotation_evm_prep")
            if not entry.compatibility.synthesis_eligible:
                path, decline = compose_workflow_path("consensus_annotation_evm_prep")
                self.assertEqual(path, ())
                self.assertIsNotNone(decline)
                self.assertEqual(decline.category, "not_composition_eligible")
        except KeyError:
            self.skipTest("Test requires specific registry entries")

    def test_deadend_stage_terminates_gracefully(self) -> None:
        """A dead end should return the path built so far instead of failing."""
        path, decline = compose_workflow_path("ab_initio_annotation_braker3")
        self.assertIsNone(decline)
        self.assertGreater(len(path), 0)


class TestCompositionBundling(unittest.TestCase):
    """Test turning a stage path into a frozen workflow spec."""

    def test_bundle_single_entry_composition(self) -> None:
        """A one-stage path should bundle into a pass-through spec."""
        spec, decline = bundle_composition_into_workflow_spec(
            ("annotation_qc_busco",),
            biological_intent="Run BUSCO quality assessment.",
        )
        self.assertIsNone(decline)
        self.assertIsNotNone(spec)
        self.assertEqual(len(spec.nodes), 1)
        self.assertEqual(len(spec.edges), 0)
        self.assertIn("busco", spec.nodes[0].reference_name)

    def test_bundle_multi_entry_composition(self) -> None:
        """A multi-stage path should bundle into connected nodes and edges."""
        spec, decline = bundle_composition_into_workflow_spec(
            ("annotation_repeat_filtering", "annotation_qc_busco"),
            biological_intent="Filter repeats and assess with BUSCO.",
        )
        self.assertIsNone(decline)
        self.assertIsNotNone(spec)
        self.assertEqual(len(spec.nodes), 2)
        self.assertEqual(len(spec.edges), 1)
        self.assertEqual(spec.edges[0].source_node, "stage_0")
        self.assertEqual(spec.edges[0].target_node, "stage_1")

    def test_bundle_respects_ordering_constraints(self) -> None:
        """Bundled specs should record the required stage order."""
        spec, decline = bundle_composition_into_workflow_spec(
            ("annotation_repeat_filtering", "annotation_qc_busco", "annotation_functional_eggnog"),
            biological_intent="Multi-stage annotation.",
        )
        self.assertIsNone(decline)
        self.assertIsNotNone(spec)
        self.assertGreater(len(spec.ordering_constraints), 0)

    def test_bundle_empty_path_declines(self) -> None:
        """An empty path should be rejected with a clear decline reason."""
        spec, decline = bundle_composition_into_workflow_spec(
            (),
            biological_intent="Empty composition.",
        )
        self.assertIsNone(spec)
        self.assertIsNotNone(decline)
        self.assertEqual(decline.category, "empty_composition")

    def test_bundle_creates_proper_output_bindings(self) -> None:
        """The final output binding should point at the last stage."""
        spec, decline = bundle_composition_into_workflow_spec(
            ("annotation_repeat_filtering", "annotation_qc_busco"),
            biological_intent="Test.",
        )
        self.assertIsNone(decline)
        self.assertIsNotNone(spec)
        self.assertGreater(len(spec.final_output_bindings), 0)
        final_binding = spec.final_output_bindings[0]
        self.assertEqual(final_binding.source_node, f"stage_{len(spec.nodes) - 1}")

    def test_bundle_with_invalid_stage_declines(self) -> None:
        """Unknown stages in the path should produce a decline."""
        spec, decline = bundle_composition_into_workflow_spec(
            ("annotation_repeat_filtering", "nonexistent_stage"),
            biological_intent="Test.",
        )
        self.assertIsNone(spec)
        self.assertIsNotNone(decline)
        self.assertEqual(decline.category, "invalid_stage")


class TestCompositionIntegration(unittest.TestCase):
    """Integration tests that cover path finding plus bundling."""

    def test_find_and_bundle_repeat_to_busco(self) -> None:
        """A discovered path should also bundle into a spec."""
        path, find_decline = compose_workflow_path("annotation_repeat_filtering")
        self.assertIsNone(find_decline)
        self.assertIn("annotation_repeat_filtering", path)

        spec, bundle_decline = bundle_composition_into_workflow_spec(
            path,
            biological_intent="Repeat filtering and quality assessment.",
        )
        self.assertIsNone(bundle_decline)
        self.assertIsNotNone(spec)
        self.assertGreaterEqual(len(spec.nodes), 1)
        self.assertIn("composition_type", spec.replay_metadata)

    def test_composition_paths_are_listed_in_spec_metadata(self) -> None:
        """Composed specs should record their length and type in metadata."""
        spec, decline = bundle_composition_into_workflow_spec(
            ("annotation_repeat_filtering", "annotation_qc_busco"),
            biological_intent="Test.",
        )
        self.assertIsNone(decline)
        self.assertIsNotNone(spec)
        self.assertEqual(spec.replay_metadata["path_length"], 2)
        self.assertIn("registry_constrained", spec.replay_metadata["composition_type"])


class TestCompositionDeclineReasons(unittest.TestCase):
    """Test that composition declines stay specific and readable."""

    def test_decline_reason_has_category(self) -> None:
        """Every decline should use a known category."""
        path, decline = compose_workflow_path("nonexistent_entry")
        self.assertIsNotNone(decline)
        self.assertIn(
            decline.category,
            frozenset({
                "unsupported_stage",
                "not_composition_eligible",
                "cycle_detected",
                "target_unreachable",
                "empty_composition",
                "invalid_stage",
            }),
        )

    def test_decline_reason_has_message(self) -> None:
        """All decline reasons should have a human-readable message."""
        path, decline = compose_workflow_path("nonexistent_entry")
        self.assertIsNotNone(decline)
        self.assertTrue(len(decline.message) > 0)

    def test_decline_reason_suggests_alternatives_when_available(self) -> None:
        """Decline reasons should suggest alternatives when relevant."""
        # This is a best-effort check because alternative suggestions depend on registry state.
        path, decline = compose_workflow_path("nonexistent_entry")
        if decline and "alternative" in decline.category.lower():
            for alt in decline.suggested_alternatives:
                try:
                    get_entry(alt)
                except KeyError:
                    self.fail(f"Suggested alternative `{alt}` is not in registry")


if __name__ == "__main__":
    unittest.main()
