"""Read-only Slurm introspection helpers (no auth required).

Slurm UX rollout Phase 0 step 05.  Surfaces partition names and limits
to the user before recipe freeze so unknown partitions are caught
earlier than the sbatch attempt.  ``sinfo`` is a read-only command and
requires no authentication, so the helper is safe to expose as an MCP
tool.

Account-level introspection (``sshare``) is deferred to Phase 1 step 11
because it needs the user's Slurm account context.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TypedDict


class SlurmPartitionInfo(TypedDict):
    """One ``sinfo`` row reshaped for MCP-friendly consumption.

    Fields match the columns requested by :func:`list_slurm_partitions`'
    ``sinfo --format`` invocation; missing or unparseable values fall
    back to safe defaults rather than raising so a single malformed row
    does not break the whole listing.
    """

    name: str
    state: str
    max_walltime: str
    available_nodes: int
    total_nodes: int


def list_slurm_partitions() -> list[SlurmPartitionInfo]:
    """Return the cluster's partitions and their limits.

    Wraps ``sinfo --noheader --format='%P %a %l %D %A'``:

    - ``%P`` partition name (default partition has a trailing ``*``)
    - ``%a`` availability (``up`` / ``down`` / ``drain``)
    - ``%l`` time-limit (``D-HH:MM:SS`` or ``INFINITE``)
    - ``%D`` total node count
    - ``%A`` ``allocated/idle`` node counts (idle == "available")

    Raises ``FileNotFoundError`` when ``sinfo`` is missing on PATH and
    ``subprocess.CalledProcessError`` when sinfo exits non-zero; the
    MCP wrapper in ``server.py`` translates both into structured
    ``{supported: False, ...}`` replies.
    """
    if shutil.which("sinfo") is None:
        raise FileNotFoundError(
            "sinfo not found on PATH; this MCP tool requires Slurm to be available."
        )

    proc = subprocess.run(
        ["sinfo", "--noheader", "--format=%P %a %l %D %A"],
        capture_output=True,
        text=True,
        check=True,
    )
    partitions: list[SlurmPartitionInfo] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        name, state, max_walltime, total_nodes_s, alloc_idle = parts[:5]
        idle_token = alloc_idle.split("/")[1] if "/" in alloc_idle else "0"
        try:
            total_nodes = int(total_nodes_s)
        except ValueError:
            total_nodes = 0
        try:
            available_nodes = int(idle_token)
        except ValueError:
            available_nodes = 0
        partitions.append(
            {
                "name": name.rstrip("*"),
                "state": state,
                "max_walltime": max_walltime,
                "available_nodes": available_nodes,
                "total_nodes": total_nodes,
            }
        )
    return partitions


def list_slurm_partitions_reply() -> dict[str, object]:
    """Wrap :func:`list_slurm_partitions` in a structured reply for MCP.

    Failures (missing ``sinfo``, non-zero exit) become
    ``{supported: False, reason, message}`` records consistent with
    the rest of the MCP surface, so the client never sees a Python
    exception trace.
    """
    try:
        partitions = list_slurm_partitions()
    except FileNotFoundError as exc:
        return {
            "supported": False,
            "reason": "sinfo_unavailable",
            "message": str(exc),
            "partitions": [],
        }
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "").strip() or "sinfo returned non-zero exit code"
        return {
            "supported": False,
            "reason": "sinfo_failed",
            "message": message,
            "partitions": [],
        }
    return {"supported": True, "partitions": partitions}


__all__ = [
    "SlurmPartitionInfo",
    "list_slurm_partitions",
    "list_slurm_partitions_reply",
]
