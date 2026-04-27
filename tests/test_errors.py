"""Tests for the PlannerResolutionError typed exception hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flytetest.errors import (
    BindingTypeMismatchError,
    BindingPathMissingError,
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


class TestBindingPathMissingError:
    def test_attributes_default_kind_is_raw_path(self):
        exc = BindingPathMissingError(path="/scratch/genome.fa")
        assert exc.path == "/scratch/genome.fa"
        assert exc.kind == "raw_path"

    def test_str_contains_path_and_binding_prefix_for_raw_path(self):
        exc = BindingPathMissingError(path="/scratch/genome.fa")
        assert "/scratch/genome.fa" in str(exc)
        assert "binding path" in str(exc)

    def test_manifest_kind_uses_manifest_message_prefix(self):
        exc = BindingPathMissingError(path="/data/manifest.json", kind="manifest")
        assert exc.kind == "manifest"
        assert "manifest path" in str(exc)
        assert "/data/manifest.json" in str(exc)

    def test_is_planner_resolution_error(self):
        exc = BindingPathMissingError(path="/scratch/genome.fa")
        assert isinstance(exc, PlannerResolutionError)


class TestBindingTypeMismatchError:
    def test_attributes(self):
        exc = BindingTypeMismatchError(
            binding_key="ReadSet",
            resolved_type="VariantCallSet",
            source="run-123",
        )
        assert exc.binding_key == "ReadSet"
        assert exc.resolved_type == "VariantCallSet"
        assert exc.source == "run-123"

    def test_str_contains_all_context(self):
        exc = BindingTypeMismatchError(
            binding_key="ReadSet",
            resolved_type="VariantCallSet",
            source="run-123",
        )
        assert "ReadSet" in str(exc)
        assert "VariantCallSet" in str(exc)
        assert "run-123" in str(exc)

    def test_is_planner_resolution_error(self):
        exc = BindingTypeMismatchError(
            binding_key="ReadSet",
            resolved_type="VariantCallSet",
            source="run-123",
        )
        assert isinstance(exc, PlannerResolutionError)


class TestPlannerResolutionErrorBase:
    def test_all_subclasses_are_exceptions(self):
        for cls in (
            UnknownRunIdError,
            UnknownOutputNameError,
            BindingPathMissingError,
            BindingTypeMismatchError,
        ):
            assert issubclass(cls, Exception)

    def test_base_is_exception(self):
        assert issubclass(PlannerResolutionError, Exception)
