"""Protein-evidence task implementations for FLyteTest.

This module stages local protein FASTAs, chunks them deterministically, runs
Exonerate alignments, converts outputs for later EVM use, and collects results.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from flyte.io import Dir, File

from flytetest.config import (
    PROTEIN_EVIDENCE_RESULTS_PREFIX,
    PROTEIN_EVIDENCE_WORKFLOW_NAME,
    RESULTS_ROOT,
    protein_evidence_env,
    require_path,
    run_tool,
)
from flytetest.types import (
    ChunkedProteinFastaAsset,
    EvmProteinEvidenceGff3Asset,
    ExonerateChunkAlignmentResult,
    ProteinEvidenceResultBundle,
    ProteinReferenceDatasetAsset,
    ReferenceGenome,
)


def _as_json_compatible(value: Any) -> Any:
    """Recursively convert manifest values into JSON-serializable primitives."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _as_json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_as_json_compatible(item) for item in value]
    if isinstance(value, list):
        return [_as_json_compatible(item) for item in value]
    return value


def _iter_fasta_records(path: Path) -> Iterator[tuple[str, list[str]]]:
    """Yield FASTA headers and sequence lines from a staged protein FASTA."""
    header: str | None = None
    sequence_lines: list[str] = []
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if line.startswith(">"):
                if header is not None:
                    yield header, sequence_lines
                header = line[1:].strip()
                sequence_lines = []
                continue
            if header is None and line.strip():
                raise ValueError(f"Invalid FASTA content in {path}: sequence content before first header.")
            if header is not None:
                sequence_lines.append(line)
    if header is not None:
        yield header, sequence_lines


def _write_fasta_record(handle: Any, header: str, sequence_lines: list[str]) -> None:
    """Write one FASTA record using the staged sequence-line layout."""
    handle.write(f">{header}\n")
    for line in sequence_lines:
        handle.write(f"{line}\n")


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON manifest into a dictionary."""
    return json.loads(path.read_text())


def _staged_inputs_dir(staged_dir: Path) -> Path:
    """Resolve the directory containing copied source protein FASTAs."""
    return require_path(staged_dir / "inputs", "Staged protein FASTA input directory")


def _staged_combined_fasta(staged_dir: Path) -> Path:
    """Resolve the combined staged protein FASTA used for chunking."""
    return require_path(staged_dir / "combined" / "proteins.all.fa", "Combined staged protein FASTA")


def _stage_manifest_path(staged_dir: Path) -> Path:
    """Resolve the manifest written by protein FASTA staging."""
    return require_path(staged_dir / "run_manifest.json", "Protein staging manifest")


def _chunk_subdir(chunk_dir: Path) -> Path:
    """Resolve the directory containing per-chunk protein FASTAs."""
    return require_path(chunk_dir / "chunks", "Protein chunk directory")


def _chunk_manifest_path(chunk_dir: Path) -> Path:
    """Resolve the manifest written by deterministic protein chunking."""
    return require_path(chunk_dir / "run_manifest.json", "Protein chunking manifest")


def _chunk_fasta_paths(chunk_dir: Path) -> tuple[Path, ...]:
    """Return all chunk FASTAs in deterministic filename order."""
    return tuple(sorted(_chunk_subdir(chunk_dir).glob("chunk_*.fa")))


def _raw_exonerate_output(alignment_dir: Path) -> Path:
    """Resolve the single raw Exonerate stdout file for one chunk."""
    candidates = sorted(alignment_dir.glob("*.exonerate.out"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single Exonerate raw output under {alignment_dir}")


def _alignment_manifest_path(alignment_dir: Path) -> Path:
    """Resolve the manifest written by an Exonerate chunk alignment."""
    return require_path(alignment_dir / "run_manifest.json", "Exonerate chunk manifest")


def _converted_evm_gff3(converted_dir: Path) -> Path:
    """Resolve the converted downstream-ready EVM GFF3 for one chunk."""
    candidates = sorted(converted_dir.glob("*.evm.gff3"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single converted EVM GFF3 under {converted_dir}")


def _converted_manifest_path(converted_dir: Path) -> Path:
    """Resolve the manifest written by Exonerate-to-EVM conversion."""
    return require_path(converted_dir / "run_manifest.json", "Converted Exonerate manifest")


@protein_evidence_env.task
def stage_protein_fastas(protein_fastas: list[File]) -> Dir:
    """Stage one or more local protein FASTAs and concatenate them deterministically."""
    if not protein_fastas:
        raise ValueError("stage_protein_fastas requires at least one protein FASTA input.")

    out_dir = Path(tempfile.mkdtemp(prefix="protein_stage_")) / "protein_stage"
    inputs_dir = out_dir / "inputs"
    combined_dir = out_dir / "combined"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    combined_dir.mkdir(parents=True, exist_ok=True)

    combined_fasta_path = combined_dir / "proteins.all.fa"
    source_paths: list[Path] = []
    staged_paths: list[Path] = []

    with combined_fasta_path.open("wb") as combined_handle:
        for index, protein_fasta in enumerate(protein_fastas, start=1):
            source_path = require_path(
                Path(protein_fasta.download_sync()),
                f"Protein FASTA input {index}",
            )
            staged_path = inputs_dir / f"{index:03d}_{source_path.name}"
            shutil.copy2(source_path, staged_path)
            source_paths.append(Path(str(protein_fasta.path)))
            staged_paths.append(staged_path)

            with source_path.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, combined_handle)
            combined_handle.write(b"\n")

    manifest = {
        "stage": "protein_fastas",
        "assumptions": [
            "This milestone accepts one or more local protein FASTA inputs and does not download UniProt or RefSeq automatically.",
            "Input FASTAs are staged and concatenated in the exact order provided to the workflow.",
            "No protein header rewriting or external preprocessing is performed in this milestone.",
        ],
        "outputs": {
            "inputs_dir": str(inputs_dir),
            "combined_fasta": str(combined_fasta_path),
        },
        "source_fasta_paths": [str(path) for path in source_paths],
        "staged_input_paths": [str(path) for path in staged_paths],
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))


@protein_evidence_env.task
def chunk_protein_fastas(
    staged_proteins: Dir,
    proteins_per_chunk: int = 500,
) -> Dir:
    """Split the staged combined protein FASTA into deterministic chunk FASTAs."""
    if proteins_per_chunk < 1:
        raise ValueError("proteins_per_chunk must be at least 1.")

    staged_dir = require_path(Path(staged_proteins.download_sync()), "Staged protein FASTA directory")
    combined_fasta_path = _staged_combined_fasta(staged_dir)

    out_dir = Path(tempfile.mkdtemp(prefix="protein_chunks_")) / "protein_chunks"
    chunks_dir = out_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    chunk_metadata: list[dict[str, Any]] = []
    current_records: list[tuple[str, list[str]]] = []
    total_proteins = 0
    chunk_index = 0

    def flush_chunk(records: list[tuple[str, list[str]]], next_index: int) -> None:
        if not records:
            return
        chunk_path = chunks_dir / f"chunk_{next_index:04d}.fa"
        with chunk_path.open("w") as handle:
            for header, sequence_lines in records:
                _write_fasta_record(handle, header, sequence_lines)
        chunk_metadata.append(
            {
                "chunk_index": next_index,
                "chunk_label": chunk_path.stem,
                "chunk_fasta": str(chunk_path),
                "protein_count": len(records),
            }
        )

    for header, sequence_lines in _iter_fasta_records(combined_fasta_path):
        total_proteins += 1
        current_records.append((header, sequence_lines))
        if len(current_records) == proteins_per_chunk:
            chunk_index += 1
            flush_chunk(current_records, chunk_index)
            current_records = []

    if current_records:
        chunk_index += 1
        flush_chunk(current_records, chunk_index)

    if total_proteins == 0:
        raise ValueError(f"No FASTA records were found in staged protein FASTA {combined_fasta_path}.")

    manifest = {
        "stage": "protein_chunking",
        "source_combined_fasta": str(combined_fasta_path),
        "proteins_per_chunk": proteins_per_chunk,
        "total_proteins": total_proteins,
        "chunk_count": len(chunk_metadata),
        "chunks": chunk_metadata,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))


@protein_evidence_env.task
def exonerate_align_chunk(
    genome: File,
    protein_chunk: File,
    exonerate_sif: str = "",
    exonerate_model: str = "protein2genome",
) -> Dir:
    """Run Exonerate for one staged protein chunk against the reference genome."""
    genome_path = require_path(Path(genome.download_sync()), "Reference genome FASTA")
    chunk_path = require_path(Path(protein_chunk.download_sync()), "Protein FASTA chunk")
    chunk_label = chunk_path.stem

    out_dir = Path(tempfile.mkdtemp(prefix=f"exonerate_{chunk_label}_")) / "alignment"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_output_path = out_dir / f"{chunk_label}.exonerate.out"

    run_tool(
        [
            "exonerate",
            "--model",
            exonerate_model,
            "--query",
            str(chunk_path),
            "--target",
            str(genome_path),
            "--showalignment",
            "no",
            "--showvulgar",
            "no",
            "--showquerygff",
            "no",
            "--showtargetgff",
            "yes",
        ],
        exonerate_sif,
        [genome_path.parent, chunk_path.parent, out_dir],
        stdout_path=raw_output_path,
    )

    manifest = {
        "stage": "exonerate_align_chunk",
        "chunk_label": chunk_label,
        "assumptions": [
            "This milestone uses Exonerate's protein2genome model by default because the notes describe protein evidence alignment against the genome but do not spell out the exact command-line flags.",
            "The raw output preserved here is Exonerate stdout with target GFF emission enabled for later deterministic conversion.",
        ],
        "outputs": {
            "raw_output": str(raw_output_path),
        },
        "inputs": {
            "genome": str(Path(str(genome.path))),
            "protein_chunk": str(Path(str(protein_chunk.path))),
            "model": exonerate_model,
        },
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))


@protein_evidence_env.task
def exonerate_to_evm_gff3(
    exonerate_alignment: Dir,
) -> Dir:
    """Convert one Exonerate chunk output into a later-EVM-ready protein GFF3."""
    alignment_dir = require_path(Path(exonerate_alignment.download_sync()), "Exonerate chunk alignment directory")
    raw_output_path = _raw_exonerate_output(alignment_dir)
    chunk_label = raw_output_path.name.removesuffix(".exonerate.out")

    out_dir = Path(tempfile.mkdtemp(prefix=f"exonerate_evm_{chunk_label}_")) / "evm"
    out_dir.mkdir(parents=True, exist_ok=True)
    gff3_path = out_dir / f"{chunk_label}.evm.gff3"

    gff_line_count = 0
    with raw_output_path.open() as source_handle, gff3_path.open("w") as out_handle:
        out_handle.write("##gff-version 3\n")
        for raw_line in source_handle:
            stripped = raw_line.rstrip("\n")
            fields = stripped.split("\t")
            # Exonerate stdout includes non-GFF status lines, so conversion only
            # keeps records that already match the expected 9-column structure.
            if len(fields) != 9:
                continue
            normalized_fields = [field.strip() for field in fields]
            normalized_fields[1] = "exonerate_protein"
            out_handle.write("\t".join(normalized_fields) + "\n")
            gff_line_count += 1

    if gff_line_count == 0:
        raise ValueError(
            f"No GFF lines were extracted from Exonerate output {raw_output_path}; cannot produce EVM-ready GFF3."
        )

    manifest = {
        "stage": "exonerate_to_evm_gff3",
        "chunk_label": chunk_label,
        "assumptions": [
            "This milestone treats Exonerate target-GFF records as the downstream-ready protein evidence representation for later EVM input.",
            "Conversion is limited to deterministic extraction of GFF-like records from Exonerate stdout plus source-column normalization; broader EVM preprocessing remains a later milestone.",
        ],
        "inputs": {
            "raw_exonerate_output": str(raw_output_path),
        },
        "outputs": {
            "evm_gff3": str(gff3_path),
        },
        "gff_line_count": gff_line_count,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))


@protein_evidence_env.task
def exonerate_concat_results(
    genome: File,
    staged_proteins: Dir,
    protein_chunks: Dir,
    raw_chunk_results: list[Dir],
    evm_chunk_results: list[Dir],
) -> Dir:
    """Collect staged, raw, and converted protein-evidence outputs into one bundle."""
    if not raw_chunk_results:
        raise ValueError("exonerate_concat_results requires at least one raw Exonerate chunk result.")
    if len(raw_chunk_results) != len(evm_chunk_results):
        raise ValueError("Raw Exonerate chunk results and converted EVM chunk results must have the same length.")

    genome_input = Path(str(genome.path))
    staged_dir = require_path(Path(staged_proteins.download_sync()), "Staged protein FASTA directory")
    chunk_dir = require_path(Path(protein_chunks.download_sync()), "Protein chunk directory")

    raw_alignment_paths = [
        require_path(Path(raw_chunk_result.download_sync()), "Exonerate chunk alignment directory")
        for raw_chunk_result in raw_chunk_results
    ]
    converted_paths = [
        require_path(Path(converted_chunk_result.download_sync()), "Converted Exonerate EVM directory")
        for converted_chunk_result in evm_chunk_results
    ]

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{PROTEIN_EVIDENCE_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_staged_dir = out_dir / "staged_proteins"
    copied_chunk_dir = out_dir / "protein_chunks"
    copied_raw_root = out_dir / "raw_exonerate_chunks"
    copied_evm_root = out_dir / "evm_protein_gff3_chunks"
    shutil.copytree(staged_dir, copied_staged_dir, dirs_exist_ok=True)
    shutil.copytree(chunk_dir, copied_chunk_dir, dirs_exist_ok=True)
    copied_raw_root.mkdir(parents=True, exist_ok=True)
    copied_evm_root.mkdir(parents=True, exist_ok=True)

    copied_raw_dirs: list[Path] = []
    for raw_alignment_path in sorted(raw_alignment_paths, key=lambda path: _raw_exonerate_output(path).name):
        raw_output_name = _raw_exonerate_output(raw_alignment_path).name
        chunk_label = raw_output_name.removesuffix(".exonerate.out")
        destination = copied_raw_root / chunk_label
        shutil.copytree(raw_alignment_path, destination, dirs_exist_ok=True)
        copied_raw_dirs.append(destination)

    copied_evm_dirs: list[Path] = []
    for converted_path in sorted(converted_paths, key=lambda path: _converted_evm_gff3(path).name):
        gff3_name = _converted_evm_gff3(converted_path).name
        chunk_label = gff3_name.removesuffix(".evm.gff3")
        destination = copied_evm_root / chunk_label
        shutil.copytree(converted_path, destination, dirs_exist_ok=True)
        copied_evm_dirs.append(destination)

    concatenated_raw_output_path = out_dir / "all_chunks.exonerate.out"
    with concatenated_raw_output_path.open("w") as out_handle:
        for index, copied_raw_dir in enumerate(copied_raw_dirs):
            raw_output_path = _raw_exonerate_output(copied_raw_dir)
            chunk_label = raw_output_path.name.removesuffix(".exonerate.out")
            if index:
                out_handle.write("\n")
            out_handle.write(f"# chunk={chunk_label}\n")
            raw_text = raw_output_path.read_text()
            out_handle.write(raw_text)
            if raw_text and not raw_text.endswith("\n"):
                out_handle.write("\n")

    concatenated_evm_gff3_path = out_dir / "protein_evidence.evm.gff3"
    with concatenated_evm_gff3_path.open("w") as out_handle:
        out_handle.write("##gff-version 3\n")
        for copied_evm_dir in copied_evm_dirs:
            for raw_line in _converted_evm_gff3(copied_evm_dir).read_text().splitlines():
                if not raw_line or raw_line == "##gff-version 3":
                    continue
                out_handle.write(raw_line + "\n")

    staged_manifest = _read_json(_stage_manifest_path(copied_staged_dir))
    chunk_manifest = _read_json(_chunk_manifest_path(copied_chunk_dir))
    combined_protein_fasta_path = _staged_combined_fasta(copied_staged_dir)

    reference_asset = ReferenceGenome(fasta_path=genome_input)
    staged_dataset_asset = ProteinReferenceDatasetAsset(
        staged_dir=copied_staged_dir,
        combined_fasta_path=combined_protein_fasta_path,
        source_fasta_paths=tuple(Path(path) for path in staged_manifest.get("source_fasta_paths", [])),
        staged_input_paths=tuple(Path(path) for path in staged_manifest.get("staged_input_paths", [])),
        notes=(
            "Protein FASTA inputs are staged locally and concatenated without additional preprocessing in this milestone.",
        ),
    )

    protein_counts = {
        str(entry["chunk_label"]): int(entry["protein_count"])
        for entry in chunk_manifest.get("chunks", [])
    }
    chunk_assets_by_label: dict[str, ChunkedProteinFastaAsset] = {}
    for chunk_index, chunk_path in enumerate(_chunk_fasta_paths(copied_chunk_dir), start=1):
        chunk_assets_by_label[chunk_path.stem] = ChunkedProteinFastaAsset(
            chunk_dir=copied_chunk_dir,
            chunk_fasta_path=chunk_path,
            chunk_index=chunk_index,
            protein_count=protein_counts.get(chunk_path.stem, 0),
            source_dataset=staged_dataset_asset,
            notes=(
                "Chunk ordering is deterministic and follows the staged combined FASTA order.",
            ),
        )

    raw_chunk_assets: list[ExonerateChunkAlignmentResult] = []
    for copied_raw_dir in copied_raw_dirs:
        raw_manifest = _read_json(_alignment_manifest_path(copied_raw_dir))
        raw_output_path = _raw_exonerate_output(copied_raw_dir)
        chunk_label = raw_output_path.name.removesuffix(".exonerate.out")
        raw_chunk_assets.append(
            ExonerateChunkAlignmentResult(
                chunk_label=chunk_label,
                output_dir=copied_raw_dir,
                protein_chunk_fasta_path=chunk_assets_by_label[chunk_label].chunk_fasta_path,
                raw_output_path=raw_output_path,
                model=str(raw_manifest.get("inputs", {}).get("model", "protein2genome")),
                source_chunk=chunk_assets_by_label.get(chunk_label),
                notes=(
                    "Raw Exonerate stdout is preserved separately from the downstream-ready converted GFF3.",
                ),
            )
        )

    converted_assets: list[EvmProteinEvidenceGff3Asset] = []
    for copied_evm_dir in copied_evm_dirs:
        converted_manifest = _read_json(_converted_manifest_path(copied_evm_dir))
        gff3_path = _converted_evm_gff3(copied_evm_dir)
        chunk_label = gff3_path.name.removesuffix(".evm.gff3")
        source_alignment = next(asset for asset in raw_chunk_assets if asset.chunk_label == chunk_label)
        converted_assets.append(
            EvmProteinEvidenceGff3Asset(
                chunk_label=chunk_label,
                gff3_path=gff3_path,
                source_alignment=source_alignment,
                notes=(
                    "Converted output is derived from Exonerate target-GFF records with deterministic source-column normalization.",
                    str(converted_manifest.get("assumptions", [""])[0]).strip(),
                ),
            )
        )

    result_bundle = ProteinEvidenceResultBundle(
        result_dir=out_dir,
        combined_protein_fasta_path=combined_protein_fasta_path,
        chunk_dir=copied_chunk_dir,
        raw_chunk_root=copied_raw_root,
        evm_chunk_root=copied_evm_root,
        concatenated_raw_output_path=concatenated_raw_output_path,
        concatenated_evm_gff3_path=concatenated_evm_gff3_path,
        reference_genome=reference_asset,
        staged_dataset=staged_dataset_asset,
        chunk_assets=tuple(chunk_assets_by_label[label] for label in sorted(chunk_assets_by_label)),
        raw_chunk_results=tuple(sorted(raw_chunk_assets, key=lambda asset: asset.chunk_label)),
        converted_chunk_results=tuple(sorted(converted_assets, key=lambda asset: asset.chunk_label)),
        notes=(
            "This milestone stops at local protein evidence staging, chunked Exonerate alignment, conversion to downstream-ready protein evidence GFF3, and deterministic result collection.",
        ),
    )

    manifest = {
        "workflow": PROTEIN_EVIDENCE_WORKFLOW_NAME,
        "assumptions": [
            "This milestone consumes one or more local protein FASTA inputs and does not fetch UniProt or RefSeq automatically.",
            "Protein FASTA chunking is deterministic and follows the staged combined FASTA order.",
            "Exonerate is run once per chunk and both raw stdout and converted downstream-ready protein evidence GFF3 outputs are preserved.",
            "Converted protein evidence currently reflects deterministic extraction of Exonerate target-GFF records for later EVM input rather than a full EVM preprocessing pipeline.",
            "This milestone does not yet implement BRAKER3, EVM, PASA update rounds, repeat filtering, BUSCO, EggNOG, AGAT, or submission preparation.",
        ],
        "outputs": {
            "staged_proteins_dir": str(copied_staged_dir),
            "combined_protein_fasta": str(combined_protein_fasta_path),
            "protein_chunks_dir": str(copied_chunk_dir),
            "raw_exonerate_chunks_dir": str(copied_raw_root),
            "evm_protein_gff3_chunks_dir": str(copied_evm_root),
            "concatenated_raw_exonerate": str(concatenated_raw_output_path),
            "concatenated_evm_protein_gff3": str(concatenated_evm_gff3_path),
        },
        "chunking": {
            "proteins_per_chunk": chunk_manifest.get("proteins_per_chunk"),
            "chunk_count": chunk_manifest.get("chunk_count"),
            "total_proteins": chunk_manifest.get("total_proteins"),
        },
        "assets": _as_json_compatible(
            {
                "reference_genome": asdict(reference_asset),
                "protein_reference_dataset": asdict(staged_dataset_asset),
                "chunked_proteins": [asdict(asset) for asset in result_bundle.chunk_assets],
                "raw_exonerate_chunk_results": [asdict(asset) for asset in result_bundle.raw_chunk_results],
                "evm_ready_protein_gff3_chunks": [asdict(asset) for asset in result_bundle.converted_chunk_results],
                "protein_evidence_result_bundle": asdict(result_bundle),
            }
        ),
        "raw_chunk_labels": [asset.chunk_label for asset in result_bundle.raw_chunk_results],
        "converted_chunk_labels": [asset.chunk_label for asset in result_bundle.converted_chunk_results],
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))
