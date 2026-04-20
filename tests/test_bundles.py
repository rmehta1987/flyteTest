"""Tests for the bundles module: ResourceBundle, BundleAvailability, list_bundles, load_bundle."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

import flytetest.bundles as bundles_mod
from flytetest.bundles import (
    BUNDLES,
    BundleAvailability,
    ResourceBundle,
    _check_bundle_availability,
    list_bundles,
    load_bundle,
)


class TestListBundles:
    def test_returns_all_seeded_bundles(self):
        results = list_bundles()
        assert len(results) == len(BUNDLES)
        names = {r["name"] for r in results}
        assert names == set(BUNDLES)

    def test_each_result_has_availability_fields(self):
        for entry in list_bundles():
            assert isinstance(entry["available"], bool)
            assert isinstance(entry["reasons"], list)
            assert "name" in entry
            assert "description" in entry
            assert "pipeline_family" in entry
            assert "applies_to" in entry
            assert "binding_types" in entry

    def test_filter_annotation_returns_only_annotation(self):
        annotation = list_bundles(pipeline_family="annotation")
        assert len(annotation) > 0
        for entry in annotation:
            assert entry["pipeline_family"] == "annotation"

    def test_filter_unknown_family_returns_empty(self):
        assert list_bundles(pipeline_family="variant_calling") == []

    def test_filter_annotation_matches_all_seeds(self):
        # All four seed bundles are annotation family; filtering should return the same count.
        all_results = list_bundles()
        annotation = list_bundles(pipeline_family="annotation")
        assert len(annotation) == len(all_results)


class TestLoadBundle:
    def test_happy_path_m18_busco_demo(self, monkeypatch):
        """m18_busco_demo returns full typed inputs when paths are present."""
        monkeypatch.setattr(Path, "exists", lambda self: True)
        result = load_bundle("m18_busco_demo")
        assert result["supported"] is True
        assert "bindings" in result
        assert "inputs" in result
        assert "runtime_images" in result
        assert "tool_databases" in result
        assert "description" in result
        assert "pipeline_family" in result

    def test_happy_path_m18_busco_demo_binding_keys(self, monkeypatch):
        monkeypatch.setattr(Path, "exists", lambda self: True)
        result = load_bundle("m18_busco_demo")
        assert "QualityAssessmentTarget" in result["bindings"]
        assert result["inputs"]["lineage_dataset"] == "eukaryota_odb10"
        assert "busco_sif" in result["runtime_images"]
        assert "busco_lineage_dir" in result["tool_databases"]

    def test_unknown_name_raises_key_error(self):
        with pytest.raises(KeyError) as exc_info:
            load_bundle("nonexistent")
        msg = str(exc_info.value)
        for name in BUNDLES:
            assert name in msg

    def test_unknown_name_error_lists_available(self):
        with pytest.raises(KeyError) as exc_info:
            load_bundle("completely_unknown_bundle")
        msg = str(exc_info.value)
        assert "braker3_small_eukaryote" in msg
        assert "m18_busco_demo" in msg

    def test_missing_container_returns_unsupported(self, monkeypatch):
        fake = ResourceBundle(
            name="test_missing_container",
            description="Test bundle with a nonexistent container image.",
            pipeline_family="annotation",
            bindings={},
            inputs={},
            runtime_images={"sif": "data/images/nonexistent_tool_xyz.sif"},
            tool_databases={},
            applies_to=(),
        )
        patched = {**BUNDLES, "test_missing_container": fake}
        monkeypatch.setattr(bundles_mod, "BUNDLES", patched)
        result = load_bundle("test_missing_container")
        assert result["supported"] is False
        assert any("nonexistent_tool_xyz.sif" in r for r in result["reasons"])

    def test_unsupported_reply_has_next_steps(self, monkeypatch):
        fake = ResourceBundle(
            name="test_no_paths",
            description="Bundle with no resolvable paths.",
            pipeline_family="annotation",
            bindings={"ReferenceGenome": {"fasta_path": "/no/such/genome.fa"}},
            inputs={},
            runtime_images={},
            tool_databases={},
            applies_to=(),
        )
        patched = {**BUNDLES, "test_no_paths": fake}
        monkeypatch.setattr(bundles_mod, "BUNDLES", patched)
        result = load_bundle("test_no_paths")
        assert result["supported"] is False
        assert isinstance(result["next_steps"], list)
        assert len(result["next_steps"]) > 0


class TestCheckBundleAvailability:
    def test_returns_bundle_availability_instance(self):
        b = next(iter(BUNDLES.values()))
        result = _check_bundle_availability(b)
        assert isinstance(result, BundleAvailability)
        assert result.name == b.name

    def test_available_flag_is_bool(self):
        for b in BUNDLES.values():
            result = _check_bundle_availability(b)
            assert isinstance(result.available, bool)

    def test_missing_binding_path_reported(self):
        b = ResourceBundle(
            name="test_missing_binding",
            description="",
            pipeline_family="annotation",
            bindings={"ReferenceGenome": {"fasta_path": "/nonexistent/path/genome.fa"}},
            inputs={},
            runtime_images={},
            tool_databases={},
            applies_to=(),
        )
        result = _check_bundle_availability(b)
        assert result.available is False
        assert any("/nonexistent/path/genome.fa" in r for r in result.reasons)

    def test_missing_tool_database_reported(self):
        b = ResourceBundle(
            name="test_missing_db",
            description="",
            pipeline_family="annotation",
            bindings={},
            inputs={},
            runtime_images={},
            tool_databases={"lineage": "/nonexistent/lineage/dir"},
            applies_to=(),
        )
        result = _check_bundle_availability(b)
        assert result.available is False
        assert any("/nonexistent/lineage/dir" in r for r in result.reasons)

    def test_unknown_applies_to_entry_reported(self):
        b = ResourceBundle(
            name="test_bad_applies_to",
            description="",
            pipeline_family="annotation",
            bindings={},
            inputs={},
            runtime_images={},
            tool_databases={},
            applies_to=("nonexistent_workflow_xyz",),
        )
        result = _check_bundle_availability(b)
        assert result.available is False
        assert any("nonexistent_workflow_xyz" in r for r in result.reasons)

    def test_pipeline_family_mismatch_reported(self):
        b = ResourceBundle(
            name="test_family_mismatch",
            description="",
            pipeline_family="wrong_family",
            bindings={},
            inputs={},
            runtime_images={},
            tool_databases={},
            applies_to=("annotation_qc_busco",),
        )
        result = _check_bundle_availability(b)
        assert result.available is False
        assert any("wrong_family" in r for r in result.reasons)

    def test_non_path_binding_fields_not_checked(self, monkeypatch):
        exists_calls: list[str] = []

        def tracking_exists(self: Path) -> bool:
            exists_calls.append(str(self))
            return True

        monkeypatch.setattr(Path, "exists", tracking_exists)
        b = ResourceBundle(
            name="test_scalar_only",
            description="",
            pipeline_family="annotation",
            bindings={"ReferenceGenome": {"sample_id": "demo", "cpu": 4}},
            inputs={},
            runtime_images={},
            tool_databases={},
            applies_to=(),
        )
        _check_bundle_availability(b)
        assert not any("sample_id" in c or "cpu" in c for c in exists_calls)


class TestStartupRobustness:
    def test_server_imports_without_bundle_path_validation(self):
        """server.py imports cleanly regardless of which bundle paths are present."""
        src = str(Path(__file__).resolve().parent.parent / "src")
        env = {**os.environ, "PYTHONPATH": src}
        result = subprocess.run(
            [sys.executable, "-c", "import flytetest.server"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr
