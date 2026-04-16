"""Tests for the background Slurm monitoring module.

These tests cover:
- Batched Slurm output parsing (``_parse_batch_squeue_output``,
  ``_parse_batch_sacct_output``)
- The ``batch_query_slurm_job_states`` helper with mocked subprocess calls
- ``discover_active_slurm_run_dirs`` scanning behaviour
- ``reconcile_active_slurm_jobs`` end-to-end with mocked scheduler output
- File-locking helpers (``save_slurm_run_record_locked``,
  ``load_slurm_run_record_locked``) for correct serialization and round-trips
- The ``slurm_poll_loop`` async lifecycle: starts, survives a poll error,
  and shuts down cleanly on cancellation

All tests are offline-friendly.  Subprocess calls are replaced by synchronous
callables that return pre-built ``CompletedProcess`` objects.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock, patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.spec_executor import (
    DEFAULT_SLURM_RUN_RECORD_FILENAME,
    SLURM_RUN_RECORD_SCHEMA_VERSION,
    SlurmRetryPolicy,
    SlurmRunRecord,
    load_slurm_run_record,
    save_slurm_run_record,
)
from flytetest.slurm_monitor import (
    SlurmPollingConfig,
    _parse_batch_sacct_output,
    _parse_batch_squeue_output,
    batch_query_slurm_job_states,
    discover_active_slurm_run_dirs,
    load_slurm_run_record_locked,
    reconcile_active_slurm_jobs,
    save_slurm_run_record_locked,
    slurm_poll_loop,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _minimal_slurm_record(run_dir: Path, *, job_id: str = "99001", state: str = "RUNNING") -> SlurmRunRecord:
    """Return a minimal ``SlurmRunRecord`` written into ``run_dir``.

    The record has only the fields required for parsing and monitoring tests.
    All path fields point inside ``run_dir`` so tests stay under the tmp tree.

    Args:
        run_dir: Temporary directory for this run's files.
        job_id: Slurm job identifier to embed in the record.
        state: Initial ``scheduler_state`` to embed.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    record = SlurmRunRecord(
        schema_version=SLURM_RUN_RECORD_SCHEMA_VERSION,
        run_id="test-run-1",
        recipe_id="recipe",
        workflow_name="annotation_qc_busco",
        artifact_path=run_dir / "recipe.json",
        script_path=run_dir / "submit_slurm.sh",
        stdout_path=run_dir / "slurm-%j.out",
        stderr_path=run_dir / "slurm-%j.err",
        run_record_path=run_dir / DEFAULT_SLURM_RUN_RECORD_FILENAME,
        job_id=job_id,
        execution_profile="slurm",
        scheduler_state=state,
        retry_policy=SlurmRetryPolicy(),
    )
    save_slurm_run_record(record)
    return record


def _make_proc(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Build a fake ``CompletedProcess`` for scheduler command mocking.

    Args:
        stdout: Simulated command standard output.
        stderr: Simulated command standard error.
        returncode: Exit code to report.
    """
    return subprocess.CompletedProcess(  # type: ignore[type-arg]
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Batch squeue output parsing
# ---------------------------------------------------------------------------


class TestParseBatchSqueueOutput(TestCase):
    """Unit tests for ``_parse_batch_squeue_output``."""

    def test_parses_single_running_job(self) -> None:
        """Return the correct state for a single job in squeue output."""
        result = _parse_batch_squeue_output("99001 RUNNING\n")
        self.assertEqual(result, {"99001": "RUNNING"})

    def test_parses_multiple_jobs(self) -> None:
        """Return all jobs from multi-line squeue output."""
        stdout = "99001 RUNNING\n99002 PENDING\n99003 COMPLETED\n"
        result = _parse_batch_squeue_output(stdout)
        self.assertEqual(result, {"99001": "RUNNING", "99002": "PENDING", "99003": "COMPLETED"})

    def test_skips_header_line(self) -> None:
        """Skip the JOBID header line that squeue sometimes emits."""
        stdout = "JOBID STATE\n99001 FAILED\n"
        result = _parse_batch_squeue_output(stdout)
        self.assertNotIn("JOBID", result)
        self.assertEqual(result["99001"], "FAILED")

    def test_empty_output_returns_empty_dict(self) -> None:
        """Return an empty dict when squeue produced no output."""
        self.assertEqual(_parse_batch_squeue_output(""), {})

    def test_normalises_state_case(self) -> None:
        """Normalise scheduler states to uppercase regardless of source case."""
        result = _parse_batch_squeue_output("99001 running\n")
        self.assertEqual(result["99001"], "RUNNING")

    def test_ignores_lines_with_too_few_tokens(self) -> None:
        """Silently skip malformed lines that have fewer than two tokens."""
        stdout = "99001\n99002 PENDING\n"
        result = _parse_batch_squeue_output(stdout)
        self.assertNotIn("99001", result)
        self.assertIn("99002", result)


# ---------------------------------------------------------------------------
# Batch sacct output parsing
# ---------------------------------------------------------------------------


class TestParseBatchSacctOutput(TestCase):
    """Unit tests for ``_parse_batch_sacct_output``."""

    def test_parses_single_job(self) -> None:
        """Extract state and exit code for a single job line."""
        stdout = "99001|COMPLETED|0:0\n"
        result = _parse_batch_sacct_output(stdout)
        self.assertIn("99001", result)
        self.assertEqual(result["99001"]["State"], "COMPLETED")
        self.assertEqual(result["99001"]["ExitCode"], "0:0")

    def test_prefers_bare_job_row_over_batch_step(self) -> None:
        """Prefer the bare ``JobID`` row over the ``.batch`` step row."""
        stdout = "99001.batch|COMPLETED|0:0\n99001|FAILED|1:0\n"
        result = _parse_batch_sacct_output(stdout)
        self.assertEqual(result["99001"]["State"], "FAILED")

    def test_falls_back_to_first_row_when_no_bare_id(self) -> None:
        """Use the first available row when no bare JobID row exists."""
        stdout = "99001.batch|COMPLETED|0:0\n"
        result = _parse_batch_sacct_output(stdout)
        self.assertIn("99001", result)
        self.assertEqual(result["99001"]["State"], "COMPLETED")

    def test_handles_multiple_jobs(self) -> None:
        """Parse multiple jobs from a single sacct output block."""
        stdout = (
            "99001|COMPLETED|0:0\n"
            "99001.batch|COMPLETED|0:0\n"
            "99002|FAILED|1:0\n"
            "99002.batch|FAILED|1:0\n"
        )
        result = _parse_batch_sacct_output(stdout)
        self.assertEqual(result["99001"]["State"], "COMPLETED")
        self.assertEqual(result["99002"]["State"], "FAILED")

    def test_skips_header_line(self) -> None:
        """Skip the JOBID header row."""
        stdout = "JobID|State|ExitCode\n99001|RUNNING|0:0\n"
        result = _parse_batch_sacct_output(stdout)
        self.assertNotIn("JobID", result)
        self.assertIn("99001", result)

    def test_empty_output_returns_empty_dict(self) -> None:
        """Return empty dict for empty sacct output."""
        self.assertEqual(_parse_batch_sacct_output(""), {})


# ---------------------------------------------------------------------------
# Batch query (with mocked subprocess)
# ---------------------------------------------------------------------------


class TestBatchQuerySlurmJobStates(TestCase):
    """Tests for ``batch_query_slurm_job_states`` with injected runners."""

    def _runner_for(self, squeue_stdout: str, sacct_stdout: str) -> MagicMock:
        """Return a mock scheduler_runner that dispatches by command name.

        Args:
            squeue_stdout: Canned output to return for ``squeue`` calls.
            sacct_stdout: Canned output to return for ``sacct`` calls.
        """
        def side_effect(args, **_kwargs):  # noqa: ANN001
            if args[0] == "squeue":
                return _make_proc(stdout=squeue_stdout)
            if args[0] == "sacct":
                return _make_proc(stdout=sacct_stdout)
            return _make_proc()

        mock = MagicMock(side_effect=side_effect)
        return mock

    def test_empty_job_list_returns_empty_dict(self) -> None:
        """Return an empty dict immediately when no job IDs are requested."""
        result = batch_query_slurm_job_states(
            [],
            scheduler_runner=MagicMock(),
            command_available=lambda _: True,
        )
        self.assertEqual(result, {})

    def test_combines_squeue_and_sacct_state(self) -> None:
        """Prefer squeue state when both commands return data for the same job."""
        runner = self._runner_for(
            squeue_stdout="99001 RUNNING\n",
            sacct_stdout="99001|PENDING|0:0\n",
        )
        result = batch_query_slurm_job_states(
            ["99001"],
            scheduler_runner=runner,
            command_available=lambda _: True,
        )
        self.assertIn("99001", result)
        # squeue wins over sacct when both respond.
        self.assertEqual(result["99001"].scheduler_state, "RUNNING")
        self.assertEqual(result["99001"].source, "squeue")

    def test_falls_back_to_sacct_when_squeue_empty(self) -> None:
        """Use sacct state when squeue returns nothing for the job."""
        runner = self._runner_for(
            squeue_stdout="",
            sacct_stdout="99001|COMPLETED|0:0\n",
        )
        result = batch_query_slurm_job_states(
            ["99001"],
            scheduler_runner=runner,
            command_available=lambda _: True,
        )
        self.assertEqual(result["99001"].scheduler_state, "COMPLETED")
        self.assertEqual(result["99001"].source, "sacct")

    def test_records_exit_code_from_sacct(self) -> None:
        """Carry the exit code from sacct into the returned snapshot."""
        runner = self._runner_for(
            squeue_stdout="",
            sacct_stdout="99001|FAILED|1:0\n",
        )
        result = batch_query_slurm_job_states(
            ["99001"],
            scheduler_runner=runner,
            command_available=lambda _: True,
        )
        self.assertEqual(result["99001"].exit_code, "1:0")

    def test_handles_squeue_failure_gracefully(self) -> None:
        """Keep sacct results when squeue returns a nonzero exit code."""
        def runner(args, **_kwargs):  # noqa: ANN001
            if args[0] == "squeue":
                return _make_proc(returncode=1, stderr="squeue: error: Invalid job id")
            return _make_proc(stdout="99001|COMPLETED|0:0\n")

        result = batch_query_slurm_job_states(
            ["99001"],
            scheduler_runner=runner,
            command_available=lambda _: True,
        )
        # sacct still returned data, so we should have a snapshot.
        self.assertIn("99001", result)
        self.assertEqual(result["99001"].scheduler_state, "COMPLETED")

    def test_handles_unavailable_commands(self) -> None:
        """Return an empty dict when no Slurm commands are available."""
        result = batch_query_slurm_job_states(
            ["99001"],
            scheduler_runner=MagicMock(),
            command_available=lambda _: False,
        )
        self.assertEqual(result, {})

    def test_handles_squeue_timeout(self) -> None:
        """Survive a subprocess.TimeoutExpired from squeue without crashing."""
        def runner(args, **_kwargs):  # noqa: ANN001
            if args[0] == "squeue":
                raise subprocess.TimeoutExpired(cmd=args, timeout=30)
            return _make_proc(stdout="99001|COMPLETED|0:0\n")

        result = batch_query_slurm_job_states(
            ["99001"],
            scheduler_runner=runner,
            command_available=lambda _: True,
        )
        # sacct should still contribute.
        self.assertIn("99001", result)


# ---------------------------------------------------------------------------
# discover_active_slurm_run_dirs
# ---------------------------------------------------------------------------


class TestDiscoverActiveSlurmRunDirs(TestCase):
    """Tests for ``discover_active_slurm_run_dirs``."""

    def test_returns_empty_list_when_run_root_missing(self) -> None:
        """Return empty list when the run root directory does not exist."""
        result = discover_active_slurm_run_dirs(Path("/nonexistent/path/runs"))
        self.assertEqual(result, [])

    def test_discovers_running_job(self) -> None:
        """Return a run directory for a job with a non-terminal scheduler state."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "20260410T120000Z-busco-abc123"
            _minimal_slurm_record(run_dir, state="RUNNING")
            result = discover_active_slurm_run_dirs(run_root)
            self.assertEqual(result, [run_dir])

    def test_skips_completed_job(self) -> None:
        """Skip directories whose run record has a terminal scheduler state."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "20260410T120000Z-busco-done"
            _minimal_slurm_record(run_dir, state="COMPLETED")
            result = discover_active_slurm_run_dirs(run_root)
            self.assertEqual(result, [])

    def test_skips_failed_job(self) -> None:
        """Skip directories whose run record has a FAILED scheduler state."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "20260410T120000Z-busco-fail"
            _minimal_slurm_record(run_dir, state="FAILED")
            result = discover_active_slurm_run_dirs(run_root)
            self.assertEqual(result, [])

    def test_skips_cancellation_requested(self) -> None:
        """Skip directories whose record has cancellation_requested_at set."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "20260410T120000Z-busco-cancel"
            record = _minimal_slurm_record(run_dir, state="RUNNING")
            cancelled = replace(record, cancellation_requested_at="2026-04-10T12:00:00Z")
            save_slurm_run_record(cancelled)
            result = discover_active_slurm_run_dirs(run_root)
            self.assertEqual(result, [])

    def test_skips_dirs_without_run_record(self) -> None:
        """Skip directories that do not contain a slurm_run_record.json file."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            empty_dir = run_root / "empty"
            empty_dir.mkdir()
            result = discover_active_slurm_run_dirs(run_root)
            self.assertEqual(result, [])

    def test_mixed_states_returns_only_active(self) -> None:
        """Return only the active subset when run directories hold mixed states."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            active_dir = run_root / "active"
            done_dir = run_root / "done"
            _minimal_slurm_record(active_dir, state="PENDING")
            _minimal_slurm_record(done_dir, state="COMPLETED")
            result = discover_active_slurm_run_dirs(run_root)
            self.assertEqual(result, [active_dir])


# ---------------------------------------------------------------------------
# File-locking helpers
# ---------------------------------------------------------------------------


class TestSlurmRunRecordLocking(TestCase):
    """Tests for ``save_slurm_run_record_locked`` and ``load_slurm_run_record_locked``."""

    def test_locked_round_trip(self) -> None:
        """Save with locked writer and reload with locked reader; payloads match."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run1"
            record = _minimal_slurm_record(run_dir, state="RUNNING")

            updated = replace(record, scheduler_state="COMPLETED")
            written_path = save_slurm_run_record_locked(updated)
            self.assertTrue(written_path.exists())

            reloaded = load_slurm_run_record_locked(run_dir)
            self.assertEqual(reloaded.scheduler_state, "COMPLETED")
            self.assertEqual(reloaded.job_id, record.job_id)

    def test_locked_save_leaves_no_tmp_artifact(self) -> None:
        """Confirm the temporary write file is removed after a locked save."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run1"
            record = _minimal_slurm_record(run_dir, state="RUNNING")
            save_slurm_run_record_locked(record)
            tmp_files = list(run_dir.glob("*.tmp"))
            self.assertEqual(tmp_files, [], "Temporary write file should not remain after save.")

    def test_lock_file_created_alongside_record(self) -> None:
        """A companion .lock file is created (or exists) after a locked save."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run1"
            record = _minimal_slurm_record(run_dir, state="RUNNING")
            save_slurm_run_record_locked(record)
            lock_file = run_dir / "slurm_run_record.lock"
            self.assertTrue(lock_file.exists(), "Lock file should exist after a locked save.")


# ---------------------------------------------------------------------------
# reconcile_active_slurm_jobs
# ---------------------------------------------------------------------------


class TestReconcileActiveSlurmJobs(TestCase):
    """Integration tests for ``reconcile_active_slurm_jobs``."""

    def _runner_returning(self, state: str, exit_code: str = "0:0"):
        """Return a scheduler runner that reports ``state`` for every queried job.

        Args:
            state: Scheduler state to embed in all squeue and sacct responses.
            exit_code: Exit code string to embed in the sacct response.
        """
        def runner(args, **_kwargs):  # noqa: ANN001
            if args[0] == "squeue":
                # Build a response line for each job ID in the CSV argument.
                id_csv_index = args.index("--jobs") + 1 if "--jobs" in args else None
                if id_csv_index is not None:
                    ids = args[id_csv_index].split(",")
                    return _make_proc(stdout="\n".join(f"{jid} {state}" for jid in ids) + "\n")
                return _make_proc(stdout="")
            if args[0] == "sacct":
                id_csv_index = args.index("-j") + 1 if "-j" in args else None
                if id_csv_index is not None:
                    ids = args[id_csv_index].split(",")
                    return _make_proc(
                        stdout="\n".join(f"{jid}|{state}|{exit_code}" for jid in ids) + "\n"
                    )
                return _make_proc(stdout="")
            return _make_proc()

        return runner

    def test_updates_active_record_to_completed(self) -> None:
        """Transition a RUNNING job to COMPLETED when Slurm reports that state."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "run1"
            _minimal_slurm_record(run_dir, job_id="99001", state="RUNNING")

            updated = reconcile_active_slurm_jobs(
                run_root,
                scheduler_runner=self._runner_returning("COMPLETED"),
                command_available=lambda _: True,
            )

            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0].scheduler_state, "COMPLETED")
            self.assertEqual(updated[0].final_scheduler_state, "COMPLETED")

    def test_persists_updated_record_to_disk(self) -> None:
        """Verify the disk record reflects the reconciled state."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "run1"
            _minimal_slurm_record(run_dir, job_id="99001", state="RUNNING")

            reconcile_active_slurm_jobs(
                run_root,
                scheduler_runner=self._runner_returning("FAILED"),
                command_available=lambda _: True,
            )

            reloaded = load_slurm_run_record(run_dir)
            self.assertEqual(reloaded.scheduler_state, "FAILED")

    def test_does_not_touch_already_terminal_record(self) -> None:
        """Leave records that transitioned to a terminal state before the poll."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "run1"
            _minimal_slurm_record(run_dir, state="COMPLETED")

            # discover_active should not include this record.
            updated = reconcile_active_slurm_jobs(
                run_root,
                scheduler_runner=self._runner_returning("RUNNING"),
                command_available=lambda _: True,
            )

            self.assertEqual(updated, [])

    def test_returns_empty_list_when_no_active_jobs(self) -> None:
        """Return an empty list when the run root is empty."""
        with tempfile.TemporaryDirectory() as tmp:
            result = reconcile_active_slurm_jobs(
                Path(tmp),
                scheduler_runner=MagicMock(side_effect=AssertionError("should not be called")),
                command_available=lambda _: True,
            )
            self.assertEqual(result, [])

    def test_survives_slurm_command_failure(self) -> None:
        """Return an empty updated list when the Slurm command fails for all jobs."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "run1"
            _minimal_slurm_record(run_dir, state="RUNNING")

            result = reconcile_active_slurm_jobs(
                run_root,
                # Scheduler returns no output (job unknown to scheduler).
                scheduler_runner=lambda *a, **kw: _make_proc(stdout=""),
                command_available=lambda _: True,
            )
            # No update should have been made.
            self.assertEqual(result, [])

    def test_sets_last_reconciled_at(self) -> None:
        """Verify that the reconciliation timestamp is written into the record."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            run_dir = run_root / "run1"
            _minimal_slurm_record(run_dir, job_id="99001", state="RUNNING")

            updated = reconcile_active_slurm_jobs(
                run_root,
                scheduler_runner=self._runner_returning("RUNNING"),
                command_available=lambda _: True,
            )

            self.assertEqual(len(updated), 1)
            self.assertIsNotNone(updated[0].last_reconciled_at)


# ---------------------------------------------------------------------------
# Async poll loop lifecycle
# ---------------------------------------------------------------------------


class TestSlurmPollLoop(IsolatedAsyncioTestCase):
    """Async tests for the ``slurm_poll_loop`` lifecycle."""

    async def test_loop_runs_at_least_one_cycle_then_cancels(self) -> None:
        """Verify the loop calls reconcile at least once before being cancelled."""
        calls: list[str] = []

        def fake_reconcile(run_root, **_kwargs):  # noqa: ANN001
            calls.append("reconcile")
            return []

        with (
            patch("flytetest.slurm_monitor.reconcile_active_slurm_jobs", side_effect=fake_reconcile),
        ):
            config = SlurmPollingConfig(poll_interval_seconds=0.05)

            async def _run():
                import anyio
                with anyio.move_on_after(0.2):
                    await slurm_poll_loop(Path("/nonexistent"), config)

            await _run()

        self.assertGreaterEqual(len(calls), 1, "Expected at least one reconcile call.")

    async def test_loop_survives_reconcile_error(self) -> None:
        """A reconcile error triggers backoff but does not crash the loop.

        The backoff sleep after the first error is real time, so thread-dispatch
        overhead from ``anyio.to_thread.run_sync`` can push the second reconcile
        call past a short wall-clock window — causing intermittent CI failures.
        This test avoids that by replacing ``anyio.to_thread.run_sync`` with a
        direct synchronous call, making the test deterministic regardless of
        thread-pool latency.
        """
        import anyio
        import anyio.to_thread

        call_count = 0

        def failing_reconcile(run_root, **_kwargs):  # noqa: ANN001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated sacct timeout")
            return []

        async def fake_run_sync(fn: object, *, abandon_on_cancel: bool = False) -> object:
            """Invoke the reconcile lambda directly, skipping real thread dispatch.

            This eliminates thread-creation latency from the timing path so the
            test only waits on ``anyio.sleep`` between poll cycles, not on OS
            thread scheduling.
            """
            return fn()  # type: ignore[operator]

        with (
            patch("flytetest.slurm_monitor.reconcile_active_slurm_jobs", side_effect=failing_reconcile),
            patch.object(anyio.to_thread, "run_sync", new=fake_run_sync),
        ):
            config = SlurmPollingConfig(
                poll_interval_seconds=0.05,
                max_backoff_seconds=0.1,
                backoff_factor=2.0,
            )

            async def _run() -> None:
                with anyio.move_on_after(1.0):
                    await slurm_poll_loop(Path("/nonexistent"), config)

            await _run()

        self.assertGreaterEqual(call_count, 2, "Loop should have retried after the initial error.")

    async def test_loop_cancels_cleanly(self) -> None:
        """``asyncio.CancelledError`` / ``anyio`` cancel propagates out of the loop."""
        import anyio

        finished_normally = False

        async def _run():
            nonlocal finished_normally
            config = SlurmPollingConfig(poll_interval_seconds=60.0)
            with patch("flytetest.slurm_monitor.reconcile_active_slurm_jobs", return_value=[]):
                with anyio.move_on_after(0.1):
                    await slurm_poll_loop(Path("/nonexistent"), config)
            finished_normally = True

        await _run()
        # move_on_after causes the loop to exit via cancellation; the wrapper
        # function should still return without raising.
        self.assertTrue(finished_normally)
