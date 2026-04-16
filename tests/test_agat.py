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
from flytetest.tasks.agat import table2asn_submission
from flytetest.workflows.agat import (
    annotation_postprocess_agat,
    annotation_postprocess_agat_cleanup,
    annotation_postprocess_agat_conversion,
    annotation_postprocess_table2asn,
)


def _read_json(path: Path) -> dict[str, object]:
    """Read one JSON manifest into a dictionary for assertions.

    Args:
        path: Manifest file to parse for the AGAT tests.

    Returns:
        Parsed JSON payload used by the post-processing tests.
    """
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    """Write one JSON payload with indentation for readable failures.

    Args:
        path: Destination for the synthetic manifest file.
        payload: Structured payload written into the manifest.

    Returns:
        The JSON file path, which is convenient for fixture chaining.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _write_text(path: Path, contents: str) -> Path:
    """Write one small text file used as a synthetic annotation fixture.

    Args:
        path: Destination for the synthetic text file.
        contents: Text content written into the fixture.

    Returns:
        The text file path, which the tests can hand back into the workflow.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    return path


def _write_gff3(path: Path) -> Path:
    """Write a minimal EggNOG-annotated GFF3 boundary.

    Args:
        path: Destination for the synthetic GFF3 file.

    Returns:
        The GFF3 file path, which the tests pass into AGAT.
    """
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
    """Create a minimal EggNOG results bundle with a decorated GFF3 boundary.

    Args:
        tmp_path: Temporary root used to stage the bundle.

    Returns:
        The staged EggNOG result directory.
    """
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
    """Create a minimal AGAT conversion results bundle with a converted GFF3.

    Args:
        tmp_path: Temporary root used to stage the bundle.

    Returns:
        The staged AGAT conversion result directory.
    """
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
    """Return a deterministic timestamp provider for result-directory naming.

    Args:
        stamp: Timestamp string captured in the synthetic manifest names.

    Returns:
        The shim class used to monkeypatch `datetime`.
    """

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
    """Task-level coverage for the AGAT post-processing slices.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_agat_statistics_runs_the_statistics_command_with_optional_fasta(self) -> None:
        """Keep the AGAT command and output collection aligned with the AGAT task ref.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
                """Capture the AGAT statistics command and stage a synthetic output file."""
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
        """Keep the AGAT conversion command and output collection aligned with the AGAT task ref.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
                """Capture the AGAT conversion command and stage a synthetic output file."""
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
        """Apply the post-AGAT cleanup rules without running table2asn.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
    """Workflow-level coverage for the AGAT post-processing entrypoints.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_annotation_postprocess_agat_collects_the_statistics_only_slice(self) -> None:
        """Run the workflow wrapper without an optional FASTA and keep the bundle stable.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
                """Stage the synthetic AGAT statistics output without optional FASTA input."""
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
        """Run the conversion workflow wrapper and keep the normalized bundle stable.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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
                """Stage the synthetic AGAT conversion output for the workflow wrapper."""
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
        """Run the cleanup workflow wrapper and keep table2asn out of scope.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
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

# ---------------------------------------------------------------------------
# Helper for M21c table2asn tests
# ---------------------------------------------------------------------------

def _create_agat_cleanup_results(tmp_path: Path) -> Path:
    """Create a minimal AGAT cleanup results bundle with a cleaned GFF3.

    Args:
        tmp_path: Temporary root used to stage the bundle.

    Returns:
        The staged AGAT cleanup result directory.
    """
    results_dir = tmp_path / "agat_cleanup_results"
    gff3_path = _write_gff3(results_dir / "agat_output" / "all_repeats_removed.agat.cleaned.gff3")
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "annotation_postprocess_agat_cleanup",
            "outputs": {
                "agat_cleaned_gff3": str(gff3_path),
            },
        },
    )
    return results_dir


# Add M21c tests to the existing AgatTaskTests class by patching at module level.

class Table2AsnTaskTests(TestCase):
    """Task-level coverage for the table2asn submission slice (M21c)."""

    def test_table2asn_submission_builds_correct_command(self) -> None:
        """table2asn_submission builds the command matching the braker3_evm_notes.md shape.

        Validates all required flags (-M n, -J, -c w, -euk, -gaps-min 10,
        -l proximity-ligation, -Z, -V b) and the optional -locus-tag-prefix
        and -j flags.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cleanup_results = _create_agat_cleanup_results(tmp_path)
            genome_fa = _write_text(tmp_path / "genome.fa", ">chr1\nACGT\n")
            template_sbt = _write_text(tmp_path / "template.sbt", "Submit-block ::= {}\n")
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Capture the table2asn command and stage a synthetic .sqn output."""
                captured["cmd"] = cmd
                if cwd is not None:
                    out = Path(cwd) / "annotation_submission.sqn"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("stub sqn\n")

            with (
                patch.object(agat, "run_tool", side_effect=fake_run_tool),
                patch.object(agat, "datetime", _fixed_datetime("20260415_120000")),
            ):
                table2asn_submission(
                    agat_cleanup_results=Dir(path=str(cleanup_results)),
                    genome_fasta=str(genome_fa),
                    submission_template=str(template_sbt),
                    locus_tag_prefix="ACFI09",
                    organism_annotation="[organism=Foo bar][isolate=X]",
                )

            cmd = list(captured["cmd"])
            self.assertEqual(cmd[0], "table2asn")
            self.assertIn("-M", cmd); self.assertEqual(cmd[cmd.index("-M") + 1], "n")
            self.assertIn("-J", cmd)
            self.assertIn("-c", cmd); self.assertEqual(cmd[cmd.index("-c") + 1], "w")
            self.assertIn("-euk", cmd)
            self.assertIn("-gaps-min", cmd); self.assertEqual(cmd[cmd.index("-gaps-min") + 1], "10")
            self.assertIn("-l", cmd); self.assertEqual(cmd[cmd.index("-l") + 1], "proximity-ligation")
            self.assertIn("-locus-tag-prefix", cmd)
            self.assertEqual(cmd[cmd.index("-locus-tag-prefix") + 1], "ACFI09")
            self.assertIn("-j", cmd)
            self.assertEqual(cmd[cmd.index("-j") + 1], "[organism=Foo bar][isolate=X]")
            self.assertIn("-Z", cmd)
            self.assertIn("-V", cmd); self.assertEqual(cmd[cmd.index("-V") + 1], "b")
            self.assertIn("-t", cmd); self.assertEqual(cmd[cmd.index("-t") + 1], str(template_sbt))
            self.assertIn("-i", cmd); self.assertEqual(cmd[cmd.index("-i") + 1], str(genome_fa))

    def test_table2asn_submission_writes_run_manifest(self) -> None:
        """table2asn_submission writes run_manifest.json with expected keys and workflow name."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cleanup_results = _create_agat_cleanup_results(tmp_path)
            genome_fa = _write_text(tmp_path / "genome.fa", ">chr1\nACGT\n")
            template_sbt = _write_text(tmp_path / "template.sbt", "Submit-block ::= {}\n")

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Stage a synthetic .sqn output without running table2asn."""
                if cwd is not None:
                    out = Path(cwd) / "annotation_submission.sqn"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("stub sqn\n")

            with (
                patch.object(agat, "run_tool", side_effect=fake_run_tool),
                patch.object(agat, "datetime", _fixed_datetime("20260415_121000")),
            ):
                result = table2asn_submission(
                    agat_cleanup_results=Dir(path=str(cleanup_results)),
                    genome_fasta=str(genome_fa),
                    submission_template=str(template_sbt),
                )

            results_dir = Path(result.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertEqual(manifest["workflow"], "annotation_postprocess_table2asn")
            self.assertIn("assumptions", manifest)
            self.assertIn("source_bundle", manifest)
            self.assertIn("inputs", manifest)
            self.assertIn("outputs", manifest)
            self.assertIn("genome_fasta", manifest["inputs"])
            self.assertIn("submission_template", manifest["inputs"])
            self.assertIn("table2asn_output_dir", manifest["outputs"])

    def test_table2asn_submission_raises_when_no_gff3_found(self) -> None:
        """table2asn_submission raises FileNotFoundError when no cleaned GFF3 exists.

        Exercises the fallback in _agat_cleaned_gff3 when neither a manifest
        record nor any agat_output/*.gff3 files are present.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Empty cleanup dir — no manifest, no agat_output subdirectory.
            empty_cleanup = tmp_path / "empty_cleanup"
            empty_cleanup.mkdir(parents=True)
            genome_fa = _write_text(tmp_path / "genome.fa", ">chr1\nACGT\n")
            template_sbt = _write_text(tmp_path / "template.sbt", "Submit-block ::= {}\n")

            with self.assertRaises(FileNotFoundError):
                table2asn_submission(
                    agat_cleanup_results=Dir(path=str(empty_cleanup)),
                    genome_fasta=str(genome_fa),
                    submission_template=str(template_sbt),
                )
