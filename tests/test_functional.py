"""Synthetic tests for the BUSCO-based annotation-QC milestone.

These checks keep the repeat-filter-to-BUSCO boundary, BUSCO command wiring,
and QC result collection honest without requiring BUSCO binaries or lineage
databases in the local environment.
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

from flyte.io import Dir, File

import flytetest.tasks.functional as functional
from flytetest.workflows.functional import annotation_qc_busco


def _read_json(path: Path) -> dict[str, object]:
    """Read one JSON manifest into a dictionary for assertions."""
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    """Write one JSON payload with indentation for readable failures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _write_fasta(path: Path, records: list[tuple[str, str]]) -> Path:
    """Write a minimal FASTA file from `(header, sequence)` pairs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for header, sequence in records:
        lines.append(f">{header}")
        lines.append(sequence)
    path.write_text("\n".join(lines) + "\n")
    return path


def _create_repeat_filter_results(tmp_path: Path) -> Path:
    """Create a minimal repeat-filter bundle with the final proteins FASTA."""
    results_dir = tmp_path / "repeat_filter_results"
    proteins_fasta = _write_fasta(
        results_dir / "all_repeats_removed.proteins.fa",
        [("prot1", "MAPP"), ("prot2", "MSTT")],
    )
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "annotation_repeat_filtering",
            "outputs": {
                "final_proteins_fasta": str(proteins_fasta),
            },
        },
    )
    return results_dir


def _fixed_datetime() -> type:
    """Return a deterministic timestamp provider for result-directory naming."""

    # Keep the synthetic result-directory name stable for manifest assertions.
    class _Stamp:
        """Fake datetime stamp that always returns the same test timestamp."""

        def strftime(self, fmt: str) -> str:
            """Return the fixed timestamp string expected by the assertions."""
            return "20260404_140000"

    class _FixedDatetime:
        """Shim object that mimics the subset of `datetime` used by the code."""

        @classmethod
        def now(cls) -> _Stamp:
            """Return the fixed timestamp stub used by the synthetic tests."""
            return _Stamp()

    return _FixedDatetime


class FunctionalTaskTests(TestCase):
    """Task-level coverage for BUSCO QC."""

    def test_lineages_from_text_strips_whitespace_and_empty_fields(self) -> None:
        """Normalize comma-separated lineages into the exact ordered BUSCO inputs."""
        self.assertEqual(
            functional._lineages_from_text(" eukaryota_odb10 , , diptera_odb10 "),
            ["eukaryota_odb10", "diptera_odb10"],
        )

    def test_busco_assess_proteins_uses_note_backed_protein_mode_flags(self) -> None:
        """Keep the BUSCO command aligned with the BUSCO tool reference and protein-mode flags."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            proteins = _write_fasta(tmp_path / "proteins.fa", [("prot1", "MAPP")])
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                captured["cmd"] = cmd
                self.assertIsNotNone(cwd)
                run_dir = cwd / "busco_output_eukaryota_odb10"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "short_summary.specific.eukaryota_odb10.txt").write_text(
                    "C:98.0%[S:97.0%,D:1.0%],F:1.0%,M:1.0%,n:255\n"
                )
                (run_dir / "full_table.tsv").write_text("# BUSCO table\n")

            with patch.object(functional, "run_tool", side_effect=fake_run_tool):
                results = functional.busco_assess_proteins(
                    proteins_fasta=File(path=str(proteins)),
                    lineage_dataset="eukaryota_odb10",
                    busco_cpu=8,
                )

            cmd = captured["cmd"]
            self.assertEqual(
                cmd,
                [
                    "busco",
                    "-i",
                    str(proteins),
                    "-o",
                    "busco_output_eukaryota_odb10",
                    "-l",
                    "eukaryota_odb10",
                    "-m",
                    "prot",
                    "-c",
                    "8",
                ],
            )
            manifest = _read_json(Path(results.download_sync()) / "run_manifest.json")
            self.assertEqual(manifest["outputs"]["summary_notation"], "C:98.0%[S:97.0%,D:1.0%],F:1.0%,M:1.0%,n:255")

    def test_busco_assess_proteins_can_omit_lineage_for_fixture_genome_mode(self) -> None:
        """Support the upstream BUSCO genome fixture command shape without a lineage flag."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            genome = _write_fasta(tmp_path / "genome.fna", [("seq1", "ACGTACGT")])
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                captured["cmd"] = cmd
                self.assertIsNotNone(cwd)
                run_dir = cwd / "busco_output_auto-lineage"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "short_summary.specific.eukaryota_odb10.txt").write_text(
                    "C:75.0%[S:75.0%,D:0.0%],F:5.0%,M:20.0%,n:255\n"
                )
                (run_dir / "full_table.tsv").write_text("# BUSCO table\n")

            with patch.object(functional, "run_tool", side_effect=fake_run_tool):
                results = functional.busco_assess_proteins(
                    proteins_fasta=File(path=str(genome)),
                    lineage_dataset="auto-lineage",
                    busco_cpu=2,
                    busco_mode="geno",
                )

            cmd = captured["cmd"]
            self.assertEqual(
                cmd,
                [
                    "busco",
                    "-i",
                    str(genome),
                    "-o",
                    "busco_output_auto-lineage",
                    "-m",
                    "geno",
                    "-c",
                    "2",
                ],
            )
            manifest = _read_json(Path(results.download_sync()) / "run_manifest.json")
            self.assertEqual(manifest["inputs"]["lineage_dataset"], "auto-lineage")


class FunctionalWorkflowTests(TestCase):
    """Workflow-level coverage for BUSCO annotation QC."""

    def test_annotation_qc_busco_collects_lineage_runs_and_summary(self) -> None:
        """Run the synthetic BUSCO workflow and collect stable lineage outputs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repeat_filter_results = _create_repeat_filter_results(tmp_path)

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                self.assertIsNotNone(cwd)
                output_name = cmd[cmd.index("-o") + 1]
                lineage = cmd[cmd.index("-l") + 1]
                run_dir = cwd / output_name
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / f"short_summary.specific.{Path(lineage).name}.txt").write_text(
                    f"C:95.0%[S:94.0%,D:1.0%],F:3.0%,M:2.0%,n:255 lineage={lineage}\n"
                )
                (run_dir / "full_table.tsv").write_text("# BUSCO table\n")

            with (
                patch.object(functional, "run_tool", side_effect=fake_run_tool),
                patch.object(functional, "datetime", _fixed_datetime()),
            ):
                results = annotation_qc_busco(
                    repeat_filter_results=Dir(path=str(repeat_filter_results)),
                    busco_lineages_text="eukaryota_odb10,diptera_odb10",
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")
            summary_tsv = (results_dir / "busco_summary.tsv").read_text()

            self.assertTrue((results_dir / "source_boundary" / "all_repeats_removed.proteins.fa").exists())
            self.assertTrue((results_dir / "busco_runs" / "eukaryota_odb10").exists())
            self.assertTrue((results_dir / "busco_runs" / "diptera_odb10").exists())
            self.assertIn("eukaryota_odb10", summary_tsv)
            self.assertIn("diptera_odb10", summary_tsv)
            self.assertEqual(
                manifest["inputs"]["busco_lineages_text"],
                "eukaryota_odb10,diptera_odb10",
            )
            self.assertIn("busco_summary_tsv", manifest["outputs"])
