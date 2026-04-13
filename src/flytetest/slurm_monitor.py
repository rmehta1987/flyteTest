"""Background async Slurm monitoring for the FLyteTest MCP server.

This module provides the background asyncio loop that periodically polls the
Slurm scheduler for all active jobs and updates the durable run records under
``.runtime/runs/`` without blocking the main MCP server event loop.

Key design points:

- Batched Slurm queries: one ``squeue``/``sacct`` call per poll cycle rather
  than one call per job, to avoid overwhelming the scheduler.
- Atomic writes with file locking: exclusive ``fcntl.flock`` on a companion
  ``.lock`` file guards concurrent writes between the async updater and any
  synchronous MCP requests that touch the same record.
- Configurable rate-limits: poll interval, exponential backoff cap, and per-
  command timeout prevent scheduler bans and stalled-command hangs.
- Exception isolation: a single ``sacct`` timeout or parse error in one poll
  cycle is logged and retried with backoff; it does not kill the MCP server.
- Graceful shutdown via anyio task-group cancellation when the MCP server
  exits.

Assumptions and known limits:

- File locking uses ``fcntl.flock``; this is Linux-only.  NFS support depends
  on the mount options; advisory locking is not guaranteed on all NFS configs.
- The async loop is read-then-write with a file lock, so it requires that any
  writer (both this loop and synchronous MCP handlers) holds the lock before
  writing.  Synchronous saves continue to use ``save_slurm_run_record``; this
  module provides ``save_slurm_run_record_locked`` for the async path.
"""

from __future__ import annotations

import fcntl
import json
import logging
import subprocess
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Any

from flytetest.spec_executor import (
    DEFAULT_SLURM_RUN_RECORD_FILENAME,
    SlurmRunRecord,
    SlurmSchedulerSnapshot,
    _TERMINAL_SLURM_STATES,
    _command_is_available,
    _normalize_scheduler_state,
    _slurm_command_failure_limitation,
    _looks_like_scheduler_reachability_issue,
    classify_slurm_failure,
    load_slurm_run_record,
    save_slurm_run_record,
)
from flytetest.spec_executor import _created_at

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public configuration
# ---------------------------------------------------------------------------

_DEFAULT_POLL_INTERVAL = 30.0
_DEFAULT_MAX_BACKOFF = 300.0
_DEFAULT_BACKOFF_FACTOR = 2.0
_DEFAULT_COMMAND_TIMEOUT = 30.0


@dataclass(frozen=True, slots=True)
class SlurmPollingConfig:
    """Configuration for the background Slurm polling loop.

    Attributes:
        poll_interval_seconds: Baseline sleep time between polling cycles.
        max_backoff_seconds: Upper bound on the sleep time after repeated
            scheduler failures.  Acts as a safety cap on the exponential
            backoff.
        backoff_factor: Multiplier applied to the current sleep interval after
            each consecutive scheduler error.  A value of ``2.0`` doubles the
            wait on every failure.
        command_timeout_seconds: Per-command wall-clock timeout passed to
            ``asyncio.to_thread`` / ``anyio.to_thread.run_sync``.  Commands
            that exceed this limit raise ``subprocess.TimeoutExpired``, which
            is caught and reported as a poll-cycle failure.
    """

    poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL
    max_backoff_seconds: float = _DEFAULT_MAX_BACKOFF
    backoff_factor: float = _DEFAULT_BACKOFF_FACTOR
    command_timeout_seconds: float = _DEFAULT_COMMAND_TIMEOUT


# ---------------------------------------------------------------------------
# File locking
# ---------------------------------------------------------------------------


def _lock_file_path(record_json_path: Path) -> Path:
    """Return the companion lock-file path for a run-record JSON file.

    Args:
        record_json_path: Path to the ``slurm_run_record.json`` file being
            protected.

    Returns:
        The path of the companion ``.lock`` file, which is created on demand.
    """
    return record_json_path.with_suffix(".lock")


@contextmanager
def _exclusive_record_lock(record_json_path: Path):
    """Context manager for exclusive write access to a durable run record.

    Acquires an exclusive ``fcntl.flock`` on a companion ``.lock`` file
    alongside the JSON record.  The JSON record itself is replaced atomically,
    so the lock guards the read-modify-write sequence as a whole.

    This is Linux-only and relies on the filesystem supporting advisory
    locking.  NFS behaviour depends on mount options; see module-level notes.

    Args:
        record_json_path: Path to the ``slurm_run_record.json`` file being
            protected.  The lock file is derived from this path.

    Yields:
        Nothing.  Callers perform their read/write inside the ``with`` block.
    """
    lock_path = _lock_file_path(record_json_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_fh:
        try:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def save_slurm_run_record_locked(record: SlurmRunRecord) -> Path:
    """Persist a Slurm run record under an exclusive file lock.

    Uses ``_exclusive_record_lock`` to prevent concurrent writes from the
    async polling loop and synchronous MCP handlers overwriting each other.
    The underlying ``save_slurm_run_record`` write is still atomic
    (temp-file swap), so partial writes are never visible.

    Args:
        record: The :class:`~flytetest.spec_executor.SlurmRunRecord` to
            persist.

    Returns:
        The path where the record was written.
    """
    with _exclusive_record_lock(record.run_record_path):
        return save_slurm_run_record(record)


def load_slurm_run_record_locked(source: Path) -> SlurmRunRecord:
    """Load a Slurm run record under an exclusive file lock.

    Taking an exclusive lock for reads may seem strict, but it prevents a
    reader from seeing a partially-replaced record during a concurrent write.
    Because writes use ``os.replace`` (atomic at the inode level), the risk
    of seeing torn data is already low; the lock provides an extra safety net
    for races between the async loop reload and the synchronous MCP path.

    Args:
        source: Directory containing ``slurm_run_record.json`` or a direct
            path to the JSON file.

    Returns:
        The deserialized :class:`~flytetest.spec_executor.SlurmRunRecord`.
    """
    record_path = (
        source / DEFAULT_SLURM_RUN_RECORD_FILENAME if source.is_dir() else source
    )
    with _exclusive_record_lock(record_path):
        return load_slurm_run_record(source)


# ---------------------------------------------------------------------------
# Batched Slurm status parsing
# ---------------------------------------------------------------------------


def _parse_batch_squeue_output(stdout: str) -> dict[str, str]:
    """Parse ``squeue --format="%i %T"`` output for multiple jobs.

    Each non-empty output line contains a whitespace-separated job-id and
    state token, e.g. ``"123 RUNNING"``.  The function skips header lines
    and any line that does not conform to this shape.

    Args:
        stdout: Raw standard output from the ``squeue`` invocation.

    Returns:
        A mapping from job ID (string) to normalised scheduler state.
    """
    states: dict[str, str] = {}
    for line in stdout.splitlines():
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        job_id_token = parts[0]
        state_token = parts[1]
        # Skip the header row emitted when --noheader is omitted.
        if job_id_token.upper() == "JOBID":
            continue
        state = _normalize_scheduler_state(state_token)
        if state is not None:
            states[job_id_token] = state
    return states


def _parse_batch_sacct_output(stdout: str) -> dict[str, dict[str, str]]:
    """Parse pipe-delimited ``sacct --format=JobID,State,ExitCode`` output.

    One job may appear on multiple rows (e.g. ``123``, ``123.batch``,
    ``123.0``).  The function prefers the bare job-ID row over step rows.
    When no bare row is present it falls back to the first non-header row
    for that job.

    Args:
        stdout: Raw standard output from the ``sacct`` invocation.

    Returns:
        A mapping from bare job ID (string) to a dict of
        ``{"JobID": ..., "State": ..., "ExitCode": ...}``.
    """
    # first pass: collect all rows keyed by their JobID token
    rows: list[dict[str, str]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            continue
        parts = stripped.split("|")
        if len(parts) < 3:
            continue
        row = {"JobID": parts[0], "State": parts[1], "ExitCode": parts[2]}
        # Skip the header row.
        if parts[0].upper() == "JOBID":
            continue
        rows.append(row)

    # second pass: gather per-bare-job best rows
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        token = row["JobID"]
        bare_id = token.split(".")[0]  # drop ".batch", ".0" step suffixes
        if bare_id not in result:
            result[bare_id] = row
            continue
        # Prefer the exact-match (bare) row over step rows.
        if token == bare_id:
            result[bare_id] = row
    return result


def batch_query_slurm_job_states(
    job_ids: Sequence[str],
    *,
    scheduler_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    command_available: Callable[[str], bool] = _command_is_available,
    command_timeout: float = _DEFAULT_COMMAND_TIMEOUT,
) -> dict[str, SlurmSchedulerSnapshot]:
    """Fetch Slurm states for multiple jobs in a single scheduler call.

    Issues one ``squeue`` call and one ``sacct`` call (when available) for all
    requested job IDs at once, avoiding the per-job request loop that would
    otherwise require ``N`` round-trips per poll cycle.

    Only jobs that appear in scheduler output receive a
    :class:`~flytetest.spec_executor.SlurmSchedulerSnapshot`; jobs that
    Slurm no longer knows about are absent from the return dict.

    Args:
        job_ids: Slurm job identifiers to query in one batch.  Duplicate IDs
            are deduplicated before querying.
        scheduler_runner: Injectable subprocess runner for testing.  Defaults
            to :func:`subprocess.run`.
        command_available: Injectable command-availability check for testing.
            Defaults to :func:`~flytetest.spec_executor._command_is_available`.
        command_timeout: Per-command wall-clock timeout in seconds.  Commands
            that exceed this limit raise :exc:`subprocess.TimeoutExpired`.

    Returns:
        A dict mapping each observed job ID to its
        :class:`~flytetest.spec_executor.SlurmSchedulerSnapshot`.  Jobs not
        present in scheduler output are absent from the dict rather than
        represented by empty snapshots.
    """
    if not job_ids:
        return {}

    unique_ids = list(dict.fromkeys(job_ids))
    id_csv = ",".join(unique_ids)

    squeue_states: dict[str, str] = {}
    sacct_fields_by_id: dict[str, dict[str, str]] = {}
    limitations: list[str] = []

    # --- squeue ---
    if command_available("squeue"):
        try:
            proc = scheduler_runner(
                ["squeue", "--noheader", "--jobs", id_csv, "--format=%i %T"],
                capture_output=True,
                text=True,
                check=False,
                timeout=command_timeout,
            )
            if proc.returncode == 0:
                squeue_states = _parse_batch_squeue_output(proc.stdout or "")
            else:
                detail = proc.stderr or proc.stdout or ""
                if detail.strip():
                    limitations.append(
                        _slurm_command_failure_limitation(
                            command="squeue",
                            stderr=detail,
                            action="batch monitoring",
                        )
                    )
        except subprocess.TimeoutExpired:
            limitations.append(
                f"squeue timed out after {command_timeout:.0f}s during batch monitoring."
            )
        except OSError as exc:
            limitations.append(f"squeue could not be executed: {exc}")

    # --- sacct ---
    if command_available("sacct"):
        try:
            proc = scheduler_runner(
                ["sacct", "-n", "-P", "-j", id_csv, "--format=JobID,State,ExitCode"],
                capture_output=True,
                text=True,
                check=False,
                timeout=command_timeout,
            )
            if proc.returncode == 0:
                sacct_fields_by_id = _parse_batch_sacct_output(proc.stdout or "")
            else:
                detail = proc.stderr or proc.stdout or ""
                if detail.strip():
                    limitations.append(
                        _slurm_command_failure_limitation(
                            command="sacct",
                            stderr=detail,
                            action="batch monitoring",
                        )
                    )
        except subprocess.TimeoutExpired:
            limitations.append(
                f"sacct timed out after {command_timeout:.0f}s during batch monitoring."
            )
        except OSError as exc:
            limitations.append(f"sacct could not be executed: {exc}")

    # --- merge per-job ---
    snapshots: dict[str, SlurmSchedulerSnapshot] = {}
    seen_ids = set(squeue_states) | set(sacct_fields_by_id)
    for job_id in seen_ids:
        sq_state = squeue_states.get(job_id)
        sa_fields = sacct_fields_by_id.get(job_id, {})
        sa_state = _normalize_scheduler_state(sa_fields.get("State"))
        state = sq_state or sa_state
        source = "squeue" if sq_state else "sacct" if sa_state else None
        exit_code = sa_fields.get("ExitCode")
        snapshots[job_id] = SlurmSchedulerSnapshot(
            job_id=job_id,
            scheduler_state=state,
            source=source,
            exit_code=exit_code,
            limitations=tuple(limitations) if not snapshots else (),
        )

    return snapshots


# ---------------------------------------------------------------------------
# Run-directory discovery
# ---------------------------------------------------------------------------


def discover_active_slurm_run_dirs(run_root: Path) -> list[Path]:
    """Return run-record directories holding an active (non-terminal) Slurm job.

    Scans ``run_root`` for sub-directories that contain a
    ``slurm_run_record.json`` whose ``scheduler_state`` is not terminal and
    whose ``cancellation_requested_at`` field is ``None``.  Failed or
    completed records are silently skipped; parse errors are logged but do not
    abort the scan.

    Args:
        run_root: Root directory under ``.runtime/runs/`` where per-run
            directories are stored.

    Returns:
        A list of run-record directories (not JSON file paths) for jobs that
        appear to still be active.
    """
    if not run_root.is_dir():
        return []
    active: list[Path] = []
    for entry in sorted(run_root.iterdir()):
        if not entry.is_dir():
            continue
        record_json = entry / DEFAULT_SLURM_RUN_RECORD_FILENAME
        if not record_json.exists():
            continue
        try:
            record = load_slurm_run_record(entry)
        except Exception as exc:
            _LOG.debug("Skipping run dir %s: %s", entry, exc)
            continue
        state = (record.scheduler_state or "").upper()
        is_terminal = state in _TERMINAL_SLURM_STATES
        is_cancel_requested = record.cancellation_requested_at is not None
        if not is_terminal and not is_cancel_requested:
            active.append(entry)
    return active


# ---------------------------------------------------------------------------
# Synchronous reconciliation helper
# ---------------------------------------------------------------------------


def reconcile_active_slurm_jobs(
    run_root: Path,
    *,
    scheduler_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    command_available: Callable[[str], bool] = _command_is_available,
    command_timeout: float = _DEFAULT_COMMAND_TIMEOUT,
) -> list[SlurmRunRecord]:
    """Discover active jobs, batch-query Slurm, and update durable run records.

    This is the synchronous heart of the monitoring loop.  It is designed to
    be called from ``anyio.to_thread.run_sync`` so it can run blocking
    subprocess calls without stalling the event loop.

    The update sequence for each active record is:

    1. Load the record under an exclusive file lock.
    2. Look up the batch snapshot for the job's ID.
    3. Merge the snapshot into the record (state, exit code, reconciled_at).
    4. Re-classify the failure status.
    5. Save the updated record under the same exclusive lock.

    Records for jobs that did not appear in the batch query are left untouched
    (their existing state is preserved).

    Args:
        run_root: Root directory holding per-run subdirectories.
        scheduler_runner: Injectable subprocess runner.
        command_available: Injectable command-availability checker.
        command_timeout: Per-command timeout in seconds.

    Returns:
        A list of updated :class:`~flytetest.spec_executor.SlurmRunRecord`
        objects (one per record that was actually changed).
    """
    active_dirs = discover_active_slurm_run_dirs(run_root)
    if not active_dirs:
        return []

    # Load job IDs without locking; individual locking happens on the update
    # path below.  A missing record at this point (e.g. deleted between
    # discover and here) is caught by the update-path load.
    job_ids: list[str] = []
    job_id_to_dir: dict[str, Path] = {}
    for run_dir in active_dirs:
        try:
            record = load_slurm_run_record(run_dir)
        except Exception as exc:
            _LOG.debug("Could not reload %s for job-id collection: %s", run_dir, exc)
            continue
        job_ids.append(record.job_id)
        job_id_to_dir[record.job_id] = run_dir

    if not job_ids:
        return []

    snapshots = batch_query_slurm_job_states(
        job_ids,
        scheduler_runner=scheduler_runner,
        command_available=command_available,
        command_timeout=command_timeout,
    )

    updated_records: list[SlurmRunRecord] = []
    for job_id, run_dir in job_id_to_dir.items():
        snapshot = snapshots.get(job_id)
        if snapshot is None or snapshot.scheduler_state is None:
            # Slurm returned nothing for this job; leave the record as-is.
            continue
        try:
            with _exclusive_record_lock(run_dir / DEFAULT_SLURM_RUN_RECORD_FILENAME):
                record = load_slurm_run_record(run_dir)
                # Skip already-terminal records that transitioned before we got
                # here.
                if (record.scheduler_state or "").upper() in _TERMINAL_SLURM_STATES:
                    continue
                final_state = (
                    snapshot.scheduler_state
                    if snapshot.scheduler_state in _TERMINAL_SLURM_STATES
                    else record.final_scheduler_state
                )
                updated = replace(
                    record,
                    scheduler_state=snapshot.scheduler_state,
                    scheduler_state_source=snapshot.source,
                    scheduler_exit_code=snapshot.exit_code or record.scheduler_exit_code,
                    final_scheduler_state=final_state,
                    last_reconciled_at=_created_at(),
                    limitations=tuple(
                        dict.fromkeys((*record.limitations, *snapshot.limitations))
                    ),
                )
                updated = replace(updated, failure_classification=classify_slurm_failure(updated))
                save_slurm_run_record(updated)
                updated_records.append(updated)
                _LOG.debug(
                    "Reconciled job %s → %s (run %s)",
                    job_id,
                    snapshot.scheduler_state,
                    run_dir.name,
                )
        except Exception as exc:
            _LOG.warning("Failed to update run record for job %s: %s", job_id, exc)

    return updated_records


# ---------------------------------------------------------------------------
# Async polling loop
# ---------------------------------------------------------------------------


async def slurm_poll_loop(
    run_root: Path,
    config: SlurmPollingConfig | None = None,
    *,
    scheduler_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    command_available: Callable[[str], bool] = _command_is_available,
) -> None:
    """Continuously reconcile active Slurm jobs in the background.

    Designed to be started as a background task inside the MCP server event
    loop via ``anyio.create_task_group().start_soon(slurm_poll_loop, ...)``.
    The function never returns normally; it runs until the parent task group
    is cancelled (i.e. when the MCP server shuts down).

    Each poll cycle runs the blocking :func:`reconcile_active_slurm_jobs`
    call through ``anyio.to_thread.run_sync`` so it does not stall the event
    loop while ``squeue``/``sacct`` commands are in flight.

    Error handling:

    - Any exception inside one poll cycle is caught, logged at WARNING level,
      and causes the current sleep interval to back off exponentially up to
      ``config.max_backoff_seconds``.
    - A successful cycle resets the sleep interval to
      ``config.poll_interval_seconds``.
    - ``anyio.get_cancelled_exc_class()`` is re-raised immediately so the task
      group shutdown is not swallowed.

    Args:
        run_root: Directory under ``.runtime/runs/`` where Slurm run records
            are stored.
        config: Polling configuration.  Defaults to
            :class:`SlurmPollingConfig` with library defaults when ``None``.
        scheduler_runner: Injectable subprocess runner for testing.
        command_available: Injectable command-availability checker for testing.
    """
    import anyio

    cfg = config or SlurmPollingConfig()
    sleep_seconds = cfg.poll_interval_seconds
    _LOG.debug("Slurm polling loop started (interval=%.0fs)", cfg.poll_interval_seconds)

    while True:
        try:
            updated = await anyio.to_thread.run_sync(
                lambda: reconcile_active_slurm_jobs(
                    run_root,
                    scheduler_runner=scheduler_runner,
                    command_available=command_available,
                    command_timeout=cfg.command_timeout_seconds,
                ),
                # Allow the thread to be abandoned when the task group is
                # cancelled; the blocking subprocess calls are protected by
                # their own per-command timeout.
                abandon_on_cancel=True,
            )
            if updated:
                _LOG.info(
                    "Slurm poll cycle updated %d job record(s).",
                    len(updated),
                )
            sleep_seconds = cfg.poll_interval_seconds
        except anyio.get_cancelled_exc_class():
            _LOG.debug("Slurm polling loop cancelled; exiting.")
            raise
        except Exception as exc:
            sleep_seconds = min(
                sleep_seconds * cfg.backoff_factor, cfg.max_backoff_seconds
            )
            _LOG.warning(
                "Slurm poll cycle failed (%s); backing off to %.0fs.",
                exc,
                sleep_seconds,
            )

        await anyio.sleep(sleep_seconds)
