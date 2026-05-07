# Step 05 — list_slurm_partitions MCP tool

## Context

Users have to know their cluster's valid `partition` strings before freezing a recipe. There's no introspection — typos surface at sbatch time. `sinfo` is read-only and requires no auth, so a Phase 0 MCP wrapper is cheap and high-leverage. Account validation (`sshare`, which needs user account context) is deferred to Phase 1 step 11.

## Files to read before editing

- `src/flytetest/slurm_monitor.py` — existing Slurm-shell-out patterns (subprocess invocation, error handling, JSON-friendly return shapes)
- `src/flytetest/server.py` — where existing Slurm MCP tools (`run_slurm_recipe`, `monitor_slurm_job`, `cancel_slurm_job`, `retry_slurm_job`) are registered
- `src/flytetest/mcp_contract.py` — tool name constant and `TOOL_DESCRIPTIONS` patterns
- `sinfo --help` (run on RCC if accessible) — confirm available format codes

## Files to create / edit

| Action | File |
|---|---|
| Create or Extend | `src/flytetest/slurm_introspection.py` (or extend `slurm_monitor.py`) |
| Edit | `src/flytetest/server.py` |
| Edit | `src/flytetest/mcp_contract.py` |
| Edit | `tests/test_slurm_introspection.py` (or matching) |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### `src/flytetest/slurm_introspection.py` (new file or addition)

```python
"""Read-only Slurm introspection helpers (no auth required).

list_slurm_partitions wraps `sinfo` to surface partition names and
limits to the user before recipe freeze, so unknown partitions are
caught earlier than the sbatch attempt.
"""
from __future__ import annotations

import shutil
import subprocess
from typing import TypedDict


class SlurmPartitionInfo(TypedDict):
    name: str
    state: str           # "up" | "down" | "drained" | "unknown"
    max_walltime: str    # e.g., "1-00:00:00" or "INFINITE"
    max_nodes: str | int
    available_nodes: int  # currently available
    total_nodes: int


def list_slurm_partitions() -> list[SlurmPartitionInfo]:
    """Return the cluster's partitions and their limits.

    Wraps `sinfo --noheader --format='%P %a %l %D %A'`. Missing
    `sinfo` is reported via raised `FileNotFoundError`; sinfo failures
    bubble up as `subprocess.CalledProcessError`. The MCP tool
    registration in server.py converts these to structured replies.
    """
    if shutil.which("sinfo") is None:
        raise FileNotFoundError("sinfo not found on PATH; this MCP tool requires Slurm.")

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
        # %P=partition, %a=avail (up|down|...), %l=time-limit, %D=node-count, %A=avail/idle
        parts = line.split()
        if len(parts) < 5:
            continue
        name, state, max_walltime, total_nodes_s, alloc_idle = parts[:5]
        # alloc_idle format is "alloc/idle" or "alloc/idle/other/total"
        idle_token = alloc_idle.split("/")[1] if "/" in alloc_idle else "0"
        try:
            total_nodes = int(total_nodes_s)
            available_nodes = int(idle_token)
        except ValueError:
            total_nodes = 0
            available_nodes = 0
        partitions.append(
            {
                "name": name.rstrip("*"),  # default partition is marked with trailing *
                "state": state,
                "max_walltime": max_walltime,
                "max_nodes": "*",
                "available_nodes": available_nodes,
                "total_nodes": total_nodes,
            }
        )
    return partitions
```

### `src/flytetest/mcp_contract.py`

Add a tool name constant and description:

```python
LIST_SLURM_PARTITIONS_TOOL_NAME = "list_slurm_partitions"

TOOL_DESCRIPTIONS[LIST_SLURM_PARTITIONS_TOOL_NAME] = (
    "Return the cluster's Slurm partitions with their state, walltime "
    "limit, and current availability. Read-only; uses `sinfo`. Useful "
    "before freezing a recipe so the user can pick a valid partition. "
    "No arguments required."
)
```

Add `LIST_SLURM_PARTITIONS_TOOL_NAME` to whichever group is appropriate (likely a new "introspection" group or under the existing Slurm tool group).

### `src/flytetest/server.py`

In `create_mcp_server()`, register the tool:

```python
from flytetest.slurm_introspection import list_slurm_partitions

@mcp.tool(name=LIST_SLURM_PARTITIONS_TOOL_NAME, description=TOOL_DESCRIPTIONS[LIST_SLURM_PARTITIONS_TOOL_NAME])
def _list_slurm_partitions() -> dict:
    """Return cluster partitions or a structured failure reply."""
    try:
        partitions = list_slurm_partitions()
        return {"supported": True, "partitions": partitions}
    except FileNotFoundError as exc:
        return {"supported": False, "reason": "sinfo_unavailable", "message": str(exc)}
    except subprocess.CalledProcessError as exc:
        return {
            "supported": False,
            "reason": "sinfo_failed",
            "message": (exc.stderr or "").strip() or "sinfo returned non-zero exit code",
        }
```

### Tests

Use `subprocess.run` mocking via `unittest.mock.patch`:

```python
@patch("flytetest.slurm_introspection.subprocess.run")
@patch("flytetest.slurm_introspection.shutil.which", return_value="/usr/bin/sinfo")
def test_list_partitions_parses_sinfo_output(mock_which, mock_run):
    mock_run.return_value = Mock(
        stdout=(
            "caslake* up 1-00:00:00 200 50/100/0/200\n"
            "broadwl up 2-00:00:00 100 5/95/0/100\n"
        ),
        stderr="",
        returncode=0,
    )
    result = list_slurm_partitions()
    assert result[0]["name"] == "caslake"
    assert result[0]["max_walltime"] == "1-00:00:00"
    assert result[0]["available_nodes"] == 100  # idle field
```

Add a test for the `sinfo not found` path:

```python
@patch("flytetest.slurm_introspection.shutil.which", return_value=None)
def test_list_partitions_raises_when_sinfo_missing(mock_which):
    with pytest.raises(FileNotFoundError):
        list_slurm_partitions()
```

## Acceptance criteria

- `list_slurm_partitions()` returns a non-empty list when run on a cluster with `sinfo`
- Mocked sinfo output parses correctly (name, state, max_walltime, available_nodes, total_nodes)
- Missing `sinfo` returns `{"supported": False, "reason": "sinfo_unavailable", ...}` from the MCP layer
- `python -m pytest tests/test_slurm_introspection.py` passes

## CHANGELOG entry template

```
## Unreleased

### Slurm UX rollout — Phase 0 step 05 (2026-05-07)

- [x] 2026-05-07 `slurm_introspection.py` (new): `list_slurm_partitions()` wraps `sinfo` to return structured partition info (name, state, max_walltime, available/total nodes). No auth required.
- [x] 2026-05-07 `mcp_contract.py`: `LIST_SLURM_PARTITIONS_TOOL_NAME` and `TOOL_DESCRIPTIONS` entry.
- [x] 2026-05-07 `server.py`: tool registered in `create_mcp_server()`. Failure modes (missing sinfo, sinfo error) surface as structured replies with `supported: False`.
```
