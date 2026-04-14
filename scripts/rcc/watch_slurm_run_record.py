#!/usr/bin/env python3
"""Passively watch one durable Slurm run record for poll-loop updates.

This helper is intentionally read-only. It does not call
``monitor_slurm_job()``, ``reconcile_active_slurm_jobs()``, or any MCP/server
boundary that would mutate the record itself. Instead it reloads the saved
JSON file at a fixed interval and prints one compact JSON snapshot per cycle so
an RCC session can prove that the background ``slurm_poll_loop()`` running
inside the MCP server is updating the durable record on its own.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SLURM_RUN_RECORD_FILENAME = "slurm_run_record.json"


def _created_at() -> str:
    """Return one UTC timestamp for emitted watcher snapshots."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _mtime_at(path: Path) -> str:
    """Return the current file mtime in UTC ISO-8601 format."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _resolve_run_record_path(raw_path: Path) -> Path:
    """Resolve the user-supplied CLI path to the concrete slurm_run_record.json.

    Three path forms are accepted because the record shows up differently
    depending on how the caller obtained it:

    - A run directory: the MCP server returns the run directory, not the JSON
      file path, in its submission response.  Appending the standard filename
      avoids making the caller know the internal layout.
    - A ``.txt`` pointer file: the convenience scripts in ``scripts/rcc/``
      write the current record path into ``latest_slurm_run_record.txt`` after
      each submission so the same watch invocation works without copy-pasting
      the full run directory name.  The pointer may itself point at a directory,
      so the resolution is recursive.
    - A direct JSON path: used in tests and when the caller already has the
      exact path from a prior ``ls`` or log line.

    Args:
        raw_path: User-supplied path from the CLI positional argument.

    Returns:
        Concrete path to ``slurm_run_record.json`` ready for periodic reload.
    """
    if raw_path.is_dir():
        return raw_path / DEFAULT_SLURM_RUN_RECORD_FILENAME
    if raw_path.is_file() and raw_path.suffix == ".txt":
        pointed_path = raw_path.read_text(encoding="utf-8").strip()
        if not pointed_path:
            raise SystemExit(f"pointer file is empty: {raw_path}")
        return _resolve_run_record_path(Path(pointed_path))
    return raw_path


def _load_snapshot(run_record_path: Path, *, cycle: int) -> dict[str, Any]:
    """Read the current record from disk and extract the fields that prove poll-loop activity.

    Only a small projection of the full 40+ field record is returned.  The
    selected fields are the minimum set needed to verify that the background
    ``slurm_poll_loop()`` inside the MCP server is writing to the record:

    - ``scheduler_state`` and ``scheduler_state_source`` change when
      ``squeue`` or ``sacct`` returns a new state.
    - ``last_reconciled_at`` is the timestamp written by
      ``reconcile_active_slurm_jobs()`` on every successful update cycle;
      its progression across snapshots proves the loop is running.
    - ``final_scheduler_state`` signals that the job has entered a terminal
      state so the watcher can exit cleanly without polling indefinitely.
    - ``file_mtime`` is read directly from the filesystem rather than from the
      JSON payload, so it catches any write to the file even if the embedded
      fields are unchanged (e.g. a retry that rewrites the record).

    Args:
        run_record_path: Concrete durable JSON record path to reload on this
            cycle.  The file is re-read from disk every call so changes written
            by the MCP server between cycles are reflected immediately.
        cycle: One-based watch iteration counter embedded in the output so a
            reader can tell at which snapshot ``last_reconciled_at`` first
            changed.

    Returns:
        Compact dict suitable for ``json.dumps`` and line-by-line streaming
        to stdout.
    """
    payload = json.loads(run_record_path.read_text(encoding="utf-8"))
    return {
        "poll_iteration": cycle,
        "observed_at": _created_at(),
        "run_record_path": str(run_record_path),
        "job_id": payload.get("job_id"),
        "scheduler_state": payload.get("scheduler_state"),
        "scheduler_state_source": payload.get("scheduler_state_source"),
        "last_reconciled_at": payload.get("last_reconciled_at"),
        "final_scheduler_state": payload.get("final_scheduler_state"),
        "scheduler_exit_code": payload.get("scheduler_exit_code"),
        "file_mtime": _mtime_at(run_record_path),
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI flags for the passive run-record watcher."""
    parser = argparse.ArgumentParser(
        description=(
            "Reload one durable Slurm run record at a fixed interval without "
            "calling the monitor helper."
        )
    )
    parser.add_argument(
        "run_record_path",
        help=(
            "Path to slurm_run_record.json, a run directory containing it, or "
            "a pointer file whose contents are the real record path."
        ),
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=15.0,
        help="Seconds to wait between passive reloads. Default: 15.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help=(
            "Maximum number of snapshots to print before exiting. Omit it to "
            "keep watching until the record reports a terminal state."
        ),
    )
    args = parser.parse_args(argv[1:])
    if args.interval_seconds <= 0:
        raise SystemExit("--interval-seconds must be > 0")
    if args.max_cycles is not None and args.max_cycles <= 0:
        raise SystemExit("--max-cycles must be > 0 when provided")
    return args


def main(argv: list[str]) -> int:
    """Watch one durable Slurm run record and print a JSON snapshot each cycle.

    Prints one compact JSON line per cycle to stdout so the output can be
    piped, redirected, or inspected live in an RCC terminal.  Runs until one
    of three stopping conditions is met:

    - The record's ``final_scheduler_state`` is set (job reached a terminal
      Slurm state); exits 0 so callers can use the exit code as a success
      signal.
    - ``--max-cycles`` snapshots have been emitted; exits 0.
    - The user sends SIGINT (Ctrl-C); exits 130, matching the standard
      shell convention for Ctrl-C termination.

    Does not call any MCP handler, monitor helper, or scheduler command.
    The only side effect is reading the JSON file from disk on each cycle.
    """
    args = _parse_args(argv)
    run_record_path = _resolve_run_record_path(Path(args.run_record_path))
    if not run_record_path.is_file():
        raise SystemExit(f"run record not found: {run_record_path}")

    cycle = 0
    try:
        while True:
            cycle += 1
            snapshot = _load_snapshot(run_record_path, cycle=cycle)
            print(json.dumps(snapshot, sort_keys=True), flush=True)
            if snapshot["final_scheduler_state"] is not None:
                return 0
            if args.max_cycles is not None and cycle >= args.max_cycles:
                return 0
            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))