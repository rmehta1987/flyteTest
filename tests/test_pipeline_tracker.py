"""Tests for the annotation pipeline status tracker.

All tests are synthetic; no real Slurm scheduler or bioinformatics tools are
required.  Records are written with save_slurm_run_record and loaded by the
tracker under a temporary directory.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest.config import (
    ANNOTATION_WORKFLOW_NAME,
    CONSENSUS_EVM_WORKFLOW_NAME,
    REPEAT_FILTER_WORKFLOW_NAME,
    TRANSCRIPT_EVIDENCE_WORKFLOW_NAME,
)
from flytetest.pipeline_tracker import (
    ANNOTATION_PIPELINE_STAGES,
    get_annotation_pipeline_status,
    get_pipeline_summary,
)
from flytetest.registry import get_pipeline_stages
from flytetest.spec_executor import (
    SLURM_RUN_RECORD_SCHEMA_VERSION,
    SlurmRunRecord,
    save_slurm_run_record,
)


def _minimal_record(
    tmp_dir: Path,
    *,
    run_id: str = "run-001",
    workflow_name: str = ANNOTATION_WORKFLOW_NAME,
    scheduler_state: str = "submitted",
    final_scheduler_state: str | None = None,
    submitted_at: str = "2026-04-15T10:00:00Z",
    job_id: str = "99001",
) -> SlurmRunRecord:
    """Create and persist a minimal SlurmRunRecord for testing."""
    run_dir = tmp_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record = SlurmRunRecord(
        schema_version=SLURM_RUN_RECORD_SCHEMA_VERSION,
        run_id=run_id,
        recipe_id="recipe-test",
        workflow_name=workflow_name,
        artifact_path=Path("/tmp/recipe.json"),
        script_path=Path("/tmp/submit_slurm.sh"),
        stdout_path=Path("/tmp/slurm.out"),
        stderr_path=Path("/tmp/slurm.err"),
        run_record_path=run_dir / "slurm_run_record.json",
        job_id=job_id,
        execution_profile="slurm",
        scheduler_state=scheduler_state,
        final_scheduler_state=final_scheduler_state,
        submitted_at=submitted_at,
    )
    save_slurm_run_record(record)
    return record


class TestGetAnnotationPipelineStatus(TestCase):

    def test_all_pending_when_no_records(self) -> None:
        """Empty runs dir → all 15 stages reported as PENDING."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            stages = get_annotation_pipeline_status(runs_dir)

        self.assertEqual(len(stages), len(ANNOTATION_PIPELINE_STAGES))
        self.assertTrue(all(s.status == "PENDING" for s in stages))
        self.assertTrue(all(s.job_id is None for s in stages))
        self.assertTrue(all(s.run_record_path is None for s in stages))

    def test_stage_indices_are_one_based_and_sequential(self) -> None:
        """Stage index should start at 1 and be sequential."""
        with tempfile.TemporaryDirectory() as tmp:
            stages = get_annotation_pipeline_status(Path(tmp) / "empty")

        for i, stage in enumerate(stages, start=1):
            self.assertEqual(stage.stage_index, i)

    def test_completed_stage_detected(self) -> None:
        """A record with final_scheduler_state=COMPLETED maps to COMPLETED."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            _minimal_record(
                runs_dir,
                workflow_name=ANNOTATION_WORKFLOW_NAME,
                final_scheduler_state="COMPLETED",
                job_id="99010",
            )
            stages = get_annotation_pipeline_status(runs_dir)

        braker_stage = next(s for s in stages if s.workflow_name == ANNOTATION_WORKFLOW_NAME)
        self.assertEqual(braker_stage.status, "COMPLETED")
        self.assertEqual(braker_stage.job_id, "99010")
        self.assertIsNotNone(braker_stage.run_record_path)

    def test_failed_stage_maps_correctly(self) -> None:
        """A record with final_scheduler_state=FAILED maps to FAILED."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            _minimal_record(
                runs_dir,
                workflow_name=REPEAT_FILTER_WORKFLOW_NAME,
                final_scheduler_state="FAILED",
            )
            stages = get_annotation_pipeline_status(runs_dir)

        stage = next(s for s in stages if s.workflow_name == REPEAT_FILTER_WORKFLOW_NAME)
        self.assertEqual(stage.status, "FAILED")

    def test_timeout_maps_to_failed(self) -> None:
        """TIMEOUT final state should map to FAILED."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            _minimal_record(
                runs_dir,
                workflow_name=CONSENSUS_EVM_WORKFLOW_NAME,
                final_scheduler_state="TIMEOUT",
            )
            stages = get_annotation_pipeline_status(runs_dir)

        stage = next(s for s in stages if s.workflow_name == CONSENSUS_EVM_WORKFLOW_NAME)
        self.assertEqual(stage.status, "FAILED")

    def test_running_stage_detected(self) -> None:
        """A record with scheduler_state=RUNNING but no final state maps to RUNNING."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            _minimal_record(
                runs_dir,
                workflow_name=TRANSCRIPT_EVIDENCE_WORKFLOW_NAME,
                scheduler_state="RUNNING",
                final_scheduler_state=None,
            )
            stages = get_annotation_pipeline_status(runs_dir)

        stage = next(s for s in stages if s.workflow_name == TRANSCRIPT_EVIDENCE_WORKFLOW_NAME)
        self.assertEqual(stage.status, "RUNNING")

    def test_most_recent_record_wins(self) -> None:
        """When two records exist for the same workflow, the most recent wins."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            # Older record: FAILED
            _minimal_record(
                runs_dir,
                run_id="run-old",
                workflow_name=ANNOTATION_WORKFLOW_NAME,
                final_scheduler_state="FAILED",
                submitted_at="2026-04-15T08:00:00Z",
                job_id="80001",
            )
            # Newer record: COMPLETED
            _minimal_record(
                runs_dir,
                run_id="run-new",
                workflow_name=ANNOTATION_WORKFLOW_NAME,
                final_scheduler_state="COMPLETED",
                submitted_at="2026-04-15T10:00:00Z",
                job_id="80002",
            )
            stages = get_annotation_pipeline_status(runs_dir)

        stage = next(s for s in stages if s.workflow_name == ANNOTATION_WORKFLOW_NAME)
        self.assertEqual(stage.status, "COMPLETED")
        self.assertEqual(stage.job_id, "80002")


class TestGetPipelineSummary(TestCase):

    def test_summary_counts_correct(self) -> None:
        """Summary counts and percent_complete should match stage statuses."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            # Mark first 3 stages COMPLETED, 4th FAILED, 5th RUNNING
            for i, (wf, _) in enumerate(ANNOTATION_PIPELINE_STAGES[:5]):
                state = ["COMPLETED", "COMPLETED", "COMPLETED", "FAILED", None][i]
                running = ["submitted", "submitted", "submitted", "submitted", "RUNNING"][i]
                _minimal_record(
                    runs_dir,
                    run_id=f"run-{i:02d}",
                    workflow_name=wf,
                    final_scheduler_state=state,
                    scheduler_state=running,
                    submitted_at=f"2026-04-15T10:0{i}:00Z",
                )
            stages = get_annotation_pipeline_status(runs_dir)
            summary = get_pipeline_summary(stages)

        total = len(ANNOTATION_PIPELINE_STAGES)
        self.assertEqual(summary["total"], total)
        self.assertEqual(summary["completed"], 3)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["running"], 1)
        self.assertEqual(summary["pending"], total - 5)
        self.assertEqual(summary["percent_complete"], round(3 / total * 100))
        self.assertTrue(summary["has_failures"])

    def test_next_pending_stage_label(self) -> None:
        """next_pending_stage should be the label of the first PENDING stage."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            # Complete only the first two stages
            for i, (wf, _) in enumerate(ANNOTATION_PIPELINE_STAGES[:2]):
                _minimal_record(
                    runs_dir,
                    run_id=f"run-{i:02d}",
                    workflow_name=wf,
                    final_scheduler_state="COMPLETED",
                    submitted_at=f"2026-04-15T10:0{i}:00Z",
                )
            stages = get_annotation_pipeline_status(runs_dir)
            summary = get_pipeline_summary(stages)

        expected_label = ANNOTATION_PIPELINE_STAGES[2][1]
        self.assertEqual(summary["next_pending_stage"], expected_label)

    def test_next_pending_stage_is_none_when_all_complete(self) -> None:
        """next_pending_stage should be None when every stage is COMPLETED."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            for i, (wf, _) in enumerate(ANNOTATION_PIPELINE_STAGES):
                _minimal_record(
                    runs_dir,
                    run_id=f"run-{i:02d}",
                    workflow_name=wf,
                    final_scheduler_state="COMPLETED",
                    submitted_at=f"2026-04-15T10:{i:02d}:00Z",
                )
            stages = get_annotation_pipeline_status(runs_dir)
            summary = get_pipeline_summary(stages)

        self.assertIsNone(summary["next_pending_stage"])
        self.assertEqual(summary["completed"], len(ANNOTATION_PIPELINE_STAGES))
        self.assertEqual(summary["percent_complete"], 100)

    def test_all_pending_summary(self) -> None:
        """Empty runs dir should produce a fully-pending summary."""
        with tempfile.TemporaryDirectory() as tmp:
            stages = get_annotation_pipeline_status(Path(tmp) / "empty")
            summary = get_pipeline_summary(stages)

        self.assertEqual(summary["completed"], 0)
        self.assertEqual(summary["pending"], len(ANNOTATION_PIPELINE_STAGES))
        self.assertEqual(summary["percent_complete"], 0)
        self.assertFalse(summary["has_failures"])
        self.assertEqual(summary["next_pending_stage"], ANNOTATION_PIPELINE_STAGES[0][1])


class TestGetPipelineStages(TestCase):
    def test_get_pipeline_stages_returns_annotation_stages_in_order(self) -> None:
        stages = get_pipeline_stages("annotation")
        assert len(stages) == 15
        assert stages[0][0] == "transcript_evidence_generation"
        assert stages[-1][0] == "annotation_postprocess_table2asn"

    def test_get_pipeline_stages_returns_empty_for_unknown_family(self) -> None:
        assert get_pipeline_stages("unknown") == []
        assert get_pipeline_stages("") == []

    def test_standalone_workflows_excluded_from_annotation_pipeline(self) -> None:
        names = [name for name, _ in get_pipeline_stages("annotation")]
        assert "busco_assess_proteins" not in names
        assert "rnaseq_qc_quant" not in names
