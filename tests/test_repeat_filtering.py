"""Tests for the repeat-filtering stage added after PASA post-EVM refinement.

    The suite keeps the external tool calls synthetic so the repeat-filtering
    boundary can be validated without RepeatMasker, gffread, or funannotate
    binaries, while still checking the local fixture paths used for optional smoke
    tests when those binaries are available. The tests document the current
    cleanup and manifest behavior for future refactor passes.
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

import flytetest.tasks.filtering as filtering
from flytetest.workflows.filtering import annotation_repeat_filtering


def _artifact_dir(path: Path) -> Dir:
    """Create a local Flyte directory wrapper from a filesystem path.

    Args:
        path: Directory path staged for the Flyte stub wrapper.

    Returns:
        Flyte directory stub pointing at the supplied path.
    """
    return Dir(path=str(path))


def _read_json(path: Path) -> dict[str, object]:
    """Read a manifest file into a dictionary for assertions.

    Args:
        path: Manifest file to parse for the repeat-filtering tests.

    Returns:
        Parsed JSON payload used by the repeat-filtering tests.
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


def _write_gff3(path: Path, records: list[str]) -> Path:
    """Write a minimal GFF3 file with a canonical header.

    Args:
        path: Destination for the synthetic GFF3 file.
        records: Annotation records written into the fixture.

    Returns:
        The GFF3 file path, which the tests hand back into the workflow.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("##gff-version 3\n" + "\n".join(records) + "\n")
    return path


def _write_fasta(path: Path, records: list[tuple[str, str]]) -> Path:
    """Write a minimal FASTA file from `(header, sequence)` pairs.

    Args:
        path: Destination for the synthetic FASTA file.
        records: Header and sequence pairs staged for the tests.

    Returns:
        The FASTA file path, which the tests hand back into the workflow.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for header, sequence in records:
        lines.append(f">{header}")
        lines.append(sequence)
    path.write_text("\n".join(lines) + "\n")
    return path


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
            return "20260403_120000"

    class _FixedDatetime:
        """Shim object that mimics the subset of `datetime` used by the code."""

        @classmethod
        def now(cls) -> _Stamp:
            """Return the fixed timestamp stub used by the synthetic tests."""
            return _Stamp()

    return _FixedDatetime


def _annotation_records() -> list[str]:
    """Return a small PASA-updated annotation used throughout the synthetic tests.

    This helper keeps the test fixture deterministic and explicit.

    Returns:
        The synthetic annotation records used across the repeat-filter tests.
    """
    return [
        "chr1\tPASA\tgene\t1\t100\t.\t+\t.\tID=evm.model.1",
        "chr1\tPASA\tmRNA\t1\t100\t.\t+\t.\tID=evm.TU.1;Parent=evm.model.1",
        "chr1\tPASA\tgene\t200\t300\t.\t+\t.\tID=evm.model.2",
        "chr1\tPASA\tmRNA\t200\t300\t.\t+\t.\tID=evm.TU.2;Parent=evm.model.2",
        "chr1\tPASA\tgene\t400\t500\t.\t+\t.\tID=evm.model.3",
    ]


def _create_pasa_update_results(tmp_path: Path) -> Path:
    """Create a minimal PASA-update bundle with the fields repeat filtering consumes.

    Args:
        tmp_path: Temporary root used to stage the bundle.

    Returns:
        The staged PASA-update result directory.
    """
    results_dir = tmp_path / "pasa_update_results"
    staged_reference = results_dir / "staged_inputs" / "reference"
    staged_reference.mkdir(parents=True, exist_ok=True)
    _write_fasta(staged_reference / "genome.fa", [("chr1", "ACGTACGTACGTACGT")])
    sorted_gff3 = _write_gff3(results_dir / "post_pasa_updates.sort.gff3", _annotation_records())
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "annotation_refinement_pasa",
            "outputs": {
                "final_sorted_gff3": str(sorted_gff3),
            },
        },
    )
    return results_dir


class RepeatFilteringTaskTests(TestCase):
    """Task-level coverage for the repeat-filtering stage boundary.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_repeatmasker_out_to_bed_converts_generated_gff3_to_downstream_bed(self) -> None:
        """Extract the deterministic three-column BED described in the tool reference.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repeatmasker_out = tmp_path / "genome.fasta.out"
            repeatmasker_out.write_text("placeholder\n")

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Write the minimal RepeatMasker GFF3 conversion output."""
                self.assertIsNotNone(stdout_path)
                stdout_path.write_text(
                    "##gff-version 3\n"
                    "chr1\tRepeatMasker\trepeat_region\t10\t20\t.\t+\t.\tID=rep1\n"
                )

            with patch.object(filtering, "run_tool", side_effect=fake_run_tool):
                results = filtering.repeatmasker_out_to_bed(
                    repeatmasker_out=File(path=str(repeatmasker_out))
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")
            self.assertTrue((results_dir / "repeatmasker.gff3").exists())
            self.assertEqual((results_dir / "repeatmasker.bed").read_text(), "chr1\t10\t20\n")
            self.assertTrue((results_dir / "genome.fasta.out").exists())
            self.assertIn("rmout_to_gff3_script", manifest["inputs"])

    def test_funannotate_remove_bad_models_resolves_clean_gff3_and_removal_list(self) -> None:
        """Capture the clean GFF3 plus overlap-removal list emitted by the funannotate stage.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            annotation_gff3 = _write_gff3(tmp_path / "annotation.gff3", _annotation_records())
            proteins_fasta = _write_fasta(tmp_path / "annotation.proteins.fa", [("tx1", "MAAP")])
            repeatmasker_bed = tmp_path / "repeatmasker.bed"
            repeatmasker_bed.write_text("chr1\t10\t20\n")

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Write the minimal funannotate-cleaned outputs."""
                self.assertIsNotNone(cwd)
                _write_gff3(cwd / "annotation.clean.gff3", _annotation_records()[1:])
                (cwd / "genome.repeats.to.remove.gff").write_text(
                    "chr1\tPASA\tgene\t200\t300\t.\t+\t.\tID=evm.model.2\n"
                    "chr1\tPASA\tmRNA\t200\t300\t.\t+\t.\tID=evm.TU.2;Parent=evm.model.2\n"
                )

            with patch.object(filtering, "run_tool", side_effect=fake_run_tool):
                results = filtering.funannotate_remove_bad_models(
                    annotation_gff3=File(path=str(annotation_gff3)),
                    proteins_fasta=File(path=str(proteins_fasta)),
                    repeatmasker_bed=File(path=str(repeatmasker_bed)),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")
            self.assertTrue((results_dir / "annotation.clean.gff3").exists())
            self.assertTrue((results_dir / "genome.repeats.to.remove.gff").exists())
            self.assertEqual(Path(str(manifest["outputs"]["models_to_remove"])).name, "genome.repeats.to.remove.gff")

    def test_remove_repeat_blast_hits_filters_parent_and_translated_ids(self) -> None:
        """Remove blast hits using both direct IDs and the deterministic evm.model/evm.TU mapping.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            annotation_gff3 = _write_gff3(tmp_path / "annotation.gff3", _annotation_records())
            repeat_blast_dir = tmp_path / "repeat_blast"
            repeat_blast_dir.mkdir(parents=True, exist_ok=True)
            (repeat_blast_dir / "repeat.dmnd.blast.txt").write_text("evm.model.1\trepeat_hit\n")

            results = filtering.remove_repeat_blast_hits(
                annotation_gff3=File(path=str(annotation_gff3)),
                repeat_blast_results=_artifact_dir(repeat_blast_dir),
            )

            filtered_gff3 = Path(results.download_sync()) / "all_repeats_removed.gff3"
            filtered_text = filtered_gff3.read_text()
            self.assertNotIn("evm.model.1", filtered_text)
            self.assertNotIn("evm.TU.1", filtered_text)
            self.assertIn("evm.model.2", filtered_text)
            self.assertIn("evm.model.3", filtered_text)


class RepeatFilteringWorkflowTests(TestCase):
    """Workflow-level coverage for the repeat-filtering biological stage.

    This test class keeps the current contract explicit and documents the current boundary behavior.
"""

    def test_annotation_repeat_filtering_collects_stable_final_outputs(self) -> None:
        """Run the synthetic repeat-filtering workflow and collect stable final filenames.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_update_results = _create_pasa_update_results(tmp_path)
            repeatmasker_out = tmp_path / "genome.fasta.out"
            repeatmasker_out.write_text("placeholder\n")
            funannotate_db = tmp_path / "funannotate_db"
            funannotate_db.mkdir(parents=True, exist_ok=True)

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                """Dispatch the repeat-filter subcommands by signature."""
                if stdout_path is not None and "rmOutToGFF3.pl" in cmd[1]:
                    stdout_path.write_text(
                        "##gff-version 3\n"
                        "chr1\tRepeatMasker\trepeat_region\t190\t310\t.\t+\t.\tID=rep2\n"
                    )
                    return

                if cmd[0] == "gffread":
                    output_index = cmd.index("-y") + 1
                    output_path = Path(cmd[output_index])
                    output_path.write_text(">prot1\nMA.P.\n")
                    return

                if "RemoveBadModels" in cmd[2]:
                    assert cwd is not None
                    _write_gff3(cwd / "post_pasa_updates.clean.gff3", _annotation_records())
                    (cwd / "genome.repeats.to.remove.gff").write_text(
                        "chr1\tPASA\tgene\t200\t300\t.\t+\t.\tID=evm.model.2\n"
                        "chr1\tPASA\tmRNA\t200\t300\t.\t+\t.\tID=evm.TU.2;Parent=evm.model.2\n"
                    )
                    return

                if "RepeatBlast" in cmd[2]:
                    assert cwd is not None
                    (cwd / "repeat.dmnd.blast.txt").write_text("evm.model.1\trepeat_hit\n")
                    return

                raise AssertionError(f"Unexpected command: {cmd}")

            with (
                patch.object(filtering, "run_tool", side_effect=fake_run_tool),
                patch.object(filtering, "datetime", _fixed_datetime()),
            ):
                results = annotation_repeat_filtering(
                    pasa_update_results=_artifact_dir(pasa_update_results),
                    repeatmasker_out=File(path=str(repeatmasker_out)),
                    funannotate_db_path=str(funannotate_db),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "repeatmasker.gff3").exists())
            self.assertTrue((results_dir / "repeatmasker.bed").exists())
            self.assertTrue((results_dir / "post_pasa_updates.proteins.fa").exists())
            self.assertTrue((results_dir / "post_pasa_updates.proteins.no_periods.fa").exists())
            self.assertTrue((results_dir / "bed_repeats_removed.gff3").exists())
            self.assertTrue((results_dir / "repeat.dmnd.blast.txt").exists())
            self.assertTrue((results_dir / "all_repeats_removed.gff3").exists())
            self.assertTrue((results_dir / "all_repeats_removed.proteins.fa").exists())
            self.assertTrue((results_dir / "all_repeats_removed.proteins.no_periods.fa").exists())
            self.assertTrue((results_dir / "reference" / "genome.fa").exists())
            self.assertTrue((results_dir / "source_boundary" / "post_pasa_updates.sort.gff3").exists())
            self.assertEqual(
                sorted(path.name for path in (results_dir / "source_manifests").glob("*.json")),
                ["pasa_update.run_manifest.json"],
            )
            final_text = (results_dir / "all_repeats_removed.gff3").read_text()
            self.assertNotIn("evm.model.1", final_text)
            self.assertNotIn("evm.model.2", final_text)
            self.assertIn("evm.model.3", final_text)
            self.assertEqual(
                sorted(manifest["outputs"].keys()),
                [
                    "all_repeats_removed_gff3",
                    "bed_filtered_proteins_fasta",
                    "bed_filtered_sanitized_proteins_fasta",
                    "bed_repeats_removed_gff3",
                    "clean_gff3",
                    "final_proteins_fasta",
                    "final_sanitized_proteins_fasta",
                    "initial_proteins_fasta",
                    "initial_sanitized_proteins_fasta",
                    "models_to_remove",
                    "repeat_blast_hits",
                    "repeatmasker_bed",
                    "repeatmasker_gff3",
                ],
            )

    def test_repeatmasker_fixture_inputs_exist_for_optional_smoke_runs(self) -> None:
        """Keep the local RepeatMasker fixture set visible for later binary-backed smoke tests.

    This test keeps the current contract explicit and guards the documented behavior against regression.
"""
        fixture_root = TESTS_DIR.parent / "data" / "repeatmasker"
        download_script = TESTS_DIR.parent / "scripts" / "rcc" / "download_minimal_repeatmasker_fixture.sh"
        expected = {
            "genome_raw.fasta",
            "Muco_library_RM2.fasta",
            "Muco_library_EDTA.fasta",
        }

        self.assertTrue(download_script.exists())
        script_text = download_script.read_text()
        for filename in expected:
            self.assertIn(filename, script_text)

        # The GTN fixture is restored into ignored local data/, so skip cleanly when it is absent.
        if not fixture_root.exists():
            self.skipTest("RepeatMasker smoke fixtures are not staged; run scripts/rcc/download_minimal_repeatmasker_fixture.sh.")
        self.assertTrue(fixture_root.exists())
        self.assertEqual({path.name for path in fixture_root.iterdir() if path.is_file() and path.name in expected}, expected)
