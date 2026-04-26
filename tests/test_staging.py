"""Tests for the staging preflight module (DESIGN §7.5)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from flytetest.staging import StagingFinding, _check_path, check_offline_staging, format_finding


# ---------------------------------------------------------------------------
# Minimal stub for a WorkflowSpec artifact
# ---------------------------------------------------------------------------

@dataclass
class _Artifact:
    runtime_images: dict[str, str] = field(default_factory=dict)
    tool_databases: dict[str, str] = field(default_factory=dict)
    resolved_input_paths: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _findings_by_reason(findings: list[StagingFinding], reason: str) -> list[StagingFinding]:
    return [f for f in findings if f.reason == reason]


# ---------------------------------------------------------------------------
# Missing paths (not_found)
# ---------------------------------------------------------------------------

class TestNotFound:
    def test_missing_container_kind_and_reason(self):
        artifact = _Artifact(runtime_images={"braker_sif": "/no/such/braker3.sif"})
        findings = check_offline_staging(artifact, (), execution_profile="slurm")
        assert len(findings) == 1
        f = findings[0]
        assert f.kind == "container"
        assert f.key == "braker_sif"
        assert f.path == "/no/such/braker3.sif"
        assert f.reason == "not_found"

    def test_missing_tool_database_kind(self):
        artifact = _Artifact(tool_databases={"busco_lineage_dir": "/no/such/lineage"})
        findings = check_offline_staging(artifact, (), execution_profile="slurm")
        assert len(findings) == 1
        assert findings[0].kind == "tool_database"
        assert findings[0].reason == "not_found"

    def test_missing_resolved_input_path_kind(self):
        artifact = _Artifact(resolved_input_paths={"genome_fa": "/no/such/genome.fa"})
        findings = check_offline_staging(artifact, (), execution_profile="local")
        assert len(findings) == 1
        assert findings[0].kind == "input_path"
        assert findings[0].reason == "not_found"

    def test_local_profile_surfaces_not_found(self):
        artifact = _Artifact(runtime_images={"sif": "/no/such/tool.sif"})
        findings = check_offline_staging(artifact, (), execution_profile="local")
        assert any(f.reason == "not_found" for f in findings)

    def test_multiple_missing_paths_all_reported(self):
        artifact = _Artifact(
            runtime_images={"sif": "/no/sif.sif"},
            tool_databases={"db": "/no/db"},
        )
        findings = check_offline_staging(artifact, (), execution_profile="slurm")
        assert len(findings) == 2


# ---------------------------------------------------------------------------
# Shared-FS membership (not_on_shared_fs)
# ---------------------------------------------------------------------------

class TestSharedFs:
    def test_resolved_input_outside_roots_slurm(self, tmp_path):
        file = tmp_path / "genome.fa"
        file.write_text("ACGT")

        other_root = tmp_path / "shared"
        other_root.mkdir()

        artifact = _Artifact(resolved_input_paths={"genome_fa": str(file)})
        findings = check_offline_staging(
            artifact, (other_root,), execution_profile="slurm"
        )
        assert len(findings) == 1
        assert findings[0].reason == "not_on_shared_fs"
        assert findings[0].kind == "input_path"

    def test_file_under_shared_root_no_findings(self, tmp_path):
        shared = tmp_path / "project"
        shared.mkdir()
        sif = shared / "braker3.sif"
        sif.write_text("")
        db = shared / "lineage"
        db.mkdir()
        ref = shared / "genome.fa"
        ref.write_text("ACGT")

        artifact = _Artifact(
            runtime_images={"braker_sif": str(sif)},
            tool_databases={"busco_lineage": str(db)},
            resolved_input_paths={"genome_fa": str(ref)},
        )
        findings = check_offline_staging(
            artifact, (shared,), execution_profile="slurm"
        )
        assert findings == []

    def test_multiple_roots_any_match_passes(self, tmp_path):
        root_a = tmp_path / "scratch"
        root_a.mkdir()
        root_b = tmp_path / "project"
        root_b.mkdir()
        file = root_b / "input.fa"
        file.write_text("ACGT")

        artifact = _Artifact(resolved_input_paths={"input_fa": str(file)})
        findings = check_offline_staging(
            artifact, (root_a, root_b), execution_profile="slurm"
        )
        assert findings == []

    def test_local_profile_ignores_shared_fs_check(self, tmp_path):
        other_root = tmp_path / "shared"
        other_root.mkdir()
        file = tmp_path / "genome.fa"
        file.write_text("ACGT")

        artifact = _Artifact(resolved_input_paths={"genome_fa": str(file)})
        findings = check_offline_staging(
            artifact, (other_root,), execution_profile="local"
        )
        # local profile: file exists and is readable — no findings expected
        assert findings == []

    def test_slurm_empty_roots_skip_shared_check(self, tmp_path):
        file = tmp_path / "genome.fa"
        file.write_text("ACGT")

        artifact = _Artifact(resolved_input_paths={"genome_fa": str(file)})
        # No shared_fs_roots provided → shared-FS check skipped even for slurm
        findings = check_offline_staging(artifact, (), execution_profile="slurm")
        assert findings == []


# ---------------------------------------------------------------------------
# Broken symlinks (not_readable)
# ---------------------------------------------------------------------------

class TestBrokenSymlink:
    def test_broken_symlink_is_not_readable(self, tmp_path):
        target = tmp_path / "nonexistent_target.sif"
        link = tmp_path / "link.sif"
        link.symlink_to(target)

        artifact = _Artifact(runtime_images={"sif": str(link)})
        findings = check_offline_staging(artifact, (), execution_profile="local")
        assert len(findings) == 1
        assert findings[0].reason == "not_readable"
        assert findings[0].kind == "container"


# ---------------------------------------------------------------------------
# getattr guards (artifact without expected attributes)
# ---------------------------------------------------------------------------

class TestGetAttrGuard:
    def test_artifact_with_no_attributes_returns_empty(self):
        class _Bare:
            pass

        findings = check_offline_staging(_Bare(), (), execution_profile="local")
        assert findings == []

    def test_artifact_with_none_tool_databases_returns_empty(self, tmp_path):
        class _PartialArtifact:
            runtime_images = {}
            tool_databases = None          # None → guarded to {}
            resolved_input_paths = {}

        findings = check_offline_staging(_PartialArtifact(), (), execution_profile="local")
        assert findings == []


# ---------------------------------------------------------------------------
# StagingFinding dataclass
# ---------------------------------------------------------------------------

class TestStagingFinding:
    def test_is_frozen(self):
        f = StagingFinding(kind="container", key="sif", path="/p", reason="not_found")
        with pytest.raises((AttributeError, TypeError)):
            f.kind = "other"  # type: ignore[misc]

    def test_fields(self):
        f = StagingFinding(
            kind="tool_database",
            key="busco_lineage_dir",
            path="/data/lineage",
            reason="not_on_shared_fs",
        )
        assert f.kind == "tool_database"
        assert f.key == "busco_lineage_dir"
        assert f.path == "/data/lineage"
        assert f.reason == "not_on_shared_fs"


# ---------------------------------------------------------------------------
# _check_path unit tests
# ---------------------------------------------------------------------------

class TestCheckPath:
    def test_existing_readable_file_no_findings(self, tmp_path):
        f = tmp_path / "genome.fa"
        f.write_text("ACGT")
        result = _check_path("input_path", "genome_fa", str(f), (), "local")
        assert result == []

    def test_nonexistent_path_not_found(self):
        result = _check_path("container", "sif", "/no/such/file.sif", (), "slurm")
        assert len(result) == 1
        assert result[0].reason == "not_found"

    def test_path_outside_root_slurm(self, tmp_path):
        f = tmp_path / "file.fa"
        f.write_text("X")
        other_root = tmp_path / "other"
        other_root.mkdir()
        result = _check_path("input_path", "key", str(f), (other_root,), "slurm")
        assert len(result) == 1
        assert result[0].reason == "not_on_shared_fs"

    def test_path_inside_root_slurm_no_findings(self, tmp_path):
        f = tmp_path / "file.fa"
        f.write_text("X")
        result = _check_path("input_path", "key", str(f), (tmp_path,), "slurm")
        assert result == []


class TestFormatFinding:
    def test_not_found_message_includes_path_and_kind(self):
        finding = StagingFinding(
            kind="container",
            key="braker_sif",
            path="data/images/braker3.sif",
            reason="not_found",
        )
        message = format_finding(finding)
        assert message
        assert "data/images/braker3.sif" in message
        assert "Container" in message
        assert "not found" in message

    def test_not_readable_message_includes_path_and_kind(self):
        finding = StagingFinding(
            kind="tool_database",
            key="busco_lineage_dir",
            path="/scratch/busco/lineages",
            reason="not_readable",
        )
        message = format_finding(finding)
        assert message
        assert "/scratch/busco/lineages" in message
        assert "Tool database" in message
        assert "not readable" in message

    def test_not_on_shared_fs_message_includes_path_and_kind(self):
        finding = StagingFinding(
            kind="input_path",
            key="ReferenceGenome.fasta_path",
            path="/tmp/ref.fa",
            reason="not_on_shared_fs",
        )
        message = format_finding(finding)
        assert message
        assert "/tmp/ref.fa" in message
        assert "Input path" in message
        assert "shared" in message
