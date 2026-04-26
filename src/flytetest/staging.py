"""Preflight checks that every container image, tool database, and resolved
input path is reachable on the compute-visible filesystem before a Slurm job
is submitted.  Mirrors DESIGN §7.5's offline-compute invariant — compute nodes
cannot reach the internet, so unreachable paths fail the job silently.

The function returns a list of findings rather than raising; the caller
(``SlurmWorkflowSpecExecutor.submit`` in Step 23, ``validate_run_recipe`` in
Step 24) decides whether to block submission or surface findings as warnings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StagingFinding:
    kind: str    # "container" | "tool_database" | "input_path"
    key: str     # e.g. "braker_sif", "busco_lineage_dir", "ReferenceGenome.fasta_path"
    path: str
    reason: str  # "not_found" | "not_readable" | "not_on_shared_fs"


_KIND_LABELS = {
    "container": "Container",
    "tool_database": "Tool database",
    "input_path": "Input path",
}


def format_finding(finding: StagingFinding) -> str:
    """Render a StagingFinding as one actionable line for a human reader."""
    kind_label = _KIND_LABELS.get(
        finding.kind, finding.kind.replace("_", " ").capitalize()
    )
    head = f"{kind_label} '{finding.key}' at {finding.path}"
    if finding.reason == "not_found":
        return f"{head}: not found."
    if finding.reason == "not_readable":
        return f"{head}: present but not readable by the running user."
    if finding.reason == "not_on_shared_fs":
        return (
            f"{head}: not on the compute-visible filesystem; restage to a"
            " shared mount (e.g. /project or /scratch)."
        )
    return f"{head}: {finding.reason}."


def check_offline_staging(
    artifact,
    shared_fs_roots: tuple[Path, ...],
    *,
    execution_profile: str,
) -> list[StagingFinding]:
    """Inspect a frozen WorkflowSpec artifact and return staging findings.

    Walks ``artifact.runtime_images``, ``artifact.tool_databases``, and
    ``artifact.resolved_input_paths``.  All three are read via ``getattr``
    guards so the function works with both the current ``WorkflowSpec`` shape
    and the reshaped form introduced by later steps.

    ``shared_fs_roots`` names the filesystem prefixes visible to compute nodes
    (e.g. ``/project/...``, ``/scratch/...``).  A path is *on shared fs* when
    one of the roots is a strict ancestor after both paths are fully resolved.

    ``execution_profile="local"`` skips the shared-FS check and verifies only
    existence and readability.  ``execution_profile="slurm"`` enforces both.
    """
    findings: list[StagingFinding] = []

    runtime_images = getattr(artifact, "runtime_images", {}) or {}
    tool_databases = getattr(artifact, "tool_databases", {}) or {}
    resolved_input_paths = getattr(artifact, "resolved_input_paths", {}) or {}

    for key, image_path in runtime_images.items():
        findings.extend(
            _check_path("container", key, image_path, shared_fs_roots, execution_profile)
        )
    for key, db_path in tool_databases.items():
        findings.extend(
            _check_path("tool_database", key, db_path, shared_fs_roots, execution_profile)
        )
    for key, input_path in resolved_input_paths.items():
        findings.extend(
            _check_path("input_path", key, input_path, shared_fs_roots, execution_profile)
        )

    return findings


def _check_path(
    kind: str,
    key: str,
    path: str,
    shared_fs_roots: tuple[Path, ...],
    execution_profile: str,
) -> list[StagingFinding]:
    """Return zero or more StagingFindings for one path.

    Check order: ``not_found`` → ``not_readable`` → ``not_on_shared_fs``
    (slurm only).

    Uses ``Path.resolve(strict=True)`` so that broken symlinks (the link inode
    exists but the target does not) surface as ``not_readable`` rather than
    ``not_found``.  ``not_found`` is reserved for paths where no filesystem
    entry exists at all.
    """
    findings: list[StagingFinding] = []
    p = Path(path)

    # Path.exists() follows symlinks — a broken symlink appears as missing.
    # Distinguish "no entry at all" from "broken symlink" with lstat(), which
    # does not follow symlinks.
    if not p.exists():
        try:
            p.lstat()
            # lstat() succeeded → the link inode is present but the target is gone.
            findings.append(StagingFinding(kind=kind, key=key, path=path, reason="not_readable"))
        except OSError:
            findings.append(StagingFinding(kind=kind, key=key, path=path, reason="not_found"))
        return findings

    # Resolve strictly to catch any remaining unresolvable edge cases.
    try:
        resolved = p.resolve(strict=True)
    except OSError:
        findings.append(StagingFinding(kind=kind, key=key, path=path, reason="not_readable"))
        return findings

    # Readability check on the resolved target.
    if not os.access(resolved, os.R_OK):
        findings.append(StagingFinding(kind=kind, key=key, path=path, reason="not_readable"))
        return findings

    # Shared-FS membership — only for slurm profile when roots are provided.
    if execution_profile == "slurm" and shared_fs_roots:
        on_shared = False
        for root in shared_fs_roots:
            try:
                resolved_root = root.resolve(strict=True)
            except OSError:
                continue  # root absent on this host — skip it
            if resolved.is_relative_to(resolved_root):
                on_shared = True
                break
        if not on_shared:
            findings.append(
                StagingFinding(kind=kind, key=key, path=path, reason="not_on_shared_fs")
            )

    return findings
