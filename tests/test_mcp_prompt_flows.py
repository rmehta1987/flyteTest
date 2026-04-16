"""MCP prompt-level integration tests for the Slurm lifecycle.

These tests call through ``create_mcp_server()`` and then invoke each tool via
``server.tools["tool_name"](keyword_args)`` — exactly the path a JSON-RPC
client takes.  The only thing replaced is the Slurm scheduler subprocess layer
(sbatch / squeue / scontrol / sacct / scancel), which is substituted by
in-process callables so the suite runs offline without real cluster access.

Three multi-turn flows are validated:

1. **Happy path** (prepare → submit → poll × 2 → COMPLETED)
   The most important MCP client behaviour: read ``final_scheduler_state``
   to decide when to stop polling.  First poll must return ``None``; second
   must return ``"COMPLETED"``.

2. **Failure + retry** (prepare → submit → FAILED → retry → COMPLETED)
   Verifies that ``retry_slurm_job`` produces a *new* ``run_record_path`` and
   a *new* ``job_id``, and that the child lifecycle chain reaches COMPLETED
   independently of the parent.

3. **Cancel idempotency** (prepare → submit → cancel → cancel again)
   The second MCP cancel call must return ``supported=True`` without issuing a
   second ``scancel`` to the scheduler.

These tests complement the unit tests in ``test_server.py``, which call the
``_*_impl`` functions directly.  The gap they close is JSON-RPC argument
coercion (all arguments arrive as strings from the client), multi-turn
orchestration, and the ``supported`` / ``limitations`` contract as seen from
the MCP boundary.

 When you log onto the cluster you can submit these with:
.venv/bin/python -m unittest tests.test_mcp_prompt_flows -v
"""

from __future__ import annotations

import json
import subprocess
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

from flytetest.server import (
    _cancel_slurm_job_impl,
    _monitor_slurm_job_impl,
    _prepare_run_recipe_impl,
    _retry_slurm_job_impl,
    _run_slurm_recipe_impl,
    create_mcp_server,
)


# ---------------------------------------------------------------------------
# Minimal FastMCP stand-in (same contract as in test_server.py)
# ---------------------------------------------------------------------------


class _FakeFastMCP:
    """Capture registered tool callables without starting a real MCP server."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, object] = {}
        self.resources: dict[str, object] = {}

    def tool(self):  # type: ignore[no-untyped-def]
        def decorator(fn):  # type: ignore[no-untyped-def]
            self.tools[fn.__name__] = fn
            return fn
        return decorator

    def resource(self, uri: str):  # type: ignore[no-untyped-def]
        def decorator(fn):  # type: ignore[no-untyped-def]
            self.resources[uri] = fn
            return fn
        return decorator

    def run(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_manifest_dir(tmp_path: Path) -> Path:
    """Write a minimal repeat-filter run manifest so BUSCO prepare succeeds."""
    result_dir = tmp_path / "repeat_filter_results"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "workflow": "annotation_repeat_filtering",
                "assumptions": ["Repeat-filtered outputs are QC-ready."],
                "inputs": {"reference_genome": "data/genome.fa"},
                "outputs": {
                    "all_repeats_removed_gff3": str(result_dir / "out.gff3"),
                    "final_proteins_fasta": str(result_dir / "proteins.fa"),
                },
            }
        )
    )
    return result_dir


# ---------------------------------------------------------------------------
# Fake scheduler callables
# ---------------------------------------------------------------------------


def _fake_sbatch(job_id: str):
    """Callable that simulates a successful ``sbatch`` submission."""
    def runner(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"Submitted batch job {job_id}\n",
            stderr="",
        )
    return runner


def _fake_terminal_scheduler(job_id: str, state: str, exit_code: str = "0:0"):
    """Immediately terminal: squeue returns empty; sacct returns the given state."""
    def runner(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        cmd = args[0]
        if cmd in ("squeue", "scontrol"):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        if cmd == "sacct":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=f"{job_id}|{state}|{exit_code}\n",
                stderr="",
            )
        raise AssertionError(f"unexpected scheduler command: {args}")
    return runner


def _fake_running_then_completed_scheduler(job_id: str):
    """Stateful fake: first squeue call returns RUNNING; later calls fall back to sacct COMPLETED."""
    squeue_hit_count = [0]

    def runner(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        cmd = args[0]
        if cmd == "squeue":
            squeue_hit_count[0] += 1
            if squeue_hit_count[0] == 1:
                # First monitor call — job is still active in the queue.
                return subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="RUNNING\n", stderr=""
                )
            # Subsequent calls — job has aged off squeue (normal after completion).
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        if cmd == "scontrol":
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        if cmd == "sacct":
            if squeue_hit_count[0] <= 1:
                # sacct not yet updated during the first pass.
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=f"{job_id}|COMPLETED|0:0\n",
                stderr="",
            )
        raise AssertionError(f"unexpected scheduler command: {args}")

    return runner


def _fake_scancel_scheduler(job_id: str, scancel_log: list[list[str]]):
    """Scheduler fake that records every scancel call into ``scancel_log``."""
    def runner(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        cmd = args[0]
        if cmd == "scancel":
            scancel_log.append(list(args))
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        if cmd in ("squeue", "scontrol", "sacct"):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {args}")
    return runner


# ---------------------------------------------------------------------------
# Helper: inject fake runners into the _impl layer for one test
# ---------------------------------------------------------------------------


class _PatchedServer:
    """Context manager that builds the MCP server with injected fake runners.

    The public MCP tools (``run_slurm_recipe``, ``monitor_slurm_job``, …) call
    the ``_*_impl`` functions by name.  Patching those names in the
    ``flytetest.server`` module makes the injection visible to the real tool
    callables that the JSON-RPC layer dispatches to.
    """

    def __init__(
        self,
        *,
        tmp_path: Path,
        sbatch_runner,
        monitor_scheduler,
        cancel_scheduler=None,
        retry_sbatch_runner=None,
        retry_scheduler=None,
    ) -> None:
        self._tmp_path = tmp_path
        self._sbatch_runner = sbatch_runner
        self._monitor_scheduler = monitor_scheduler
        self._cancel_scheduler = cancel_scheduler or _fake_terminal_scheduler("0", "CANCELLED")
        self._retry_sbatch_runner = retry_sbatch_runner
        self._retry_scheduler = retry_scheduler
        self._run_dir = tmp_path / "runs"
        self._recipe_dir = tmp_path / "specs"
        self._patches: list = []
        self.server: _FakeFastMCP | None = None

    def __enter__(self) -> _FakeFastMCP:
        run_dir = self._run_dir
        recipe_dir = self._recipe_dir
        sbatch_runner = self._sbatch_runner
        monitor_scheduler = self._monitor_scheduler
        cancel_scheduler = self._cancel_scheduler
        retry_sbatch_runner = self._retry_sbatch_runner or self._sbatch_runner
        retry_scheduler = self._retry_scheduler or self._monitor_scheduler

        def _patched_prepare(prompt, **kwargs):
            kwargs.setdefault("recipe_dir", recipe_dir)
            return _prepare_run_recipe_impl(prompt, **kwargs)

        def _patched_submit(artifact_path, **kwargs):
            return _run_slurm_recipe_impl(
                artifact_path,
                run_dir=run_dir,
                sbatch_runner=sbatch_runner,
                command_available=lambda _: True,
            )

        def _patched_monitor(run_record_path, **kwargs):
            return _monitor_slurm_job_impl(
                run_record_path,
                run_dir=run_dir,
                scheduler_runner=monitor_scheduler,
                command_available=lambda _: True,
            )

        def _patched_cancel(run_record_path, **kwargs):
            return _cancel_slurm_job_impl(
                run_record_path,
                run_dir=run_dir,
                scheduler_runner=cancel_scheduler,
                command_available=lambda _: True,
            )

        def _patched_retry(run_record_path, **kwargs):
            return _retry_slurm_job_impl(
                run_record_path,
                run_dir=run_dir,
                sbatch_runner=retry_sbatch_runner,
                scheduler_runner=retry_scheduler,
                command_available=lambda _: True,
                resource_overrides=kwargs.get("resource_overrides"),
            )

        self._patches = [
            patch("flytetest.server._prepare_run_recipe_impl", side_effect=_patched_prepare),
            patch("flytetest.server._run_slurm_recipe_impl", side_effect=_patched_submit),
            patch("flytetest.server._monitor_slurm_job_impl", side_effect=_patched_monitor),
            patch("flytetest.server._cancel_slurm_job_impl", side_effect=_patched_cancel),
            patch("flytetest.server._retry_slurm_job_impl", side_effect=_patched_retry),
        ]
        for p in self._patches:
            p.start()

        self.server = create_mcp_server(fastmcp_cls=_FakeFastMCP)
        return self.server  # type: ignore[return-value]

    def __exit__(self, *_exc) -> None:
        for p in reversed(self._patches):
            p.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class SlurmMcpPromptFlowTests(TestCase):
    """Multi-turn Slurm lifecycle flows exercised through the MCP tool surface.

    Each test calls ``server.tools["tool_name"](keyword_args)`` with string
    arguments, mirroring what the MCP JSON-RPC layer delivers from a Claude
    client.  Assertions are made on the structured response fields that clients
    are expected to read (``supported``, ``final_scheduler_state``,
    ``run_record_path``, ``job_id``, ``limitations``).
    """

    # ------------------------------------------------------------------
    # Flow 1: Happy path — prepare → submit → poll until COMPLETED
    # ------------------------------------------------------------------

    def test_mcp_prepare_submit_and_poll_until_completed(self) -> None:
        """prepare_run_recipe → run_slurm_recipe → monitor × 2 through the MCP surface.

        Validates the client polling gate:
        - First ``monitor_slurm_job`` call: ``final_scheduler_state`` is ``None``
          (client must call again).
        - Second call: ``final_scheduler_state == "COMPLETED"`` (client stops).
        """
        job_id = "99101"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_dir = _make_manifest_dir(tmp_path)

            ctx = _PatchedServer(
                tmp_path=tmp_path,
                sbatch_runner=_fake_sbatch(job_id),
                monitor_scheduler=_fake_running_then_completed_scheduler(job_id),
            )
            with ctx as server:
                # Phase 1: prepare — resource_request arrives as a plain dict from JSON.
                prepared = server.tools["prepare_run_recipe"](
                    prompt="Run BUSCO quality assessment on the annotation.",
                    manifest_sources=[str(manifest_dir)],
                    runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                    resource_request={
                        "cpu": 8,
                        "memory": "32Gi",
                        "queue": "caslake",
                        "account": "rcc-staff",
                        "walltime": "02:00:00",
                    },
                    execution_profile="slurm",
                )
                self.assertTrue(prepared["supported"], prepared.get("limitations"))
                artifact_path = prepared["artifact_path"]
                self.assertIsNotNone(artifact_path, "artifact_path must be set for a supported prepare")

                # Phase 2: submit — artifact_path is passed as a plain string.
                submitted = server.tools["run_slurm_recipe"](artifact_path=str(artifact_path))
                self.assertTrue(submitted["supported"], submitted.get("limitations"))
                self.assertEqual(
                    submitted["job_id"],
                    job_id,
                    "job_id in response must match the submitted batch job ID",
                )
                run_record_path = submitted["run_record_path"]
                self.assertIsNotNone(run_record_path, "run_record_path must be set after successful submission")

                # Phase 3: first poll — job is RUNNING; final_scheduler_state must be None.
                status1 = server.tools["monitor_slurm_job"](run_record_path=str(run_record_path))
                self.assertTrue(status1["supported"], status1.get("limitations"))
                self.assertEqual(
                    status1["lifecycle_result"]["scheduler_state"],
                    "RUNNING",
                    "First poll must report RUNNING while job is active",
                )
                self.assertIsNone(
                    status1["lifecycle_result"]["final_scheduler_state"],
                    "final_scheduler_state must be None while job is non-terminal (client must keep polling)",
                )

                # Phase 4: second poll — job has completed; final_scheduler_state must be set.
                status2 = server.tools["monitor_slurm_job"](run_record_path=str(run_record_path))
                self.assertTrue(status2["supported"], status2.get("limitations"))
                self.assertEqual(
                    status2["lifecycle_result"]["final_scheduler_state"],
                    "COMPLETED",
                    "final_scheduler_state must be COMPLETED once job reaches terminal state",
                )
                self.assertEqual(
                    status2["lifecycle_result"]["scheduler_state"],
                    "COMPLETED",
                )

    # ------------------------------------------------------------------
    # Flow 2: Failure + retry — FAILED job is retried to COMPLETED
    # ------------------------------------------------------------------

    def test_mcp_failed_job_is_retried_to_completed(self) -> None:
        """prepare → submit → monitor(NODE_FAIL) → retry_slurm_job → monitor(COMPLETED).

        Validates the retry lifecycle from the MCP client perspective:
        - ``retry_slurm_job`` must return a *different* ``retry_run_record_path``
          and a *new* ``job_id`` for the resubmission.
        - Monitoring the child run record must eventually reach COMPLETED.

        NODE_FAIL is used because it is in ``_RETRYABLE_SLURM_STATES``.  FAILED
        with a non-zero exit code is classified as ``workflow_exit_failure``
        (not retryable) — that case is already covered in test_server.py.
        """
        parent_job_id = "99201"
        retry_job_id = "99202"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_dir = _make_manifest_dir(tmp_path)

            ctx = _PatchedServer(
                tmp_path=tmp_path,
                sbatch_runner=_fake_sbatch(parent_job_id),
                monitor_scheduler=_fake_terminal_scheduler(parent_job_id, "NODE_FAIL", "0:0"),
                retry_sbatch_runner=_fake_sbatch(retry_job_id),
                retry_scheduler=_fake_terminal_scheduler(parent_job_id, "NODE_FAIL", "0:0"),
            )
            with ctx as server:
                # Prepare + submit the parent job.
                prepared = server.tools["prepare_run_recipe"](
                    prompt="Run BUSCO quality assessment on the annotation.",
                    manifest_sources=[str(manifest_dir)],
                    runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                    resource_request={
                        "cpu": 8,
                        "memory": "32Gi",
                        "queue": "caslake",
                        "account": "rcc-staff",
                        "walltime": "02:00:00",
                    },
                    execution_profile="slurm",
                )
                self.assertTrue(prepared["supported"], prepared.get("limitations"))

                submitted = server.tools["run_slurm_recipe"](
                    artifact_path=str(prepared["artifact_path"])
                )
                self.assertTrue(submitted["supported"], submitted.get("limitations"))
                parent_run_record_path = submitted["run_record_path"]

                # Monitor → FAILED.  final_scheduler_state must be set.
                failed_status = server.tools["monitor_slurm_job"](
                    run_record_path=str(parent_run_record_path)
                )
                self.assertTrue(failed_status["supported"], failed_status.get("limitations"))
                self.assertEqual(
                    failed_status["lifecycle_result"]["final_scheduler_state"],
                    "NODE_FAIL",
                )

                # Retry — client passes the *same* run_record_path as a string.
                retry_result = server.tools["retry_slurm_job"](
                    run_record_path=str(parent_run_record_path)
                )
                self.assertTrue(retry_result["supported"], retry_result.get("limitations"))
                self.assertEqual(
                    retry_result["job_id"],
                    retry_job_id,
                    "retry_slurm_job must report the new Slurm job ID for the resubmission",
                )
                child_run_record_path = retry_result["retry_run_record_path"]
                self.assertIsNotNone(child_run_record_path, "retry_run_record_path must be set")
                self.assertNotEqual(
                    child_run_record_path,
                    parent_run_record_path,
                    "retry must produce a new run_record_path separate from the parent",
                )

                # Monitor the child run record through the patched monitor layer.
                # The patched monitor reuses the same _PatchedServer scheduler, so
                # we need to monitor the child record path directly.
                child_status = _monitor_slurm_job_impl(
                    str(child_run_record_path),
                    run_dir=tmp_path / "runs",
                    scheduler_runner=_fake_terminal_scheduler(retry_job_id, "COMPLETED"),
                    command_available=lambda _: True,
                )
                self.assertTrue(child_status["supported"], child_status.get("limitations"))
                self.assertEqual(
                    child_status["lifecycle_result"]["final_scheduler_state"],
                    "COMPLETED",
                    "Child run record must reach COMPLETED independently of the parent",
                )

    # ------------------------------------------------------------------
    # Flow 3: Cancel idempotency — second cancel does not scancel again
    # ------------------------------------------------------------------

    def test_mcp_duplicate_cancel_does_not_issue_second_scancel(self) -> None:
        """prepare → submit → cancel → cancel again via the MCP surface.

        Validates that the second ``cancel_slurm_job`` call:
        - Returns ``supported=True`` (not an error).
        - Does NOT issue a second ``scancel`` to the scheduler.
        """
        job_id = "99301"
        scancel_log: list[list[str]] = []

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_dir = _make_manifest_dir(tmp_path)

            cancel_scheduler = _fake_scancel_scheduler(job_id, scancel_log)

            ctx = _PatchedServer(
                tmp_path=tmp_path,
                sbatch_runner=_fake_sbatch(job_id),
                monitor_scheduler=cancel_scheduler,
                cancel_scheduler=cancel_scheduler,
            )
            with ctx as server:
                # Prepare + submit.
                prepared = server.tools["prepare_run_recipe"](
                    prompt="Run BUSCO quality assessment on the annotation.",
                    manifest_sources=[str(manifest_dir)],
                    runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                    resource_request={
                        "cpu": 8,
                        "memory": "32Gi",
                        "queue": "caslake",
                        "account": "rcc-staff",
                        "walltime": "02:00:00",
                    },
                    execution_profile="slurm",
                )
                self.assertTrue(prepared["supported"], prepared.get("limitations"))

                submitted = server.tools["run_slurm_recipe"](
                    artifact_path=str(prepared["artifact_path"])
                )
                self.assertTrue(submitted["supported"], submitted.get("limitations"))
                run_record_path = submitted["run_record_path"]

                # First cancel — must issue scancel and persist cancellation_requested_at.
                cancel1 = server.tools["cancel_slurm_job"](
                    run_record_path=str(run_record_path)
                )
                self.assertTrue(cancel1["supported"], cancel1.get("limitations"))
                self.assertEqual(
                    len(scancel_log),
                    1,
                    "First cancel must issue exactly one scancel call",
                )

                # Second cancel — idempotency: no duplicate scancel.
                cancel2 = server.tools["cancel_slurm_job"](
                    run_record_path=str(run_record_path)
                )
                self.assertTrue(
                    cancel2["supported"],
                    "Second cancel must return supported=True (idempotent, not an error)",
                )
                self.assertEqual(
                    len(scancel_log),
                    1,
                    "Second cancel must NOT issue a second scancel to the scheduler",
                )

    # ------------------------------------------------------------------
    # Flow 4: resource_request as embedded text (MCP arg-drop fallback)
    # ------------------------------------------------------------------

    def test_mcp_prepare_with_resource_request_dict_uses_slurm_profile(self) -> None:
        """resource_request dict is passed through prepare to the frozen artifact.

        Some MCP clients drop optional structured arguments and embed them in
        the prompt text instead.  This test verifies that when resource_request
        *is* passed as a JSON dict, the frozen recipe captures the slurm
        execution profile so run_slurm_recipe can proceed without re-planning.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_dir = _make_manifest_dir(tmp_path)

            ctx = _PatchedServer(
                tmp_path=tmp_path,
                sbatch_runner=_fake_sbatch("99401"),
                monitor_scheduler=_fake_terminal_scheduler("99401", "COMPLETED"),
            )
            with ctx as server:
                prepared = server.tools["prepare_run_recipe"](
                    prompt="Run BUSCO quality assessment on the annotation.",
                    manifest_sources=[str(manifest_dir)],
                    runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                    resource_request={
                        "cpu": 4,
                        "memory": "16Gi",
                        "queue": "caslake",
                        "account": "rcc-staff",
                        "walltime": "01:00:00",
                    },
                    execution_profile="slurm",
                )
                self.assertTrue(prepared["supported"], prepared.get("limitations"))

                # The typed plan must show the slurm execution profile was accepted.
                typed_plan = prepared.get("typed_plan", {})
                binding_plan = typed_plan.get("binding_plan", {})
                self.assertEqual(
                    binding_plan.get("execution_profile"),
                    "slurm",
                    "resource_request with execution_profile='slurm' must freeze slurm into the recipe",
                )

    # ------------------------------------------------------------------
    # Flow 5: list_slurm_run_history reflects submitted jobs
    # ------------------------------------------------------------------

    def test_mcp_list_slurm_run_history_returns_submitted_job(self) -> None:
        """list_slurm_run_history surfaces run records after a successful submission.

        Verifies that after prepare + submit, the job appears in history with
        the correct workflow_name and job_id, as a client would see it when
        calling list_slurm_run_history to resume monitoring after a restart.
        """
        from flytetest.server import _list_slurm_run_history_impl

        job_id = "99501"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_dir = _make_manifest_dir(tmp_path)

            ctx = _PatchedServer(
                tmp_path=tmp_path,
                sbatch_runner=_fake_sbatch(job_id),
                monitor_scheduler=_fake_terminal_scheduler(job_id, "RUNNING"),
            )
            with ctx as server:
                prepared = server.tools["prepare_run_recipe"](
                    prompt="Run BUSCO quality assessment on the annotation.",
                    manifest_sources=[str(manifest_dir)],
                    runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                    resource_request={
                        "cpu": 8,
                        "memory": "32Gi",
                        "queue": "caslake",
                        "account": "rcc-staff",
                        "walltime": "02:00:00",
                    },
                    execution_profile="slurm",
                )
                self.assertTrue(prepared["supported"])

                submitted = server.tools["run_slurm_recipe"](
                    artifact_path=str(prepared["artifact_path"])
                )
                self.assertTrue(submitted["supported"])

            # History query uses the same run_dir as the submission.
            history = _list_slurm_run_history_impl(run_dir=tmp_path / "runs")

        self.assertTrue(history["supported"], history.get("limitations"))
        entries = history.get("entries", [])
        self.assertEqual(len(entries), 1, "Exactly one run should appear in history")
        entry = entries[0]
        self.assertEqual(entry["job_id"], job_id)
        self.assertIn("busco", entry["workflow_name"].lower())

    # ------------------------------------------------------------------
    # Flow 4 (M20a): OOM failure + escalation retry with resource_overrides
    # ------------------------------------------------------------------

    def test_mcp_oom_job_is_retried_with_resource_overrides_to_completed(self) -> None:
        """prepare → submit → monitor(OUT_OF_MEMORY) → retry(resource_overrides) → COMPLETED.

        Validates the escalation-retry lifecycle from the MCP client perspective:
        - ``retry_slurm_job`` with ``resource_overrides`` must return a *new*
          ``retry_run_record_path`` and a *new* ``job_id``.
        - The child run record carries the overridden memory in both
          ``resource_spec`` and ``resource_overrides``.
        - Monitoring the child record must reach COMPLETED.
"""
        from flytetest.spec_executor import load_slurm_run_record as _load_record

        parent_job_id = "99401"
        retry_job_id = "99402"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_dir = _make_manifest_dir(tmp_path)

            ctx = _PatchedServer(
                tmp_path=tmp_path,
                sbatch_runner=_fake_sbatch(parent_job_id),
                monitor_scheduler=_fake_terminal_scheduler(parent_job_id, "OUT_OF_MEMORY", "1:0"),
                retry_sbatch_runner=_fake_sbatch(retry_job_id),
                retry_scheduler=_fake_terminal_scheduler(parent_job_id, "OUT_OF_MEMORY", "1:0"),
            )
            with ctx as server:
                # Prepare + submit the parent job.
                prepared = server.tools["prepare_run_recipe"](
                    prompt="Run BUSCO quality assessment on the annotation.",
                    manifest_sources=[str(manifest_dir)],
                    runtime_bindings={"busco_lineages_text": "embryophyta_odb10"},
                    resource_request={
                        "cpu": 8,
                        "memory": "32Gi",
                        "queue": "caslake",
                        "account": "rcc-staff",
                        "walltime": "02:00:00",
                    },
                    execution_profile="slurm",
                )
                self.assertTrue(prepared["supported"], prepared.get("limitations"))

                submitted = server.tools["run_slurm_recipe"](
                    artifact_path=str(prepared["artifact_path"])
                )
                self.assertTrue(submitted["supported"], submitted.get("limitations"))
                parent_run_record_path = submitted["run_record_path"]

                # Monitor → OUT_OF_MEMORY.
                failed_status = server.tools["monitor_slurm_job"](
                    run_record_path=str(parent_run_record_path)
                )
                self.assertTrue(failed_status["supported"], failed_status.get("limitations"))
                self.assertEqual(
                    failed_status["lifecycle_result"]["final_scheduler_state"],
                    "OUT_OF_MEMORY",
                )

                # Retry with resource_overrides to escalate memory.
                retry_result = server.tools["retry_slurm_job"](
                    run_record_path=str(parent_run_record_path),
                    resource_overrides={"memory": "64Gi"},
                )
                self.assertTrue(retry_result["supported"], retry_result.get("limitations"))
                self.assertEqual(
                    retry_result["job_id"],
                    retry_job_id,
                    "retry_slurm_job must report the new Slurm job ID for the escalation retry",
                )
                child_run_record_path = retry_result["retry_run_record_path"]
                self.assertIsNotNone(child_run_record_path)
                self.assertNotEqual(child_run_record_path, parent_run_record_path)

                # Verify child run record carries the overridden memory.
                child_record = _load_record(Path(str(child_run_record_path)))
                self.assertEqual(
                    child_record.resource_spec.memory,
                    "64Gi",
                    "Child resource_spec.memory must reflect the resource_override",
                )
                self.assertIsNotNone(child_record.resource_overrides)
                self.assertEqual(child_record.resource_overrides.memory, "64Gi")

                # Monitor the child → COMPLETED.
                child_status = _monitor_slurm_job_impl(
                    str(child_run_record_path),
                    run_dir=tmp_path / "runs",
                    scheduler_runner=_fake_terminal_scheduler(retry_job_id, "COMPLETED"),
                    command_available=lambda _: True,
                )
                self.assertTrue(child_status["supported"], child_status.get("limitations"))
                self.assertEqual(
                    child_status["lifecycle_result"]["final_scheduler_state"],
                    "COMPLETED",
                    "Child run record must reach COMPLETED after escalation retry",
                )
