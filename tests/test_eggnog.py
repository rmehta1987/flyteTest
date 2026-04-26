"""Synthetic tests for the EggNOG functional-annotation milestone.

    These checks keep the repeat-filtered protein boundary, EggNOG command wiring,
    and annotated GFF3 collection honest without requiring EggNOG databases or
    container images in the local environment. The tests also describe the
    current annotation propagation contract for future maintenance work.
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

import flytetest.tasks.eggnog as eggnog
from flytetest.workflows.eggnog import annotation_functional_eggnog


def _read_json(path: Path) -> dict[str, object]:
    """Read one JSON manifest into a dictionary for assertions.

    Args:
        path: Manifest file to parse for the EggNOG tests.

    Returns:
        Parsed JSON payload used by the functional-annotation tests.
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


def _write_fasta(path: Path, records: list[tuple[str, str]]) -> Path:
    """Write a minimal FASTA file from `(header, sequence)` pairs.

    Args:
        path: Destination for the synthetic FASTA file.
        records: Header and sequence pairs staged for EggNOG.

    Returns:
        The FASTA file path, which the tests pass back into the task.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for header, sequence in records:
        lines.append(f">{header}")
        lines.append(sequence)
    path.write_text("\n".join(lines) + "\n")
    return path


def _write_gff3(path: Path) -> Path:
    """Write a small repeat-filtered GFF3 with transcript-to-gene boundaries.

    Args:
        path: Destination for the synthetic GFF3 file.

    Returns:
        The GFF3 file path, which the tests pass back into the workflow.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "##gff-version 3",
                "chr1\tEggNOG\tgene\t1\t100\t.\t+\t.\tID=gene1",
                "chr1\tEggNOG\tmRNA\t1\t100\t.\t+\t.\tID=tx1;Parent=gene1",
                "chr1\tEggNOG\texon\t1\t100\t.\t+\t.\tID=exon1;Parent=tx1",
                "chr1\tEggNOG\tgene\t200\t300\t.\t+\t.\tID=gene2",
                "chr1\tEggNOG\tmRNA\t200\t300\t.\t+\t.\tID=tx2;Parent=gene2",
                "chr1\tEggNOG\texon\t200\t300\t.\t+\t.\tID=exon2;Parent=tx2",
            ]
        )
        + "\n"
    )
    return path


def _create_repeat_filter_results(tmp_path: Path) -> Path:
    """Create a minimal repeat-filter bundle with the final protein and GFF3 boundaries.

    Args:
        tmp_path: Temporary root used to stage the bundle.

    Returns:
        The staged repeat-filter result directory.
    """
    results_dir = tmp_path / "repeat_filter_results"
    proteins_fasta = _write_fasta(
        results_dir / "all_repeats_removed.proteins.fa",
        [("tx1", "MAPP"), ("tx2", "MSTT")],
    )
    gff3_path = _write_gff3(results_dir / "all_repeats_removed.gff3")
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "annotation_repeat_filtering",
            "outputs": {
                "final_proteins_fasta": str(proteins_fasta),
                "all_repeats_removed_gff3": str(gff3_path),
            },
        },
    )
    return results_dir


def _fixed_datetime() -> type:
    """Return a deterministic timestamp provider for result-directory naming.

    This helper keeps the test fixture deterministic and explicit.

    Returns:
        The shim class used to monkeypatch `datetime`.
    """

    # Keep the synthetic result-directory name stable for manifest assertions.
    class _Stamp:
        """Fake datetime stamp that always returns the same test timestamp."""

        def strftime(self, fmt: str) -> str:
            """Return the fixed timestamp string expected by the assertions."""
            return "20260404_150000"

    class _FixedDatetime:
        """Shim object that mimics the subset of `datetime` used by the code."""

        @classmethod
        def now(cls) -> _Stamp:
            """Return the fixed timestamp stub used by the synthetic tests."""
            return _Stamp()

    return _FixedDatetime


class EggnogTaskTests(TestCase):
    """Task-level coverage for the EggNOG functional-annotation boundary.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_eggnog_map_writes_tx2gene_and_annotated_gff3(self) -> None:
        """Keep the EggNOG command and GFF3 decoration aligned with the tool reference.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repeat_filter_results = _create_repeat_filter_results(tmp_path)
            eggnog_data_dir = tmp_path / "eggnog_data"
            eggnog_data_dir.mkdir(parents=True, exist_ok=True)
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Emit the minimal EggNOG outputs the task collects."""
                captured["cmd"] = cmd
                self.assertIsNotNone(cwd)
                work_dir = Path(cwd)
                (work_dir / "eggnog_output.emapper.annotations").write_text(
                    "\n".join(
                        [
                            "#query\tseed_ortholog\tseed_ortholog_evalue\tseed_ortholog_score\tPreferred_name\tGOs",
                            "tx1\torth1\t1e-5\t100\tAlpha protein\tGO:0000001",
                            "tx2\torth2\t1e-6\t90\tBeta protein\tGO:0000002",
                        ]
                    )
                    + "\n"
                )
                (work_dir / "eggnog_output.emapper.decorated.gff").write_text(
                    (repeat_filter_results / "all_repeats_removed.gff3").read_text()
                )

            with patch.object(eggnog, "run_tool", side_effect=fake_run_tool):
                results = eggnog.eggnog_map(
                    repeat_filter_results=Dir(path=str(repeat_filter_results)),
                    eggnog_data_dir=str(eggnog_data_dir),
                    eggnog_cpu=24,
            )

            cmd = captured["cmd"]
            proteins_input = Path(cmd[4])
            gff3_input = Path(cmd[14])
            self.assertEqual(
                cmd,
                [
                    "emapper.py",
                    "-m",
                    "hmmer",
                    "-i",
                    str(proteins_input),
                    "-o",
                    "eggnog_output",
                    "-d",
                    "Diptera",
                    "--data_dir",
                    str(eggnog_data_dir),
                    "--cpu",
                    "24",
                    "--decorate_gff",
                    str(gff3_input),
                    "--report_orthologs",
                    "--excel",
                ],
            )
            self.assertEqual(
                proteins_input.name,
                "all_repeats_removed.proteins.fa",
            )
            self.assertEqual(proteins_input.parent.name, "source_boundary")
            self.assertEqual(gff3_input.name, "all_repeats_removed.gff3")
            self.assertEqual(gff3_input.parent.name, "source_boundary")

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")
            tx2gene = (results_dir / "tx2gene.tsv").read_text().splitlines()
            annotated_gff3 = (results_dir / "eggnog_output.annotated.gff3").read_text()

            self.assertEqual(tx2gene, ["tx1\tgene1", "tx2\tgene2"])
            self.assertIn("Name=Alpha protein", annotated_gff3)
            self.assertIn("Name=Beta protein", annotated_gff3)
            self.assertIn("eggnog_annotations", manifest["outputs"])
            self.assertEqual(manifest["inputs"]["eggnog_database"], "Diptera")


class EggnogWorkflowTests(TestCase):
    """Workflow-level coverage for the EggNOG functional-annotation boundary.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_annotation_functional_eggnog_collects_results_and_sources(self) -> None:
        """Run the synthetic workflow and collect the stable EggNOG result bundle.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repeat_filter_results = _create_repeat_filter_results(tmp_path)
            eggnog_data_dir = tmp_path / "eggnog_data"
            eggnog_data_dir.mkdir(parents=True, exist_ok=True)

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Emit the minimal EggNOG outputs the workflow collects."""
                self.assertIsNotNone(cwd)
                work_dir = Path(cwd)
                (work_dir / "eggnog_output.emapper.annotations").write_text(
                    "\n".join(
                        [
                            "#query\tseed_ortholog\tseed_ortholog_evalue\tseed_ortholog_score\tPreferred_name",
                            "tx1\torth1\t1e-5\t100\tAlpha protein",
                            "tx2\torth2\t1e-6\t90\tBeta protein",
                        ]
                    )
                    + "\n"
                )
                (work_dir / "eggnog_output.emapper.decorated.gff").write_text(
                    (repeat_filter_results / "all_repeats_removed.gff3").read_text()
                )

            with (
                patch.object(eggnog, "run_tool", side_effect=fake_run_tool),
                patch.object(eggnog, "datetime", _fixed_datetime()),
            ):
                results = annotation_functional_eggnog(
                    repeat_filter_results=Dir(path=str(repeat_filter_results)),
                    eggnog_data_dir=str(eggnog_data_dir),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "source_boundary" / "all_repeats_removed.proteins.fa").exists())
            self.assertTrue((results_dir / "source_boundary" / "all_repeats_removed.gff3").exists())
            self.assertTrue((results_dir / "eggnog_runs" / "Diptera").exists())
            self.assertTrue((results_dir / "eggnog.emapper.annotations").exists())
            self.assertTrue((results_dir / "eggnog.emapper.decorated.gff").exists())
            self.assertTrue((results_dir / "all_repeats_removed.eggnog.gff3").exists())
            self.assertEqual(manifest["workflow"], "annotation_functional_eggnog")
            self.assertEqual(manifest["inputs"]["eggnog_database"], "Diptera")
            self.assertEqual(
                manifest["outputs"]["eggnog_annotated_gff3"],
                str(results_dir / "all_repeats_removed.eggnog.gff3"),
            )
