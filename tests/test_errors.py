"""Tests for the PlannerResolutionError typed exception hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flytetest.errors import (
    BindingPathMissingError,
    ManifestNotFoundError,
    PlannerResolutionError,
    UnknownOutputNameError,
    UnknownRunIdError,
)


class TestUnknownRunIdError:
    def test_attributes(self):
        exc = UnknownRunIdError(run_id="run-abc", available_count=3)
        assert exc.run_id == "run-abc"
        assert exc.available_count == 3

    def test_str_contains_run_id(self):
        exc = UnknownRunIdError(run_id="run-abc", available_count=3)
        assert "run-abc" in str(exc)

    def test_is_planner_resolution_error(self):
        exc = UnknownRunIdError(run_id="run-abc", available_count=3)
        assert isinstance(exc, PlannerResolutionError)


class TestUnknownOutputNameError:
    def test_attributes(self):
        exc = UnknownOutputNameError(
            run_id="run-xyz",
            output_name="assembly_fasta",
            known_outputs=("gff3", "stats"),
        )
        assert exc.run_id == "run-xyz"
        assert exc.output_name == "assembly_fasta"
        assert exc.known_outputs == ("gff3", "stats")

    def test_str_contains_run_id_and_output_name(self):
        exc = UnknownOutputNameError(
            run_id="run-xyz",
            output_name="assembly_fasta",
            known_outputs=("gff3", "stats"),
        )
        assert "run-xyz" in str(exc)
        assert "assembly_fasta" in str(exc)

    def test_str_contains_known_outputs(self):
        exc = UnknownOutputNameError(
            run_id="run-xyz",
            output_name="assembly_fasta",
            known_outputs=("gff3", "stats"),
        )
        assert "gff3" in str(exc)
        assert "stats" in str(exc)

    def test_empty_known_outputs(self):
        exc = UnknownOutputNameError(
            run_id="run-xyz",
            output_name="missing",
            known_outputs=(),
        )
        assert exc.known_outputs == ()
        assert "none" in str(exc).lower()

    def test_is_planner_resolution_error(self):
        exc = UnknownOutputNameError(
            run_id="run-xyz",
            output_name="assembly_fasta",
            known_outputs=("gff3",),
        )
        assert isinstance(exc, PlannerResolutionError)


class TestManifestNotFoundError:
    def test_attributes(self):
        exc = ManifestNotFoundError(manifest_path="/data/manifest.json")
        assert exc.manifest_path == "/data/manifest.json"

    def test_str_contains_manifest_path(self):
        exc = ManifestNotFoundError(manifest_path="/data/manifest.json")
        assert "/data/manifest.json" in str(exc)

    def test_is_planner_resolution_error(self):
        exc = ManifestNotFoundError(manifest_path="/data/manifest.json")
        assert isinstance(exc, PlannerResolutionError)


class TestBindingPathMissingError:
    def test_attributes(self):
        exc = BindingPathMissingError(path="/scratch/genome.fa")
        assert exc.path == "/scratch/genome.fa"

    def test_str_contains_path(self):
        exc = BindingPathMissingError(path="/scratch/genome.fa")
        assert "/scratch/genome.fa" in str(exc)

    def test_is_planner_resolution_error(self):
        exc = BindingPathMissingError(path="/scratch/genome.fa")
        assert isinstance(exc, PlannerResolutionError)


class TestPlannerResolutionErrorBase:
    def test_all_subclasses_are_exceptions(self):
        for cls in (
            UnknownRunIdError,
            UnknownOutputNameError,
            ManifestNotFoundError,
            BindingPathMissingError,
        ):
            assert issubclass(cls, Exception)

    def test_base_is_exception(self):
        assert issubclass(PlannerResolutionError, Exception)
