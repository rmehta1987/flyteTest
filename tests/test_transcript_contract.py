"""Synthetic tests for the transcript-to-PASA contract.

These checks keep the de novo-plus-genome-guided Trinity branch, StringTie
flags, and PASA handoff honest without requiring STAR, Trinity, StringTie,
or PASA binaries.
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

import flytetest.tasks.transcript_evidence as transcript_tasks
import flytetest.workflows.pasa as pasa_workflows


def _artifact_dir(path: Path) -> Dir:
    """Create a stub Flyte directory artifact from a local path."""
    return Dir.from_local_sync(str(path))


def _read_json(path: Path) -> dict[str, object]:
    """Read one JSON file for assertions."""
    return json.loads(path.read_text())


def _fixed_datetime() -> type:
    """Return a deterministic timestamp provider for result-directory naming."""

    class _Stamp:
        def strftime(self, fmt: str) -> str:
            return "20260402_130000"

    class _FixedDatetime:
        @classmethod
        def now(cls) -> _Stamp:
            return _Stamp()

    return _FixedDatetime


class TranscriptContractTests(TestCase):
    """Coverage for the transcript-evidence branch and PASA handoff."""

    def test_trinity_denovo_assemble_uses_single_sample_paired_end_shape(self) -> None:
        """Keep the de novo Trinity task explicit and deterministic."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            left = tmp_path / "reads_1.fq.gz"
            right = tmp_path / "reads_2.fq.gz"
            left.write_text("@r1\nACGT\n+\n!!!!\n")
            right.write_text("@r2\nTGCA\n+\n!!!!\n")
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                captured["cmd"] = cmd

            with patch.object(transcript_tasks, "run_tool", side_effect=fake_run_tool):
                transcript_tasks.trinity_denovo_assemble(
                    left=File(path=str(left)),
                    right=File(path=str(right)),
                    sample_id="sampleA",
                    trinity_cpu=8,
                    trinity_max_memory_gb=64,
                )

            cmd = captured["cmd"]
            self.assertEqual(cmd[:3], ["Trinity", "--seqType", "fq"])
            self.assertEqual(cmd[cmd.index("--left") + 1], str(left))
            self.assertEqual(cmd[cmd.index("--right") + 1], str(right))
            self.assertEqual(cmd[cmd.index("--CPU") + 1], "8")
            self.assertEqual(cmd[cmd.index("--max_memory") + 1], "64G")
            self.assertIn("--output", cmd)
            self.assertNotIn("--genome_guided_bam", cmd)

    def test_stringtie_assemble_uses_note_backed_flags(self) -> None:
        """Keep the exposed StringTie command aligned with the attached notes."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            merged_bam = tmp_path / "merged.bam"
            merged_bam.write_text("bam\n")
            captured: dict[str, object] = {}

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                captured["cmd"] = cmd

            with patch.object(transcript_tasks, "run_tool", side_effect=fake_run_tool):
                transcript_tasks.stringtie_assemble(
                    merged_bam=File(path=str(merged_bam)),
                    stringtie_threads=16,
                )

            cmd = captured["cmd"]
            self.assertEqual(cmd[:2], ["stringtie", str(merged_bam)])
            self.assertIn("-l", cmd)
            self.assertEqual(cmd[cmd.index("-l") + 1], "STRG")
            self.assertIn("-f", cmd)
            self.assertEqual(cmd[cmd.index("-f") + 1], "0.10")
            self.assertIn("-c", cmd)
            self.assertEqual(cmd[cmd.index("-c") + 1], "3")
            self.assertIn("-j", cmd)
            self.assertEqual(cmd[cmd.index("-j") + 1], "3")
            self.assertEqual(cmd[cmd.index("-p") + 1], "16")

    def test_collect_transcript_evidence_results_marks_bundle_as_pasa_ready(self) -> None:
        """Mark the collected transcript bundle as upstream-complete for PASA."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            genome = tmp_path / "genome.fa"
            left = tmp_path / "reads_1.fq.gz"
            right = tmp_path / "reads_2.fq.gz"
            genome.write_text(">chr1\nACGT\n")
            left.write_text("@r1\nACGT\n+\n!!!!\n")
            right.write_text("@r2\nTGCA\n+\n!!!!\n")

            trinity_denovo = tmp_path / "trinity_denovo"
            star_index = tmp_path / "star_index"
            alignment = tmp_path / "alignment"
            trinity_gg = tmp_path / "trinity_gg"
            stringtie = tmp_path / "stringtie"
            merged_bam_dir = tmp_path / "merged"
            trinity_denovo.mkdir()
            star_index.mkdir()
            alignment.mkdir()
            trinity_gg.mkdir()
            stringtie.mkdir()
            merged_bam_dir.mkdir()

            (trinity_denovo / "Trinity.fasta").write_text(">denovo1\nATGC\n")
            (alignment / "Aligned.sortedByCoord.out.bam").write_text("bam\n")
            (alignment / "Log.final.out").write_text("STAR log\n")
            (trinity_gg / "Trinity-GG.fasta").write_text(">gg1\nATGG\n")
            (stringtie / "transcripts.gtf").write_text("chr1\tStringTie\ttranscript\t1\t4\t.\t+\t.\tgene_id \"g1\";\n")
            (stringtie / "gene_abund.tab").write_text("Gene ID\tCoverage\n")
            merged_bam = merged_bam_dir / "merged.bam"
            merged_bam.write_text("bam\n")

            with patch.object(transcript_tasks, "datetime", _fixed_datetime()):
                result = transcript_tasks.collect_transcript_evidence_results(
                    genome=File(path=str(genome)),
                    left=File(path=str(left)),
                    right=File(path=str(right)),
                    trinity_denovo=_artifact_dir(trinity_denovo),
                    star_index=_artifact_dir(star_index),
                    alignment=_artifact_dir(alignment),
                    merged_bam=File(path=str(merged_bam)),
                    trinity_gg=_artifact_dir(trinity_gg),
                    stringtie=_artifact_dir(stringtie),
                    sample_id="sampleA",
                )

            manifest = _read_json(Path(result.download_sync()) / "run_manifest.json")

            self.assertEqual(
                manifest["notes_alignment"]["status"],
                "implemented_with_documented_simplifications",
            )
            self.assertTrue(manifest["notes_alignment"]["pasa_ready"])
            assumptions = "\n".join(manifest["assumptions"])
            self.assertIn("both Trinity branches required upstream of PASA", manifest["notes_alignment"]["reason"])
            self.assertIn("de novo Trinity before STAR alignment", assumptions)
            self.assertIn("aligning all RNA-seq samples", assumptions)
            self.assertIn("Trinity --left/--right", assumptions)
            self.assertIn("StringTie is run with the note-backed fixed flags", assumptions)
            self.assertIn("trinity_denovo_fasta", manifest["outputs"])

    def test_pasa_transcript_alignment_uses_internal_denovo_trinity_from_bundle(self) -> None:
        """Resolve the de novo Trinity FASTA from the transcript bundle instead of an external path."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            transcript_bundle = tmp_path / "transcript_bundle"
            trinity_denovo_dir = transcript_bundle / "trinity_denovo"
            trinity_gg_dir = transcript_bundle / "trinity_gg"
            stringtie_dir = transcript_bundle / "stringtie"
            trinity_denovo_dir.mkdir(parents=True)
            trinity_gg_dir.mkdir()
            stringtie_dir.mkdir()

            denovo_fasta = trinity_denovo_dir / "Trinity.fasta"
            gg_fasta = trinity_gg_dir / "Trinity-GG.fasta"
            stringtie_gtf = stringtie_dir / "transcripts.gtf"
            denovo_fasta.write_text(">denovo1\nATGC\n")
            gg_fasta.write_text(">gg1\nATGG\n")
            stringtie_gtf.write_text("chr1\tStringTie\ttranscript\t1\t4\t.\t+\t.\tgene_id \"g1\";\n")
            (transcript_bundle / "run_manifest.json").write_text(json.dumps({"sample_id": "sampleA"}))

            combined = tmp_path / "trinity_transcripts.fa"
            combined.write_text(">combined\nATGC\n")
            tdn_accs = tmp_path / "tdn.accs"
            tdn_accs.write_text("TDN1\n")
            seqclean_dir = tmp_path / "seqclean"
            config_dir = tmp_path / "config"
            pasa_dir = tmp_path / "pasa"
            result_dir = tmp_path / "results"
            seqclean_dir.mkdir()
            config_dir.mkdir()
            pasa_dir.mkdir()
            result_dir.mkdir()

            captured: dict[str, dict[str, object]] = {}

            def fake_combine_trinity_fastas(**kwargs: object) -> File:
                captured["combine"] = kwargs
                return File(path=str(combined))

            def fake_pasa_accession_extract(**kwargs: object) -> File:
                captured["accession"] = kwargs
                return File(path=str(tdn_accs))

            def fake_pasa_seqclean(**kwargs: object) -> Dir:
                captured["seqclean"] = kwargs
                return Dir(path=str(seqclean_dir))

            def fake_pasa_create_sqlite_db(**kwargs: object) -> Dir:
                captured["config"] = kwargs
                return Dir(path=str(config_dir))

            def fake_pasa_align_assemble(**kwargs: object) -> Dir:
                captured["align"] = kwargs
                return Dir(path=str(pasa_dir))

            def fake_collect_pasa_results(**kwargs: object) -> Dir:
                captured["collect"] = kwargs
                return Dir(path=str(result_dir))

            with patch.object(
                pasa_workflows,
                "combine_trinity_fastas",
                side_effect=fake_combine_trinity_fastas,
            ), patch.object(
                pasa_workflows,
                "pasa_accession_extract",
                side_effect=fake_pasa_accession_extract,
            ), patch.object(
                pasa_workflows,
                "pasa_seqclean",
                side_effect=fake_pasa_seqclean,
            ), patch.object(
                pasa_workflows,
                "pasa_create_sqlite_db",
                side_effect=fake_pasa_create_sqlite_db,
            ), patch.object(
                pasa_workflows,
                "pasa_align_assemble",
                side_effect=fake_pasa_align_assemble,
            ), patch.object(
                pasa_workflows,
                "collect_pasa_results",
                side_effect=fake_collect_pasa_results,
            ):
                result = pasa_workflows.pasa_transcript_alignment(
                    genome=File(path=str(tmp_path / "genome.fa")),
                    transcript_evidence_results=Dir(path=str(transcript_bundle)),
                    univec_fasta=File(path=str(tmp_path / "UniVec.txt")),
                    pasa_config_template=File(path=str(tmp_path / "pasa.alignAssembly.TEMPLATE.txt")),
                )

            self.assertEqual(Path(str(captured["combine"]["denovo_trinity_fasta"].path)), denovo_fasta)
            self.assertEqual(Path(str(captured["combine"]["genome_guided_trinity_fasta"].path)), gg_fasta)
            self.assertEqual(Path(str(captured["accession"]["denovo_trinity_fasta"].path)), denovo_fasta)
            self.assertEqual(Path(str(captured["align"]["tdn_accs"].path)), tdn_accs)
            self.assertEqual(Path(str(captured["collect"]["trinity_denovo_fasta"].path)), denovo_fasta)
            self.assertEqual(Path(str(result.path)), result_dir)
