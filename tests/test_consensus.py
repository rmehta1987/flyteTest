"""Tests for the consensus-stage pre-EVM and EVM execution boundaries.

The suite keeps deterministic staging, partitioning, command assembly, and
result collection synthetic so Milestone 2 can be validated without requiring
installed EVM utilities.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"
DATA_DIR = TESTS_DIR.parent / "data"
GENOME_FASTA = DATA_DIR / "genome.fa"
RNASEQ_BAM = DATA_DIR / "RNAseq.bam"
PROTEIN_FASTA = DATA_DIR / "proteins.fa"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flyte.io import Dir

from flytetest.tasks import consensus
import flytetest.workflows.consensus as consensus_workflow
from flytetest.workflows.consensus import consensus_annotation_evm, consensus_annotation_evm_prep


def _artifact_dir(path: Path) -> Dir:
    """Create a stub Flyte directory artifact from a local path."""
    return Dir.from_local_sync(str(path))


def _read_json(path: Path) -> dict[str, object]:
    """Read a manifest file into a dictionary for assertions."""
    return json.loads(path.read_text())


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


def _write_gff3(path: Path, records: list[str]) -> Path:
    """Write a minimal GFF3 file with a canonical header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("##gff-version 3\n" + "\n".join(records) + "\n")
    return path


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    """Write a JSON payload with indentation for readability in failures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _create_pasa_results(tmp_path: Path) -> Path:
    """Create a minimal PASA results bundle that exposes a PASA assemblies GFF3."""
    results_dir = tmp_path / "pasa_results"
    pasa_dir = results_dir / "pasa"
    config_dir = results_dir / "config"
    pasa_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    assemblies_gff3 = _write_gff3(
        pasa_dir / "test.sqlite.pasa_assemblies.gff3",
        ["chr1\tPASA\ttranscript\t1\t20\t.\t+\t.\tID=pasa_tx1"],
    )
    (config_dir / "test.sqlite").write_text("")
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "pasa_transcript_alignment",
            "outputs": {
                "pasa_assemblies_gff3": str(assemblies_gff3),
            },
        },
    )
    return results_dir


def _create_transdecoder_results(tmp_path: Path) -> Path:
    """Create a minimal TransDecoder results bundle with a genome-coordinate GFF3."""
    results_dir = tmp_path / "transdecoder_results"
    transdecoder_dir = results_dir / "transdecoder"
    transdecoder_dir.mkdir(parents=True, exist_ok=True)

    transcript_fasta = transdecoder_dir / "test.sqlite.assemblies.fasta"
    transcript_fasta.write_text(">tx1\nATGGCC\n")
    genome_gff3 = _write_gff3(
        transdecoder_dir / f"{transcript_fasta.name}.transdecoder.genome.gff3",
        ["chr1\tTransDecoder\tCDS\t25\t40\t.\t+\t0\tID=td_orf1"],
    )
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "transdecoder_from_pasa",
            "outputs": {
                "input_transcripts_fasta": str(transcript_fasta),
                "transdecoder_genome_gff3": str(genome_gff3),
            },
        },
    )
    return results_dir


def _create_protein_results(tmp_path: Path, source_protein_fasta: Path | None = None) -> Path:
    """Create a minimal protein-evidence results bundle with a concatenated GFF3."""
    results_dir = tmp_path / "protein_results"
    results_dir.mkdir(parents=True, exist_ok=True)

    protein_gff3 = _write_gff3(
        results_dir / "protein_evidence.evm.gff3",
        ["chr1\texonerate_protein\tgene\t50\t80\t.\t+\t.\tID=protein_hit1"],
    )
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "protein_evidence_alignment",
            "outputs": {
                "concatenated_evm_protein_gff3": str(protein_gff3),
            },
            "inputs": {
                "source_protein_fasta": str(source_protein_fasta) if source_protein_fasta else None,
            },
        },
    )
    return results_dir


def _create_braker_results(
    tmp_path: Path,
    genome_source: Path | None = None,
    rnaseq_bam_path: Path | None = None,
    protein_fasta_path: Path | None = None,
    source_records: list[str] | None = None,
) -> Path:
    """Create a minimal BRAKER3 results bundle with staged genome and normalized GFF3."""
    results_dir = tmp_path / "braker_results"
    staged_genome_dir = results_dir / "staged_inputs" / "genome"
    normalized_dir = results_dir / "braker3_normalized"
    staged_genome_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    genome_path = staged_genome_dir / "genome.fa"
    if genome_source is None:
        genome_path.write_text(">chr1\nACGTACGTACGT\n")
    else:
        shutil.copy2(genome_source, genome_path)

    if source_records is None:
        source_records = ["chr1\tAugustus\tgene\t5\t18\t.\t+\t.\tID=braker_gene1"]
    source_fields = []
    for record in source_records:
        source_name = record.split("\t")[1]
        if source_name not in source_fields:
            source_fields.append(source_name)

    normalized_gff3 = _write_gff3(
        normalized_dir / "braker3.evm.gff3",
        source_records,
    )
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "ab_initio_annotation_braker3",
            "notes_backed_behavior": ["`braker.gff3` is the notes-backed EVM input boundary."],
            "tutorial_backed_behavior": ["The Galaxy tutorial defines the runtime model for this BRAKER bundle."],
            "repo_policy": ["Normalization preserves upstream BRAKER source-column values."],
            "outputs": {
                "normalized_braker_gff3": str(normalized_gff3),
                "normalized_source_fields": source_fields,
            },
            "inputs": {
                "rnaseq_bam_path": str(rnaseq_bam_path) if rnaseq_bam_path else None,
                "protein_fasta_path": str(protein_fasta_path) if protein_fasta_path else None,
            },
        },
    )
    return results_dir


def _create_pre_evm_results(tmp_path: Path) -> Path:
    """Create the corrected Milestone 1 pre-EVM bundle used by Milestone 2."""
    results_dir = tmp_path / "evm_prep_results"
    reference_dir = results_dir / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)

    transcripts_gff3 = _write_gff3(
        results_dir / "transcripts.gff3",
        ["chr1\tPASA\ttranscript\t1\t20\t.\t+\t.\tID=pasa_tx1"],
    )
    predictions_gff3 = _write_gff3(
        results_dir / "predictions.gff3",
        [
            "chr1\tAugustus\tgene\t5\t18\t.\t+\t.\tID=braker_gene1",
            "chr1\tTransDecoder\tCDS\t25\t40\t.\t+\t0\tID=td_orf1",
        ],
    )
    proteins_gff3 = _write_gff3(
        results_dir / "proteins.gff3",
        ["chr1\texonerate_protein\tgene\t50\t80\t.\t+\t.\tID=protein_hit1"],
    )
    genome_fasta = reference_dir / "genome.fa"
    genome_fasta.write_text(">chr1\nACGTACGTACGT\n")
    _write_json(
        results_dir / "run_manifest.json",
        {
            "workflow": "consensus_annotation_evm_prep",
            "outputs": {
                "reference_genome_fasta": str(genome_fasta),
                "transcripts_gff3": str(transcripts_gff3),
                "predictions_gff3": str(predictions_gff3),
                "proteins_gff3": str(proteins_gff3),
            },
            "pre_evm_contract": {
                "reference_genome_fasta": {"path": str(genome_fasta)},
                "transcripts.gff3": {"path": str(transcripts_gff3)},
                "predictions.gff3": {"path": str(predictions_gff3)},
                "proteins.gff3": {"path": str(proteins_gff3)},
            },
        },
    )
    return results_dir


def _create_partitioned_workspace(tmp_path: Path) -> Path:
    """Create a minimal partitioned EVM workspace for command-generation tests."""
    workspace_dir = tmp_path / "partitioned_workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "genome.fa").write_text(">chr1\nACGTACGT\n")
    _write_gff3(workspace_dir / "transcripts.gff3", ["chr1\tPASA\ttranscript\t1\t20\t.\t+\t.\tID=tx1"])
    _write_gff3(
        workspace_dir / "predictions.gff3",
        ["chr1\tAugustus\tgene\t1\t20\t.\t+\t.\tID=gene1"],
    )
    _write_gff3(
        workspace_dir / "proteins.gff3",
        ["chr1\texonerate_protein\tgene\t1\t20\t.\t+\t.\tID=prot1"],
    )
    (workspace_dir / "evm.weights").write_text("ABINITIO_PREDICTION\tAugustus\t3\n")
    (workspace_dir / "Partitions").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "partitions_list.out").write_text("chr1\tPartitions/part001\tN\n")
    _write_json(
        workspace_dir / "run_manifest.json",
        {
            "stage": "evm_partition_inputs",
            "inputs": {
                "evm_segment_size": 3000000,
                "evm_overlap_size": 300000,
            },
            "outputs": {
                "partitions_dir": str(workspace_dir / "Partitions"),
                "partition_listing": str(workspace_dir / "partitions_list.out"),
            },
        },
    )
    return workspace_dir


def _create_commands_workspace(tmp_path: Path, commands: list[str]) -> Path:
    """Create a minimal EVM command workspace with one commands.list file."""
    workspace_dir = _create_partitioned_workspace(tmp_path)
    (workspace_dir / "commands.list").write_text("\n".join(commands) + "\n")
    _write_json(
        workspace_dir / "run_manifest.json",
        {
            "stage": "evm_write_commands",
            "inputs": {
                "evm_output_file_name": "evm.out",
            },
            "command_count": len(commands),
            "outputs": {
                "commands_path": str(workspace_dir / "commands.list"),
            },
        },
    )
    return workspace_dir


class ConsensusPrepTaskTests(TestCase):
    """Task-level coverage for the pre-EVM file assembly boundary."""

    def test_prepare_evm_transcript_inputs_copies_pasa_assemblies_to_transcripts_gff3(self) -> None:
        """Stage PASA assemblies GFF3 under the corrected pre-EVM transcript filename."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_pasa_results(tmp_path)

            prepared = consensus.prepare_evm_transcript_inputs(
                pasa_results=_artifact_dir(pasa_results),
            )

            prepared_dir = Path(prepared.download_sync())
            manifest = _read_json(prepared_dir / "run_manifest.json")

            self.assertEqual((prepared_dir / "transcripts.gff3").read_text().splitlines()[-1], "chr1\tPASA\ttranscript\t1\t20\t.\t+\t.\tID=pasa_tx1")
            self.assertEqual(Path(manifest["outputs"]["transcripts_gff3"]).name, "transcripts.gff3")

    def test_prepare_evm_prediction_inputs_concatenates_braker_and_transdecoder(self) -> None:
        """Assemble predictions.gff3 in the required BRAKER-first then TransDecoder order."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            transdecoder_results = _create_transdecoder_results(tmp_path)
            braker_results = _create_braker_results(tmp_path)

            prepared = consensus.prepare_evm_prediction_inputs(
                transdecoder_results=_artifact_dir(transdecoder_results),
                braker3_results=_artifact_dir(braker_results),
            )

            prepared_dir = Path(prepared.download_sync())
            manifest = _read_json(prepared_dir / "run_manifest.json")
            self.assertEqual(
                (prepared_dir / "predictions.gff3").read_text().splitlines(),
                [
                    "##gff-version 3",
                    "chr1\tAugustus\tgene\t5\t18\t.\t+\t.\tID=braker_gene1",
                    "chr1\tTransDecoder\tCDS\t25\t40\t.\t+\t0\tID=td_orf1",
                ],
            )
            self.assertEqual(
                [Path(path).name for path in manifest["component_order"]],
                ["braker.gff3", "test.sqlite.assemblies.fasta.transdecoder.genome.gff3"],
            )
            self.assertEqual(manifest["evm_source_fields"], ["Augustus", "TransDecoder"])
            self.assertIn("repo_policy", manifest)

    def test_prepare_evm_protein_inputs_copies_exonerate_gff3_to_proteins_gff3(self) -> None:
        """Stage the downstream-ready protein evidence under the corrected filename."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            protein_results = _create_protein_results(tmp_path)

            prepared = consensus.prepare_evm_protein_inputs(
                protein_evidence_results=_artifact_dir(protein_results),
            )

            prepared_dir = Path(prepared.download_sync())
            manifest = _read_json(prepared_dir / "run_manifest.json")

            self.assertEqual((prepared_dir / "proteins.gff3").read_text().splitlines()[-1], "chr1\texonerate_protein\tgene\t50\t80\t.\t+\t.\tID=protein_hit1")
            self.assertEqual(Path(manifest["outputs"]["proteins_gff3"]).name, "proteins.gff3")

    def test_consensus_annotation_evm_prep_materializes_root_level_contract_files(self) -> None:
        """Collect the corrected `transcripts.gff3`, `predictions.gff3`, and `proteins.gff3` files."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_pasa_results(tmp_path)
            transdecoder_results = _create_transdecoder_results(tmp_path)
            protein_results = _create_protein_results(tmp_path)
            braker_results = _create_braker_results(tmp_path)

            with patch.object(consensus, "datetime", _fixed_datetime()):
                results = consensus_annotation_evm_prep(
                    pasa_results=_artifact_dir(pasa_results),
                    transdecoder_results=_artifact_dir(transdecoder_results),
                    protein_evidence_results=_artifact_dir(protein_results),
                    braker3_results=_artifact_dir(braker_results),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "transcripts.gff3").exists())
            self.assertTrue((results_dir / "predictions.gff3").exists())
            self.assertTrue((results_dir / "proteins.gff3").exists())
            self.assertTrue((results_dir / "reference" / "genome.fa").exists())
            self.assertEqual(
                sorted(path.name for path in (results_dir / "source_manifests").glob("*.json")),
                [
                    "braker3.run_manifest.json",
                    "pasa.run_manifest.json",
                    "protein_evidence.run_manifest.json",
                    "transdecoder.run_manifest.json",
                ],
            )
            self.assertEqual(
                sorted(manifest["outputs"].keys()),
                [
                    "predictions_gff3",
                    "prepared_inputs_dir",
                    "proteins_gff3",
                    "reference_dir",
                    "reference_genome_fasta",
                    "transcripts_gff3",
                ],
            )
            self.assertEqual(
                manifest["pre_evm_contract"]["transcripts.gff3"]["source_fields"],
                ["PASA"],
            )
            self.assertEqual(
                manifest["pre_evm_contract"]["predictions.gff3"]["source_fields"],
                ["Augustus", "TransDecoder"],
            )
            self.assertEqual(
                manifest["pre_evm_contract"]["proteins.gff3"]["source_fields"],
                ["exonerate_protein"],
            )
            self.assertIn("notes_backed_behavior", manifest)
            self.assertIn("tutorial_backed_behavior", manifest)
            self.assertIn("repo_policy", manifest)

    def test_consensus_annotation_evm_prep_preserves_fixture_rooted_provenance(self) -> None:
        """Keep local tutorial fixture paths visible when the pre-EVM bundle is assembled."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pasa_results = _create_pasa_results(tmp_path)
            transdecoder_results = _create_transdecoder_results(tmp_path)
            protein_results = _create_protein_results(tmp_path, source_protein_fasta=PROTEIN_FASTA)
            braker_results = _create_braker_results(
                tmp_path,
                genome_source=GENOME_FASTA,
                rnaseq_bam_path=RNASEQ_BAM,
                protein_fasta_path=PROTEIN_FASTA,
            )

            with patch.object(consensus, "datetime", _fixed_datetime()):
                results = consensus_annotation_evm_prep(
                    pasa_results=_artifact_dir(pasa_results),
                    transdecoder_results=_artifact_dir(transdecoder_results),
                    protein_evidence_results=_artifact_dir(protein_results),
                    braker3_results=_artifact_dir(braker_results),
                )

            results_dir = Path(results.download_sync())
            copied_braker_manifest = _read_json(results_dir / "source_manifests" / "braker3.run_manifest.json")
            copied_protein_manifest = _read_json(results_dir / "source_manifests" / "protein_evidence.run_manifest.json")

            self.assertEqual((results_dir / "reference" / "genome.fa").read_text(), GENOME_FASTA.read_text())
            self.assertEqual(copied_braker_manifest["inputs"]["rnaseq_bam_path"], str(RNASEQ_BAM))
            self.assertEqual(copied_braker_manifest["inputs"]["protein_fasta_path"], str(PROTEIN_FASTA))
            self.assertEqual(copied_protein_manifest["inputs"]["source_protein_fasta"], str(PROTEIN_FASTA))


class ConsensusEvmTaskTests(TestCase):
    """Task-level coverage for the Milestone 2 downstream EVM execution boundary."""

    def test_prepare_evm_execution_inputs_infers_repo_local_weights_from_prep_bundle(self) -> None:
        """Infer a deterministic repo-local weights file from the staged source columns."""
        with tempfile.TemporaryDirectory() as tmp:
            prep_results = _create_pre_evm_results(Path(tmp))

            prepared = consensus.prepare_evm_execution_inputs(
                evm_prep_results=_artifact_dir(prep_results),
            )

            prepared_dir = Path(prepared.download_sync())
            manifest = _read_json(prepared_dir / "run_manifest.json")

            self.assertEqual(
                (prepared_dir / "evm.weights").read_text().splitlines(),
                [
                    "ABINITIO_PREDICTION\tAugustus\t3",
                    "PROTEIN\texonerate_protein\t5",
                    "TRANSCRIPT\tPASA\t10",
                    "OTHER_PREDICTION\tTransDecoder\t5",
                ],
            )
            self.assertEqual(Path(manifest["outputs"]["transcripts_gff3"]).name, "transcripts.gff3")
            self.assertTrue(manifest["inputs"]["evm_prep_results"].endswith("evm_prep_results"))
            self.assertIn("repo_policy", manifest)

    def test_evm_partition_inputs_runs_note_faithful_partition_command_deterministically(self) -> None:
        """Use the note-backed partition flags and preserve a stable partition listing."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prep_results = _create_pre_evm_results(tmp_path)
            execution_inputs = consensus.prepare_evm_execution_inputs(
                evm_prep_results=_artifact_dir(prep_results),
            )
            captured_cmds: list[list[str]] = []

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                self.assertIsNone(stdout_path)
                self.assertIsNotNone(cwd)
                captured_cmds.append(cmd)
                (cwd / "Partitions" / "part001").mkdir(parents=True, exist_ok=True)
                (cwd / "partitions_list.out").write_text("chr1\tPartitions/part001\tN\n")

            with patch.object(consensus, "run_tool", side_effect=fake_run_tool):
                partitioned = consensus.evm_partition_inputs(
                    evm_execution_inputs=execution_inputs,
                )

            partitioned_dir = Path(partitioned.download_sync())
            manifest = _read_json(partitioned_dir / "run_manifest.json")

            self.assertEqual(captured_cmds[0][:2], ["perl", "partition_EVM_inputs.pl"])
            self.assertIn("--segmentSize", captured_cmds[0])
            self.assertIn("--overlapSize", captured_cmds[0])
            self.assertEqual(manifest["partition_entries"], ["chr1\tPartitions/part001\tN"])
            self.assertTrue((partitioned_dir / "Partitions" / "part001").exists())

    def test_evm_write_commands_normalizes_commands_and_tracks_count(self) -> None:
        """Keep one non-empty EVM command per line while preserving file order."""
        with tempfile.TemporaryDirectory() as tmp:
            partitioned_workspace = _create_partitioned_workspace(Path(tmp))

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                self.assertEqual(cmd[:2], ["perl", "write_EVM_commands.pl"])
                self.assertIsNotNone(stdout_path)
                stdout_path.write_text("  perl run_part2  \n\nperl run_part1\n")

            with patch.object(consensus, "run_tool", side_effect=fake_run_tool):
                commands = consensus.evm_write_commands(
                    partitioned_evm_inputs=_artifact_dir(partitioned_workspace),
                )

            commands_dir = Path(commands.download_sync())
            manifest = _read_json(commands_dir / "run_manifest.json")
            self.assertEqual((commands_dir / "commands.list").read_text().splitlines(), ["perl run_part2", "perl run_part1"])
            self.assertEqual(manifest["command_count"], 2)

    def test_evm_execute_commands_runs_in_file_order(self) -> None:
        """Execute generated EVM commands sequentially in the order listed on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            commands_workspace = _create_commands_workspace(
                Path(tmp),
                ["perl do_first", "perl do_second"],
            )
            executed_commands: list[str] = []

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                executed_commands.append(cmd[2])
                if stdout_path is not None:
                    stdout_path.write_text(f"ran {cmd[2]}\n")

            with patch.object(consensus, "run_tool", side_effect=fake_run_tool):
                executed = consensus.evm_execute_commands(
                    evm_commands=_artifact_dir(commands_workspace),
                )

            executed_dir = Path(executed.download_sync())
            manifest = _read_json(executed_dir / "run_manifest.json")

            self.assertEqual(executed_commands, ["perl do_first", "perl do_second"])
            self.assertEqual([entry["command"] for entry in manifest["executed_commands"]], executed_commands)
            self.assertTrue((executed_dir / "execution_logs" / "command_0001.stdout.txt").exists())

    def test_evm_recombine_outputs_emits_stable_final_gff3_files(self) -> None:
        """Materialize deterministic final GFF3 filenames from synthetic partition outputs."""
        with tempfile.TemporaryDirectory() as tmp:
            executed_workspace = _create_commands_workspace(Path(tmp), ["perl do_first"])
            _write_json(
                executed_workspace / "run_manifest.json",
                {
                    "stage": "evm_execute_commands",
                    "executed_commands": [{"index": 1, "command": "perl do_first"}],
                    "outputs": {
                        "commands_path": str(executed_workspace / "commands.list"),
                    },
                },
            )

            def fake_run_tool(
                cmd: list[str],
                sif: str,
                bind_paths: list[Path],
                cwd: Path | None = None,
                stdout_path: Path | None = None,
            ) -> None:
                self.assertIsNotNone(cwd)
                if cmd[1] == "convert_EVM_outputs_to_GFF3.pl":
                    _write_gff3(
                        cwd / "Partitions" / "part002" / "evm.out.gff3",
                        ["chr1\tEVM\tgene\t30\t40\t.\t+\t.\tID=evm_gene2"],
                    )
                    _write_gff3(
                        cwd / "Partitions" / "part001" / "evm.out.gff3",
                        ["chr1\tEVM\tgene\t10\t20\t.\t+\t.\tID=evm_gene1"],
                    )
                if cmd[1] == "gff3sort.pl" and stdout_path is not None:
                    stdout_path.write_text(Path(cmd[-1]).read_text())

            with patch.object(consensus, "run_tool", side_effect=fake_run_tool):
                recombined = consensus.evm_recombine_outputs(
                    executed_evm_commands=_artifact_dir(executed_workspace),
                )

            recombined_dir = Path(recombined.download_sync())
            manifest = _read_json(recombined_dir / "run_manifest.json")

            self.assertTrue((recombined_dir / "EVM.all.gff3").exists())
            self.assertTrue((recombined_dir / "EVM.all.removed.gff3").exists())
            self.assertTrue((recombined_dir / "EVM.all.sort.gff3").exists())
            self.assertEqual(
                [Path(path).as_posix().split("/")[-3:] for path in manifest["converted_partition_gff3s"]],
                [
                    ["Partitions", "part001", "evm.out.gff3"],
                    ["Partitions", "part002", "evm.out.gff3"],
                ],
            )

    def test_collect_evm_results_copies_final_outputs_and_stage_manifests(self) -> None:
        """Collect the deterministic EVM boundary into one manifest-bearing results bundle."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prep_results = _create_pre_evm_results(tmp_path)
            execution_inputs = consensus.prepare_evm_execution_inputs(
                evm_prep_results=_artifact_dir(prep_results),
            )
            partitioned_workspace = _create_partitioned_workspace(tmp_path / "partitioned_case")
            commands_workspace = _create_commands_workspace(tmp_path / "commands_case", ["perl do_first"])

            executed_workspace = tmp_path / "executed_workspace"
            shutil.copytree(commands_workspace, executed_workspace)
            (executed_workspace / "execution_logs").mkdir(parents=True, exist_ok=True)
            (executed_workspace / "execution_logs" / "command_0001.stdout.txt").write_text("ran perl do_first\n")
            _write_json(
                executed_workspace / "run_manifest.json",
                {
                    "stage": "evm_execute_commands",
                    "executed_commands": [{"index": 1, "command": "perl do_first"}],
                    "outputs": {
                        "execution_logs_dir": str(executed_workspace / "execution_logs"),
                        "commands_path": str(executed_workspace / "commands.list"),
                    },
                },
            )

            recombined_workspace = tmp_path / "recombined_workspace"
            shutil.copytree(executed_workspace, recombined_workspace)
            _write_gff3(
                recombined_workspace / "EVM.all.gff3",
                [
                    "chr1\tEVM\tgene\t10\t20\t.\t+\t.\tID=evm_gene1",
                    "chr1\tEVM\tgene\t30\t40\t.\t+\t.\tID=evm_gene2",
                ],
            )
            _write_gff3(
                recombined_workspace / "EVM.all.removed.gff3",
                [
                    "chr1\tEVM\tgene\t10\t20\t.\t+\t.\tID=evm_gene1",
                    "chr1\tEVM\tgene\t30\t40\t.\t+\t.\tID=evm_gene2",
                ],
            )
            _write_gff3(
                recombined_workspace / "EVM.all.sort.gff3",
                [
                    "chr1\tEVM\tgene\t10\t20\t.\t+\t.\tID=evm_gene1",
                    "chr1\tEVM\tgene\t30\t40\t.\t+\t.\tID=evm_gene2",
                ],
            )
            _write_json(
                recombined_workspace / "run_manifest.json",
                {
                    "stage": "evm_recombine_outputs",
                    "converted_partition_gff3s": [],
                    "outputs": {
                        "concatenated_gff3": str(recombined_workspace / "EVM.all.gff3"),
                        "blank_lines_removed_gff3": str(recombined_workspace / "EVM.all.removed.gff3"),
                        "sorted_gff3": str(recombined_workspace / "EVM.all.sort.gff3"),
                    },
                },
            )

            with patch.object(consensus, "datetime", _fixed_datetime()):
                results = consensus.collect_evm_results(
                    evm_prep_results=_artifact_dir(prep_results),
                    evm_execution_inputs=execution_inputs,
                    partitioned_evm_inputs=_artifact_dir(partitioned_workspace),
                    evm_commands=_artifact_dir(commands_workspace),
                    executed_evm_commands=_artifact_dir(executed_workspace),
                    recombined_evm_outputs=_artifact_dir(recombined_workspace),
                )

            results_dir = Path(results.download_sync())
            manifest = _read_json(results_dir / "run_manifest.json")

            self.assertTrue((results_dir / "EVM.all.gff3").exists())
            self.assertTrue((results_dir / "EVM.all.removed.gff3").exists())
            self.assertTrue((results_dir / "EVM.all.sort.gff3").exists())
            self.assertEqual(
                manifest["stage_manifests"]["evm_execution_inputs"]["discovered_sources"]["predictions"],
                ["Augustus", "TransDecoder"],
            )
            self.assertEqual(
                sorted(manifest["copied_stage_dirs"].keys()),
                [
                    "evm_commands",
                    "evm_executed",
                    "evm_execution_inputs",
                    "evm_partitioned",
                    "evm_recombined",
                    "pre_evm_bundle",
                ],
            )


class ConsensusEvmWorkflowTests(TestCase):
    """Workflow-level coverage for the Milestone 2 EVM entrypoint contract."""

    def test_consensus_annotation_evm_consumes_existing_prep_bundle_only(self) -> None:
        """Use the pre-EVM bundle as the sole upstream workflow input."""
        with tempfile.TemporaryDirectory() as tmp:
            prep_results = _create_pre_evm_results(Path(tmp))
            calls: list[tuple[str, tuple[str, ...]]] = []

            def fake_prepare(*, evm_prep_results: Dir, evm_weights_text: str = "") -> Dir:
                calls.append(("prepare", tuple(sorted(["evm_prep_results", "evm_weights_text"]))))
                return _artifact_dir(Path(tmp) / "prepared")

            def fake_partition(**kwargs: object) -> Dir:
                calls.append(("partition", tuple(sorted(kwargs.keys()))))
                return _artifact_dir(Path(tmp) / "partitioned")

            def fake_write(**kwargs: object) -> Dir:
                calls.append(("write", tuple(sorted(kwargs.keys()))))
                return _artifact_dir(Path(tmp) / "commands")

            def fake_execute(**kwargs: object) -> Dir:
                calls.append(("execute", tuple(sorted(kwargs.keys()))))
                return _artifact_dir(Path(tmp) / "executed")

            def fake_recombine(**kwargs: object) -> Dir:
                calls.append(("recombine", tuple(sorted(kwargs.keys()))))
                return _artifact_dir(Path(tmp) / "recombined")

            def fake_collect(**kwargs: object) -> Dir:
                calls.append(("collect", tuple(sorted(kwargs.keys()))))
                return _artifact_dir(Path(tmp) / "results")

            for name in ("prepared", "partitioned", "commands", "executed", "recombined", "results"):
                (Path(tmp) / name).mkdir(parents=True, exist_ok=True)

            with (
                patch.object(consensus_workflow, "prepare_evm_execution_inputs", side_effect=fake_prepare),
                patch.object(consensus_workflow, "evm_partition_inputs", side_effect=fake_partition),
                patch.object(consensus_workflow, "evm_write_commands", side_effect=fake_write),
                patch.object(consensus_workflow, "evm_execute_commands", side_effect=fake_execute),
                patch.object(consensus_workflow, "evm_recombine_outputs", side_effect=fake_recombine),
                patch.object(consensus_workflow, "collect_evm_results", side_effect=fake_collect),
            ):
                consensus_annotation_evm(
                    evm_prep_results=_artifact_dir(prep_results),
                )

            self.assertEqual(calls[0], ("prepare", ("evm_prep_results", "evm_weights_text")))
            self.assertEqual(calls[-1][0], "collect")
            self.assertNotIn("pasa_results", {key for _, keys in calls for key in keys})
            self.assertNotIn("transdecoder_results", {key for _, keys in calls for key in keys})
