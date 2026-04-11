"""Synthetic tests for the AGAT post-EggNOG milestone slices.

These checks keep the EggNOG-annotated GFF3 boundary, AGAT statistics,
conversion command wiring, deterministic cleanup, and result-bundle collection
honest without requiring a local AGAT installation.
"""

from __future__ import annotations

import json
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

from flyte.io import Dir

import flytetest.tasks.agat as agat
from flytetest.workflows.agat import (
    annotation_postprocess_agat,
    annotation_postprocess_agat_cleanup,
    annotation_postprocess_agat_conversion,
)


def _read_json(path: Path) -> dict[str, object]:
    """Read one JSON manifest into a dictionary for assertions."""
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    """Write one JSON payload with indentation for readable failures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _write_text(path: Path, contents: str) -> Path:
    """Write one small text file used as a synthetic annotation fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    return path


def _write_gff3(path: Path) -> Path:
    """Write a minimal EggNOG-annotated GFF3 boundary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "##gff-version 3",
                "chr1\tEggNOG\tgene\t1\t100\t.\t+\t.\tID=gene1;Name=Alpha;Note=remove-me",
                "chr1\tEggNOG\tmRNA\t1\t100\t.\t+\t.\tID=tx1;Parent=gene1;Name=Alpha",
                "chr1\tEggNOG\tCDS\t1\t90\t.\t+\t0\tID=cds1;Parent=tx1",
                "chr1\tEggNOG\tmRNA\t120\t180\t.\t+\t.\tID=tx2;Parent=gene1;Name=-",
                "chr1\tEggNOG\tCDS\t120\t180\t.\t+\t0\tID=cds2;Parent=tx2;product=-",
            ]
        )
        + "\n"
    )
    return path


def _create_eggnog_results(tmp_path: Path) -> Path:
    """Create a minimal EggNOG results bundle with a decorated GFF3 boundary."""
    results_dir = tmp_path / "eggnog_results"
    gff3_path = _write_gff3(results_dir / "all_repeats_removed.eggnog.gff3")
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "annotation_functional_eggnog",
            "outputs": {
                "eggnog_annotated_gff3": str(gff3_path),
            },
        },
    )
    return results_dir


def _create_agat_conversion_results(tmp_path: Path) -> Path:
    """Create a minimal AGAT conversion results bundle with a converted GFF3."""
    results_dir = tmp_path / "agat_conversion_results"
    gff3_path = _write_gff3(results_dir / "all_repeats_removed.agat.gff3")
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "annotation_postprocess_agat_conversion",
            "outputs": {
                "agat_converted_gff3": str(gff3_path),
            },
        },
    )
    return results_dir


def _fixed_datetime(stamp: str = "20260404_160000") -> type:
    """Return a deterministic timestamp provider for result-directory naming."""

    # Keep the synthetic result-directory name stable for manifest assertions.
    class _Stamp:
        """Fake datetime stamp that always returns the same test timestamp."""

        def strftime(self, fmt: str) -> str:
            """Return the fixed timestamp string expected by the assertions."""
            return stamp

    class _FixedDatetime:
        """Shim object that mimics the subset of `datetime` used by the code."""

        @classmethod
        def now(cls) -> _Stamp:
            """Return the fixed timestamp stub used by the synthetic tests."""
            return _Stamp()

    return _FixedDatetime


class AgatTaskTests(TestCase):
    """Task-level coverage for the AGAT post-processing slices."""

    def test_agat_statistics_runs_the_statistics_command_with_optional_fasta(self) -> None:
        """Keep the AGAT command and output collection aligned with the AGAT task ref."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eggnog_results = _create_eggnog_results(tmp_path)
            annotation_fasta = _write_text(tmp_path / "repeatmasked.fa", ">chr1\nACGT\n")
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                captured["cmd"] = cmd
                captured["bind_paths"] = bind_paths
                self.assertIsNotNone(cwd)
                work_dir = Path(cwd)
                (work_dir / "agat_output").mkdir(parents=True, exist_ok=True)
                (work_dir / "agat_output" / "agat_statistics.tsv").write_text("feature\tcount\n")

            with (
                patch.object(agat, "run_tool", side_effect=fake_run_tool),
                patch.object(agat, "datetime", _fixed_datetime("20260404_160000")),
            ):
                results = agat.agat_statistics(
                    eggnog_results=Dir(path=str(eggnog_results)),
                    annotation_fasta_path=str(annotation_fasta),
                )

            stats_path = Path(captured["cmd"][-1])
            gff3_path = Path(captured["cmd"][2])
            fasta_path = Path(captured["cmd"][4])
            self.assertEqual(
                captured["cmd"],
                [
                    "agat_sp_statistics.pl",
                    "--gff",
                    str(gff3_path),
                    "-f",
                    str(fasta_path),
                    "--output",
                    str(stats_path),
                ],
            )
            self.assertEqual(gff3_path.name, "all_repeats_removed.eggnog.gff3")
            self.assertEqual(fasta_path.name, "repeatmasked.fa")
            self.assertIn(eggnog_results, [Path(path) for path in captured["bind_paths"]])

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "source_boundary" / "all_repeats_removed.eggnog.gff3").exists())
            self.assertTrue((results_dir / "source_boundary" / "repeatmasked.fa").exists())
            self.assertTrue((results_dir / "agat_output" / "agat_statistics.tsv").exists())
            self.assertTrue((results_dir / "agat_statistics.tsv").exists())
            self.assertEqual(manifest["workflow"], "annotation_postprocess_agat")
            self.assertEqual(manifest["inputs"]["annotation_fasta_path"], str(annotation_fasta))
            self.assertEqual(manifest["outputs"]["agat_statistics_tsv"], str(results_dir / "agat_statistics.tsv"))

    def test_agat_convert_sp_gxf2gxf_runs_the_conversion_command(self) -> None:
        """Keep the AGAT conversion command and output collection aligned with the AGAT task ref."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eggnog_results = _create_eggnog_results(tmp_path)
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                captured["cmd"] = cmd
                captured["bind_paths"] = bind_paths
                self.assertIsNotNone(cwd)
                work_dir = Path(cwd)
                (work_dir / "agat_output").mkdir(parents=True, exist_ok=True)
                (work_dir / "agat_output" / "all_repeats_removed.agat.gff3").write_text(
                    "##gff-version 3\n"
                )

            with (
                patch.object(agat, "run_tool", side_effect=fake_run_tool),
                patch.object(agat, "datetime", _fixed_datetime("20260404_161000")),
            ):
                results = agat.agat_convert_sp_gxf2gxf(
                    eggnog_results=Dir(path=str(eggnog_results)),
                )

            gff3_path = Path(captured["cmd"][2])
            output_path = Path(captured["cmd"][4])
            self.assertEqual(
                captured["cmd"],
                [
                    "agat_convert_sp_gxf2gxf.pl",
                    "-g",
                    str(gff3_path),
                    "-o",
                    str(output_path),
                ],
            )
            self.assertEqual(gff3_path.name, "all_repeats_removed.eggnog.gff3")
            self.assertEqual(output_path.name, "all_repeats_removed.agat.gff3")
            self.assertIn(eggnog_results, [Path(path) for path in captured["bind_paths"]])

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "source_boundary" / "all_repeats_removed.eggnog.gff3").exists())
            self.assertTrue((results_dir / "agat_output" / "all_repeats_removed.agat.gff3").exists())
            self.assertTrue((results_dir / "all_repeats_removed.agat.gff3").exists())
            self.assertEqual(manifest["workflow"], "annotation_postprocess_agat_conversion")
            self.assertEqual(manifest["outputs"]["agat_converted_gff3"], str(results_dir / "all_repeats_removed.agat.gff3"))

    def test_agat_cleanup_gff3_applies_the_notes_backed_attribute_cleanup(self) -> None:
        """Apply the post-AGAT cleanup rules without running table2asn."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            conversion_results = _create_agat_conversion_results(tmp_path)

            with patch.object(agat, "datetime", _fixed_datetime("20260404_164000")):
                results = agat.agat_cleanup_gff3(
                    agat_conversion_results=Dir(path=str(conversion_results)),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")
            cleaned_gff3 = results_dir / "all_repeats_removed.agat.cleaned.gff3"
            cleanup_summary = _read_json(results_dir / "agat_cleanup_summary.json")
            cleaned_text = cleaned_gff3.read_text()

            self.assertTrue((results_dir / "source_boundary" / "all_repeats_removed.agat.gff3").exists())
            self.assertTrue((results_dir / "agat_output" / "all_repeats_removed.agat.cleaned.gff3").exists())
            self.assertNotIn("Note=remove-me", cleaned_text)
            self.assertIn("ID=cds1;Parent=tx1;product=Alpha", cleaned_text)
            self.assertIn("ID=cds2;Parent=tx2;product=putative", cleaned_text)
            self.assertEqual(manifest["workflow"], "annotation_postprocess_agat_cleanup")
            self.assertEqual(
                manifest["outputs"]["agat_cleaned_gff3"],
                str(cleaned_gff3),
            )
            self.assertEqual(cleanup_summary["gene_notes_removed"], 1)
            self.assertEqual(cleanup_summary["cds_products_propagated"], 2)
            self.assertEqual(cleanup_summary["cds_products_replaced_with_putative"], 1)


class AgatWorkflowTests(TestCase):
    """Workflow-level coverage for the AGAT post-processing entrypoints."""

    def test_annotation_postprocess_agat_collects_the_statistics_only_slice(self) -> None:
        """Run the workflow wrapper without an optional FASTA and keep the bundle stable."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eggnog_results = _create_eggnog_results(tmp_path)

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                self.assertIsNotNone(cwd)
                work_dir = Path(cwd)
                (work_dir / "agat_output").mkdir(parents=True, exist_ok=True)
                (work_dir / "agat_output" / "agat_statistics.tsv").write_text("feature\tcount\n")

            with (
                patch.object(agat, "run_tool", side_effect=fake_run_tool),
                patch.object(agat, "datetime", _fixed_datetime("20260404_162000")),
            ):
                results = annotation_postprocess_agat(
                    eggnog_results=Dir(path=str(eggnog_results)),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "source_boundary" / "all_repeats_removed.eggnog.gff3").exists())
            self.assertFalse((results_dir / "source_boundary" / "repeatmasked.fa").exists())
            self.assertTrue((results_dir / "agat_output" / "agat_statistics.tsv").exists())
            self.assertEqual(manifest["workflow"], "annotation_postprocess_agat")
            self.assertEqual(manifest["inputs"]["annotation_fasta_path"], "")
            self.assertEqual(
                manifest["outputs"]["eggnog_annotated_gff3"],
                str(results_dir / "source_boundary" / "all_repeats_removed.eggnog.gff3"),
            )

    def test_annotation_postprocess_agat_conversion_collects_the_normalized_gff3_slice(self) -> None:
        """Run the conversion workflow wrapper and keep the normalized bundle stable."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            eggnog_results = _create_eggnog_results(tmp_path)

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                self.assertIsNotNone(cwd)
                work_dir = Path(cwd)
                (work_dir / "agat_output").mkdir(parents=True, exist_ok=True)
                (work_dir / "agat_output" / "all_repeats_removed.agat.gff3").write_text(
                    "##gff-version 3\n"
                )

            with (
                patch.object(agat, "run_tool", side_effect=fake_run_tool),
                patch.object(agat, "datetime", _fixed_datetime("20260404_163000")),
            ):
                results = annotation_postprocess_agat_conversion(
                    eggnog_results=Dir(path=str(eggnog_results)),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "source_boundary" / "all_repeats_removed.eggnog.gff3").exists())
            self.assertTrue((results_dir / "agat_output" / "all_repeats_removed.agat.gff3").exists())
            self.assertTrue((results_dir / "all_repeats_removed.agat.gff3").exists())
            self.assertEqual(manifest["workflow"], "annotation_postprocess_agat_conversion")
            self.assertEqual(
                manifest["outputs"]["agat_converted_gff3"],
                str(results_dir / "all_repeats_removed.agat.gff3"),
            )

    def test_annotation_postprocess_agat_cleanup_collects_the_cleaned_gff3_slice(self) -> None:
        """Run the cleanup workflow wrapper and keep table2asn out of scope."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            conversion_results = _create_agat_conversion_results(tmp_path)

            with patch.object(agat, "datetime", _fixed_datetime("20260404_165000")):
                results = annotation_postprocess_agat_cleanup(
                    agat_conversion_results=Dir(path=str(conversion_results)),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "agat_output" / "all_repeats_removed.agat.cleaned.gff3").exists())
            self.assertTrue((results_dir / "all_repeats_removed.agat.cleaned.gff3").exists())
            self.assertTrue((results_dir / "agat_cleanup_summary.json").exists())
            self.assertEqual(manifest["workflow"], "annotation_postprocess_agat_cleanup")
            self.assertEqual(
                manifest["outputs"]["agat_cleaned_gff3"],
                str(results_dir / "all_repeats_removed.agat.cleaned.gff3"),
            )
