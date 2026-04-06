"""Tests for the BRAKER3 task boundary and normalization policy.

These checks keep the Milestone 5 source-preserving BRAKER3 normalization
reviewable without requiring a native BRAKER installation.
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

from flytetest.tasks import annotation


def _artifact_dir(path: Path) -> Dir:
    """Create a stub Flyte directory artifact from a local path."""
    return Dir.from_local_sync(str(path))


def _artifact_file(path: Path) -> File:
    """Create a stub Flyte file artifact from a local path."""
    return File.from_local_sync(str(path))


def _read_json(path: Path) -> dict[str, object]:
    """Read a JSON payload for assertions."""
    return json.loads(path.read_text())


def _fixed_datetime() -> type:
    """Return a deterministic timestamp provider for result-directory naming."""

    class _Stamp:
        def strftime(self, fmt: str) -> str:
            return "20260402_090000"

    class _FixedDatetime:
        @classmethod
        def now(cls) -> _Stamp:
            return _Stamp()

    return _FixedDatetime


class AnnotationTaskTests(TestCase):
    """Task-level coverage for the BRAKER3 source-preserving normalization policy."""

    def test_stage_braker3_inputs_requires_at_least_one_evidence_input(self) -> None:
        """Reject empty BRAKER3 staging requests so runtime boundaries stay explicit."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            genome_path = tmp_path / "genome.fa"
            genome_path.write_text(">chr1\nACGTACGT\n")

            with self.assertRaisesRegex(ValueError, "requires at least one local BRAKER3 evidence input"):
                annotation.stage_braker3_inputs(
                    genome=_artifact_file(genome_path),
                )

    def test_braker3_predict_records_tutorial_backed_command_boundary(self) -> None:
        """Capture the BRAKER3 runtime command with explicit RNA-seq and protein inputs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            genome_path = tmp_path / "genome.fa"
            rnaseq_bam = tmp_path / "RNAseq.bam"
            proteins_fa = tmp_path / "proteins.fa"
            genome_path.write_text(">chr1\nACGTACGT\n")
            rnaseq_bam.write_text("bam\n")
            proteins_fa.write_text(">prot1\nMAMA\n")

            staged = annotation.stage_braker3_inputs(
                genome=_artifact_file(genome_path),
                rnaseq_bam_path=str(rnaseq_bam),
                protein_fasta_path=str(proteins_fa),
            )
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                captured["cmd"] = cmd
                working_dir = Path(str(cmd[cmd.index("--workingdir") + 1]))
                (working_dir / "braker.gff3").write_text(
                    "##gff-version 3\nchr1\tAugustus\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
                )

            with patch.object(annotation, "run_tool", side_effect=fake_run_tool):
                braker_run = annotation.braker3_predict(
                    staged_inputs=staged,
                    braker_species="flytetest_species",
                )

            run_dir = Path(braker_run.download_sync())
            manifest = _read_json(run_dir / "run_manifest.json")
            cmd = captured["cmd"]

            self.assertEqual(cmd[:2], ["braker.pl", "--genome"])
            self.assertIn("--bam", cmd)
            self.assertIn("--prot_seq", cmd)
            self.assertIn("--gff3", cmd)
            self.assertEqual(cmd[cmd.index("--species") + 1], "flytetest_species")
            self.assertTrue((run_dir / "braker.gff3").exists())
            self.assertIn("tutorial_backed_behavior", manifest)
            self.assertEqual(Path(str(manifest["outputs"]["braker_gff3"])).name, "braker.gff3")

    def test_normalize_braker3_for_evm_preserves_upstream_source_values(self) -> None:
        """Keep native BRAKER source labels instead of rewriting them to BRAKER3."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir = tmp_path / "braker_run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run_manifest.json").write_text("{}\n")
            (run_dir / "braker.gff3").write_text(
                "\n".join(
                    [
                        "##gff-version 3",
                        "##gff-version 3",
                        "# synthetic comment",
                        "chr1\tAugustus\tgene\t1\t20\t.\t+\t.\tID=gene1",
                        "chr1\tgmst\tmRNA\t1\t20\t.\t+\t.\tID=mrna1;Parent=gene1",
                    ]
                )
                + "\n"
            )

            normalized = annotation.normalize_braker3_for_evm(braker_run=_artifact_dir(run_dir))

            normalized_dir = Path(normalized.download_sync())
            normalized_gff3 = normalized_dir / "braker3.evm.gff3"
            manifest = _read_json(normalized_dir / "run_manifest.json")

            self.assertEqual(
                normalized_gff3.read_text().splitlines(),
                [
                    "##gff-version 3",
                    "# synthetic comment",
                    "chr1\tAugustus\tgene\t1\t20\t.\t+\t.\tID=gene1",
                    "chr1\tgmst\tmRNA\t1\t20\t.\t+\t.\tID=mrna1;Parent=gene1",
                ],
            )
            self.assertEqual(manifest["inputs"]["source_fields"], ["Augustus", "gmst"])
            self.assertEqual(manifest["outputs"]["normalized_source_fields"], ["Augustus", "gmst"])
            self.assertIn("notes_backed_behavior", manifest)
            self.assertIn("tutorial_backed_behavior", manifest)
            self.assertIn("repo_policy", manifest)

    def test_collect_braker3_results_manifest_records_policy_sections(self) -> None:
        """Surface note-backed, tutorial-backed, and repo-policy language in the result bundle."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            genome_path = tmp_path / "genome.fa"
            genome_path.write_text(">chr1\nACGTACGT\n")

            staged_dir = tmp_path / "staged_inputs"
            (staged_dir / "genome").mkdir(parents=True, exist_ok=True)
            (staged_dir / "genome" / "genome.fa").write_text(">chr1\nACGTACGT\n")
            _ = (staged_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "source_inputs": {
                            "rnaseq_bam_path": "/tmp/RNAseq.bam",
                            "protein_fasta_path": "/tmp/proteins.fa",
                        }
                    },
                    indent=2,
                )
            )

            raw_dir = tmp_path / "braker_raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / "braker.gff3").write_text("##gff-version 3\nchr1\tAugustus\tgene\t1\t20\t.\t+\t.\tID=gene1\n")
            (raw_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "notes_backed_behavior": ["`braker.gff3` is the notes-backed output contract."],
                        "tutorial_backed_behavior": ["Galaxy tutorial-backed runtime."],
                        "repo_policy": ["Raw BRAKER output is preserved."],
                    },
                    indent=2,
                )
            )

            normalized_dir = tmp_path / "braker_normalized"
            normalized_dir.mkdir(parents=True, exist_ok=True)
            (normalized_dir / "braker3.evm.gff3").write_text(
                "##gff-version 3\nchr1\tAugustus\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
            )
            (normalized_dir / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "notes_backed_behavior": ["Notes require matching EVM source labels."],
                        "tutorial_backed_behavior": ["Derived from tutorial-backed BRAKER output."],
                        "repo_policy": ["Normalization preserves upstream source labels."],
                        "outputs": {"normalized_source_fields": ["Augustus"]},
                    },
                    indent=2,
                )
            )

            with patch.object(annotation, "datetime", _fixed_datetime()):
                results = annotation.collect_braker3_results(
                    genome=_artifact_file(genome_path),
                    staged_inputs=_artifact_dir(staged_dir),
                    braker_run=_artifact_dir(raw_dir),
                    normalized_braker=_artifact_dir(normalized_dir),
                    braker_species="flytetest_braker3",
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertEqual(manifest["outputs"]["normalized_source_fields"], ["Augustus"])
            self.assertIn("notes_backed_behavior", manifest)
            self.assertIn("tutorial_backed_behavior", manifest)
            self.assertIn("repo_policy", manifest)
            self.assertIn("preserves upstream BRAKER source-column values", " ".join(manifest["repo_policy"]))
