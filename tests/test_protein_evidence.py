"""Tests for the Exonerate protein-evidence task chain.

The suite uses the tutorial-derived fixtures staged directly under `data/` for
lightweight real-data smoke coverage, while keeping collector and manifest
checks synthetic when a real tool run is unnecessary.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import shutil

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"
DATA_DIR = TESTS_DIR.parent / "data"
PROTEIN_FASTA = DATA_DIR / "braker3" / "protein_data" / "fastas" / "proteins.fa"
GENOME_FASTA = DATA_DIR / "braker3" / "reference" / "genome.fa"
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flyte.io import Dir, File

from flytetest.tasks import protein_evidence
import flytetest.workflows.protein_evidence as protein_evidence_workflow
from flytetest.workflows.protein_evidence import protein_evidence_alignment


EXONERATE_AVAILABLE = shutil.which("exonerate") is not None


def _copy_fasta_subset(source: Path, destination: Path, record_limit: int) -> Path:
    """Copy the first `record_limit` FASTA records from a real downloaded file."""
    if record_limit < 1:
        raise ValueError("record_limit must be at least 1")

    records = 0
    include_record = False
    with source.open() as source_handle, destination.open("w") as destination_handle:
        for line in source_handle:
            if line.startswith(">"):
                records += 1
                include_record = records <= record_limit
                if not include_record:
                    break
            if include_record:
                destination_handle.write(line)
    return destination


def _read_json(path: Path) -> dict[str, object]:
    """Read a manifest file into a dictionary for assertions."""
    return json.loads(path.read_text())


def _artifact_dir(path: Path) -> Dir:
    """Create a stub Flyte directory artifact from a local path."""
    return Dir.from_local_sync(str(path))


def _artifact_file(path: Path) -> File:
    """Create a stub Flyte file artifact from a local path."""
    return File.from_local_sync(str(path))


def _fixed_datetime() -> type:
    """Return a deterministic timestamp provider for result-directory naming."""

    class _Stamp:
        def strftime(self, fmt: str) -> str:
            return "20260401_120000"

    class _FixedDatetime:
        @classmethod
        def now(cls) -> _Stamp:
            return _Stamp()

    return _FixedDatetime


def _real_alignment_dir(tmp_path: Path, record_limit: int = 5) -> Path:
    """Run Exonerate on a small real subset derived from the downloaded tutorial data."""
    subset = _copy_fasta_subset(PROTEIN_FASTA, tmp_path / f"protein_subset_{record_limit}.fa", record_limit)
    alignment = protein_evidence.exonerate_align_chunk(
        genome=_artifact_file(GENOME_FASTA),
        protein_chunk=_artifact_file(subset),
        exonerate_sif="",
        exonerate_model="protein2genome",
    )
    return Path(alignment.download_sync())


class ProteinEvidenceTaskTests(TestCase):
    """Task-level coverage for the Exonerate staging and conversion boundary."""

    def test_stage_and_chunk_protein_fastas_preserve_input_order(self) -> None:
        """Stage and chunk small subsets copied from the local tutorial protein fixture."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first_subset = _copy_fasta_subset(PROTEIN_FASTA, tmp_path / "proteins_a.fa", 2)
            second_subset = _copy_fasta_subset(PROTEIN_FASTA, tmp_path / "proteins_b.fa", 3)

            staged = protein_evidence.stage_protein_fastas(
                protein_fastas=[_artifact_file(first_subset), _artifact_file(second_subset)]
            )
            staged_dir = Path(staged.download_sync())
            manifest = _read_json(staged_dir / "run_manifest.json")

            self.assertEqual(manifest["source_fasta_paths"], [str(first_subset), str(second_subset)])
            self.assertEqual(
                [Path(path).name for path in manifest["staged_input_paths"]],
                ["001_proteins_a.fa", "002_proteins_b.fa"],
            )
            self.assertTrue((staged_dir / "combined" / "proteins.all.fa").exists())
            self.assertTrue(
                (staged_dir / "combined" / "proteins.all.fa").read_text().startswith(
                    first_subset.read_text().splitlines()[0]
                )
            )

            chunked = protein_evidence.chunk_protein_fastas(
                staged_proteins=staged,
                proteins_per_chunk=2,
            )
            chunk_dir = Path(chunked.download_sync())
            chunk_manifest = _read_json(chunk_dir / "run_manifest.json")

            self.assertEqual(chunk_manifest["total_proteins"], 5)
            self.assertEqual(chunk_manifest["chunk_count"], 3)
            self.assertEqual(
                [chunk["chunk_label"] for chunk in chunk_manifest["chunks"]],
                ["chunk_0001", "chunk_0002", "chunk_0003"],
            )
            self.assertEqual(
                sorted(path.name for path in (chunk_dir / "chunks").glob("chunk_*.fa")),
                ["chunk_0001.fa", "chunk_0002.fa", "chunk_0003.fa"],
            )

    def test_exonerate_align_chunk_records_command_and_manifest(self) -> None:
        """Capture the Exonerate command contract while using local fixture-derived inputs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subset = _copy_fasta_subset(PROTEIN_FASTA, tmp_path / "protein_subset.fa", 2)

            seen: dict[str, object] = {}

            def fake_run_tool(cmd: list[str], sif: str, bind_paths: list[Path], cwd=None, stdout_path=None) -> None:
                seen["cmd"] = cmd
                seen["sif"] = sif
                seen["bind_paths"] = [Path(path) for path in bind_paths]
                seen["cwd"] = cwd
                seen["stdout_path"] = stdout_path
                assert stdout_path is not None
                stdout_path.write_text(
                    "status line\n"
                    "chr1\texonerate_protein\tmatch\t1\t10\t.\t+\t.\tID=hit1\n"
                )

            with patch.object(protein_evidence, "run_tool", fake_run_tool):
                alignment = protein_evidence.exonerate_align_chunk(
                    genome=_artifact_file(GENOME_FASTA),
                    protein_chunk=_artifact_file(subset),
                    exonerate_sif="",
                    exonerate_model="protein2genome",
                )

            alignment_dir = Path(alignment.download_sync())
            manifest = _read_json(alignment_dir / "run_manifest.json")

            self.assertEqual(seen["cmd"][0], "exonerate")
            self.assertIn("--showtargetgff", seen["cmd"])
            self.assertEqual(seen["cmd"][seen["cmd"].index("--showtargetgff") + 1], "yes")
            self.assertEqual(seen["sif"], "")
            self.assertEqual(
                {Path(path) for path in seen["bind_paths"]},
                {GENOME_FASTA.parent, subset.parent, Path(seen["stdout_path"]).parent},
            )
            self.assertEqual(manifest["stage"], "exonerate_align_chunk")
            self.assertEqual(manifest["chunk_label"], "protein_subset")
            self.assertEqual(Path(manifest["outputs"]["raw_output"]).name, "protein_subset.exonerate.out")
            self.assertEqual(manifest["inputs"]["model"], "protein2genome")

    @unittest.skipUnless(EXONERATE_AVAILABLE, "exonerate is required for the real-data smoke test")
    def test_exonerate_align_chunk_real_data_smoke(self) -> None:
        """Run Exonerate on a tiny tutorial-derived subset and confirm real GFF output."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            alignment_dir = _real_alignment_dir(tmp_path, record_limit=2)
            manifest = _read_json(alignment_dir / "run_manifest.json")
            raw_output = alignment_dir / "protein_subset_2.exonerate.out"

            self.assertEqual(manifest["stage"], "exonerate_align_chunk")
            self.assertTrue(raw_output.exists())
            self.assertGreater(raw_output.stat().st_size, 0)

    def test_exonerate_to_evm_gff3_converts_only_gff_records(self) -> None:
        """Keep 9-column Exonerate target-GFF lines and normalize the source column."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            alignment_dir = tmp_path / "alignment"
            alignment_dir.mkdir()
            (alignment_dir / "chunk_0001.exonerate.out").write_text(
                "status line\n"
                "chr1\texonerate\tgene\t1\t9\t.\t+\t.\tID=gene1\n"
                "chr1\ttoo\tfew\tcolumns\n"
            )
            (alignment_dir / "run_manifest.json").write_text("{}")

            converted = protein_evidence.exonerate_to_evm_gff3(
                exonerate_alignment=_artifact_dir(alignment_dir)
            )

            converted_dir = Path(converted.download_sync())
            manifest = _read_json(converted_dir / "run_manifest.json")
            gff3_path = Path(manifest["outputs"]["evm_gff3"])

            self.assertEqual(manifest["gff_line_count"], 1)
            self.assertEqual(
                gff3_path.read_text().splitlines(),
                [
                    "##gff-version 3",
                    "chr1\texonerate_protein\tgene\t1\t9\t.\t+\t.\tID=gene1",
                ],
            )

    def test_exonerate_to_evm_gff3_rejects_non_gff_output(self) -> None:
        """Fail fast when the raw Exonerate stdout contains no 9-column GFF records."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            alignment_dir = tmp_path / "alignment"
            alignment_dir.mkdir()
            (alignment_dir / "chunk_0001.exonerate.out").write_text("status only\n")

            with self.assertRaises(ValueError):
                protein_evidence.exonerate_to_evm_gff3(
                    exonerate_alignment=_artifact_dir(alignment_dir)
                )

    def test_exonerate_concat_results_builds_sorted_bundle(self) -> None:
        """Collect raw and converted chunk results into a stable, ordered bundle."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first_subset = _copy_fasta_subset(PROTEIN_FASTA, tmp_path / "proteins_a.fa", 1)
            second_subset = _copy_fasta_subset(PROTEIN_FASTA, tmp_path / "proteins_b.fa", 2)
            staged = protein_evidence.stage_protein_fastas(
                protein_fastas=[
                    _artifact_file(first_subset),
                    _artifact_file(second_subset),
                ]
            )
            chunked = protein_evidence.chunk_protein_fastas(
                staged_proteins=staged,
                proteins_per_chunk=2,
            )

            raw_dirs: list[Dir] = []
            converted_dirs: list[Dir] = []
            for chunk_name in ["chunk_0002", "chunk_0001"]:
                raw_dir = tmp_path / f"raw_{chunk_name}"
                raw_dir.mkdir()
                (raw_dir / f"{chunk_name}.exonerate.out").write_text(
                    f"# raw {chunk_name}\n"
                    f"chr1\texonerate\tgene\t1\t9\t.\t+\t.\tID={chunk_name}\n"
                )
                (raw_dir / "run_manifest.json").write_text(
                    json.dumps({"inputs": {"model": "protein2genome"}})
                )
                raw_dirs.append(_artifact_dir(raw_dir))

                converted_dir = tmp_path / f"converted_{chunk_name}"
                converted_dir.mkdir()
                (converted_dir / f"{chunk_name}.evm.gff3").write_text(
                    "##gff-version 3\n"
                    f"chr1\texonerate_protein\tgene\t1\t9\t.\t+\t.\tID={chunk_name}\n"
                )
                (converted_dir / "run_manifest.json").write_text(
                    json.dumps({"assumptions": ["Converted for downstream EVM input."]})
                )
                converted_dirs.append(_artifact_dir(converted_dir))

            with patch.object(protein_evidence, "RESULTS_ROOT", str(tmp_path / "results")):
                with patch.object(protein_evidence, "datetime", _fixed_datetime()):
                    bundle = protein_evidence.exonerate_concat_results(
                        genome=_artifact_file(GENOME_FASTA),
                        staged_proteins=staged,
                        protein_chunks=chunked,
                        raw_chunk_results=raw_dirs,
                        evm_chunk_results=converted_dirs,
                    )

            bundle_dir = Path(bundle.download_sync())
            manifest = _read_json(bundle_dir / "run_manifest.json")

            self.assertEqual(manifest["raw_chunk_labels"], ["chunk_0001", "chunk_0002"])
            self.assertEqual(manifest["converted_chunk_labels"], ["chunk_0001", "chunk_0002"])
            self.assertTrue((bundle_dir / "all_chunks.exonerate.out").read_text().startswith("# chunk=chunk_0001"))
            self.assertEqual(
                (bundle_dir / "protein_evidence.evm.gff3").read_text().splitlines(),
                [
                    "##gff-version 3",
                    "chr1\texonerate_protein\tgene\t1\t9\t.\t+\t.\tID=chunk_0001",
                    "chr1\texonerate_protein\tgene\t1\t9\t.\t+\t.\tID=chunk_0002",
                ],
            )


class ProteinEvidenceWorkflowTests(TestCase):
    """Workflow-level coverage for the Exonerate fan-out and collection order."""

    def test_protein_evidence_alignment_runs_expected_stage_order(self) -> None:
        """Confirm the workflow stages, fans out by chunk, and collects once at the end."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            calls: list[str] = []
            expected_chunk_labels: list[str] = []

            staged = protein_evidence.stage_protein_fastas(
                protein_fastas=[_artifact_file(PROTEIN_FASTA)]
            )
            chunked = protein_evidence.chunk_protein_fastas(
                staged_proteins=staged,
                proteins_per_chunk=20,
            )
            chunk_manifest = _read_json(Path(chunked.download_sync()) / "run_manifest.json")
            expected_chunk_labels.extend([str(chunk["chunk_label"]) for chunk in chunk_manifest["chunks"]])

            original_stage = protein_evidence_workflow.stage_protein_fastas
            original_chunk = protein_evidence_workflow.chunk_protein_fastas

            def wrapped_stage(*, protein_fastas: list[File]) -> Dir:
                calls.append("stage")
                self.assertEqual([artifact.path for artifact in protein_fastas], [str(PROTEIN_FASTA)])
                return staged

            def wrapped_chunk(*, staged_proteins: Dir, proteins_per_chunk: int) -> Dir:
                calls.append("chunk")
                self.assertEqual(staged_proteins.download_sync(), staged.download_sync())
                self.assertEqual(proteins_per_chunk, 20)
                return chunked

            def wrapped_align(*, genome: File, protein_chunk: File, exonerate_sif: str = "", exonerate_model: str = "protein2genome") -> Dir:
                chunk_name = Path(protein_chunk.download_sync()).stem
                calls.append(f"align:{chunk_name}")
                raw_dir = tmp_path / f"raw_{chunk_name}"
                raw_dir.mkdir(exist_ok=True)
                (raw_dir / f"{chunk_name}.exonerate.out").write_text(
                    f"chr1\texonerate\tgene\t1\t9\t.\t+\t.\tID={chunk_name}\n"
                )
                (raw_dir / "run_manifest.json").write_text(json.dumps({"inputs": {"model": exonerate_model}}))
                return _artifact_dir(raw_dir)

            def wrapped_convert(*, exonerate_alignment: Dir) -> Dir:
                raw_dir = Path(exonerate_alignment.download_sync())
                chunk_name = next(raw_dir.glob("*.exonerate.out")).stem.removesuffix(".exonerate")
                calls.append(f"convert:{chunk_name}")
                converted_dir = tmp_path / f"converted_{chunk_name}"
                converted_dir.mkdir(exist_ok=True)
                (converted_dir / f"{chunk_name}.evm.gff3").write_text(
                    "##gff-version 3\n"
                    f"chr1\texonerate_protein\tgene\t1\t9\t.\t+\t.\tID={chunk_name}\n"
                )
                (converted_dir / "run_manifest.json").write_text(json.dumps({"assumptions": ["synthetic conversion"]}))
                return _artifact_dir(converted_dir)

            def wrapped_collect_results(
                *,
                genome: File,
                staged_proteins: Dir,
                protein_chunks: Dir,
                raw_chunk_results: list[Dir],
                evm_chunk_results: list[Dir],
            ) -> Dir:
                calls.append("collect")
                output_dir = tmp_path / "workflow_result"
                output_dir.mkdir(exist_ok=True)
                (output_dir / "run_manifest.json").write_text(json.dumps({"stage": "collect"}))
                return _artifact_dir(output_dir)

            with (
                patch.object(protein_evidence_workflow, "stage_protein_fastas", wrapped_stage),
                patch.object(protein_evidence_workflow, "chunk_protein_fastas", wrapped_chunk),
                patch.object(protein_evidence_workflow, "exonerate_align_chunk", wrapped_align),
                patch.object(protein_evidence_workflow, "exonerate_to_evm_gff3", wrapped_convert),
                patch.object(protein_evidence_workflow, "exonerate_concat_results", wrapped_collect_results),
            ):
                result = protein_evidence_alignment(
                    genome=_artifact_file(GENOME_FASTA),
                    protein_fastas=[_artifact_file(PROTEIN_FASTA)],
                    proteins_per_chunk=20,
                    exonerate_sif="",
                    exonerate_model="protein2genome",
                )

            result_dir = Path(result.download_sync())
            self.assertTrue(result_dir.exists())
            expected_calls = ["stage", "chunk"]
            for chunk_label in expected_chunk_labels:
                expected_calls.append(f"align:{chunk_label}")
                expected_calls.append(f"convert:{chunk_label}")
            expected_calls.append("collect")
            self.assertEqual(calls, expected_calls)
