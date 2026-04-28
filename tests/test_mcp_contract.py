"""Tests for the FLyteTest MCP contract module (Step 27).

Covers:
- Every registered server tool has a description in TOOL_DESCRIPTIONS.
- No description references removed helpers.
- run_task / run_workflow / run_slurm_recipe descriptions contain the
  queue/account handoff sentence.
- Tool group membership is queryable via the group constants, and
  MCP_TOOL_NAMES order reflects experiment-loop → inspect → lifecycle.
"""

from unittest import TestCase

from flytetest.mcp_contract import (
    EXPERIMENT_LOOP_TOOLS,
    INSPECT_TOOLS,
    LIFECYCLE_TOOLS,
    MCP_TOOL_NAMES,
    QUEUE_ACCOUNT_HANDOFF,
    RUN_SLURM_RECIPE_TOOL_NAME,
    RUN_TASK_TOOL_NAME,
    RUN_WORKFLOW_TOOL_NAME,
    SUPPORTED_TASK_NAMES,
    SUPPORTED_WORKFLOW_NAMES,
    TOOL_DESCRIPTIONS,
)


def _registered_tool_names() -> list[str]:
    """Return the names of all tools registered in create_mcp_server()."""
    from flytetest.server import create_mcp_server

    registered: list[str] = []

    class _CaptureMCP:
        def __init__(self, name: str) -> None:
            pass

        def tool(self, *, description: str | None = None, **_kw):  # type: ignore[override]
            def decorator(fn):  # type: ignore[return]
                registered.append(fn.__name__)
                return fn

            return decorator

        def resource(self, *_a, **_kw):  # type: ignore[override]
            def decorator(fn):  # type: ignore[return]
                return fn

            return decorator

    create_mcp_server(fastmcp_cls=_CaptureMCP)
    return registered


class ToolDescriptionCoverageTests(TestCase):
    """Every registered tool must have a description in TOOL_DESCRIPTIONS."""

    def test_all_registered_tools_have_descriptions(self) -> None:
        """No orphaned tools — every name in create_mcp_server has an entry in TOOL_DESCRIPTIONS."""
        registered = _registered_tool_names()
        missing = [name for name in registered if name not in TOOL_DESCRIPTIONS]
        self.assertEqual(
            missing,
            [],
            msg=f"Registered tools missing from TOOL_DESCRIPTIONS: {missing}",
        )

    def test_no_removed_helper_references(self) -> None:
        """Descriptions must not reference helpers removed during the reshape."""
        removed_helpers = (
            "_extract_prompt_paths",
            "_classify_target",
            "task_inputs",
        )
        for name, description in TOOL_DESCRIPTIONS.items():
            for helper in removed_helpers:
                self.assertNotIn(
                    helper,
                    description,
                    msg=f"TOOL_DESCRIPTIONS[{name!r}] still references removed helper {helper!r}",
                )


class QueueAccountHandoffTests(TestCase):
    """run_task, run_workflow, and run_slurm_recipe must carry the handoff sentence."""

    _TOOLS_REQUIRING_HANDOFF = (RUN_TASK_TOOL_NAME, RUN_WORKFLOW_TOOL_NAME, RUN_SLURM_RECIPE_TOOL_NAME)

    def test_handoff_sentence_present_in_required_tools(self) -> None:
        for tool_name in self._TOOLS_REQUIRING_HANDOFF:
            with self.subTest(tool=tool_name):
                self.assertIn(
                    QUEUE_ACCOUNT_HANDOFF,
                    TOOL_DESCRIPTIONS[tool_name],
                    msg=f"TOOL_DESCRIPTIONS[{tool_name!r}] is missing the queue/account handoff sentence",
                )


class ToolGroupOrderTests(TestCase):
    """MCP_TOOL_NAMES order must reflect experiment-loop → inspect → lifecycle."""

    def test_group_constants_cover_all_mcp_tool_names(self) -> None:
        from flytetest.mcp_contract import FLAT_TOOLS
        all_grouped = set(EXPERIMENT_LOOP_TOOLS) | set(FLAT_TOOLS) | set(INSPECT_TOOLS) | set(LIFECYCLE_TOOLS)
        extra_in_names = set(MCP_TOOL_NAMES) - all_grouped
        extra_in_groups = all_grouped - set(MCP_TOOL_NAMES)
        self.assertEqual(extra_in_names, set(), msg=f"MCP_TOOL_NAMES has tools not in any group: {extra_in_names}")
        self.assertEqual(extra_in_groups, set(), msg=f"Group constants have tools not in MCP_TOOL_NAMES: {extra_in_groups}")

    def test_mcp_tool_names_ordered_by_group(self) -> None:
        """MCP_TOOL_NAMES must list all experiment-loop tools before any inspect tool,
        and all inspect tools before any lifecycle tool."""
        names = list(MCP_TOOL_NAMES)
        experiment_indices = [names.index(t) for t in EXPERIMENT_LOOP_TOOLS if t in names]
        inspect_indices = [names.index(t) for t in INSPECT_TOOLS if t in names]
        lifecycle_indices = [names.index(t) for t in LIFECYCLE_TOOLS if t in names]
        self.assertLess(
            max(experiment_indices),
            min(inspect_indices),
            msg="All experiment-loop tools must appear before any inspect tool in MCP_TOOL_NAMES",
        )
        self.assertLess(
            max(inspect_indices),
            min(lifecycle_indices),
            msg="All inspect tools must appear before any lifecycle tool in MCP_TOOL_NAMES",
        )

    def test_run_task_and_run_workflow_in_experiment_loop(self) -> None:
        self.assertIn(RUN_TASK_TOOL_NAME, EXPERIMENT_LOOP_TOOLS)
        self.assertIn(RUN_WORKFLOW_TOOL_NAME, EXPERIMENT_LOOP_TOOLS)

    def test_run_slurm_recipe_in_inspect_group(self) -> None:
        self.assertIn(RUN_SLURM_RECIPE_TOOL_NAME, INSPECT_TOOLS)


class VariantCallingMcpSurfaceTests(TestCase):
    """Milestone I: verify variant_calling targets are reachable through the MCP surface."""

    _WORKFLOW_NAMES = [
        "prepare_reference",
        "preprocess_sample",
        "germline_short_variant_discovery",
        "genotype_refinement",
        "preprocess_sample_from_ubam",
        "sequential_interval_haplotype_caller",
        "post_genotyping_refinement",
        # Milestone I new workflows
        "small_cohort_filter",
        "pre_call_coverage_qc",
        "post_call_qc_summary",
        "annotate_variants_snpeff",
    ]

    _TASK_NAMES = [
        "create_sequence_dictionary",
        "index_feature_file",
        "base_recalibrator",
        "apply_bqsr",
        "haplotype_caller",
        "combine_gvcfs",
        "joint_call_gvcfs",
        # Milestone I ported tasks (now exposed)
        "bwa_mem2_index",
        "bwa_mem2_mem",
        "sort_sam",
        "mark_duplicates",
        "variant_recalibrator",
        "apply_vqsr",
        "merge_bam_alignment",
        "gather_vcfs",
        "calculate_genotype_posteriors",
        # Milestone I new tasks
        "variant_filtration",
        "collect_wgs_metrics",
        "bcftools_stats",
        "multiqc_summarize",
        "snpeff_annotate",
    ]

    def test_variant_calling_workflows_in_supported_names(self) -> None:
        """All 11 variant_calling workflow names are in SUPPORTED_WORKFLOW_NAMES."""
        for name in self._WORKFLOW_NAMES:
            self.assertIn(name, SUPPORTED_WORKFLOW_NAMES, f"{name} not in SUPPORTED_WORKFLOW_NAMES")

    def test_variant_calling_tasks_in_supported_names(self) -> None:
        """All variant_calling task names (Milestones A–I) are in SUPPORTED_TASK_NAMES."""
        for name in self._TASK_NAMES:
            self.assertIn(name, SUPPORTED_TASK_NAMES, f"{name} not in SUPPORTED_TASK_NAMES")

    def test_scattered_haplotype_caller_removed(self) -> None:
        """scattered_haplotype_caller must no longer appear in SUPPORTED_WORKFLOW_NAMES (renamed to sequential_interval_haplotype_caller)."""
        self.assertNotIn("scattered_haplotype_caller", SUPPORTED_WORKFLOW_NAMES)
