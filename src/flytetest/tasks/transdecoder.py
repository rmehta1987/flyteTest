"""TransDecoder task implementations for FLyteTest.

The stage order follows `docs/braker3_evm_notes.md`, while the TransDecoder
command shapes and input/output expectations follow
`docs/tool_refs/transdecoder.md`. This module covers the PASA-derived
coding-prediction boundary: training/predicting on PASA assemblies, lifting ORFs
back to genome coordinates, and collecting the stable downstream-ready bundle.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir, File

from flytetest.config import (
    RESULTS_ROOT,
    TRANSDECODER_RESULTS_PREFIX,
    TRANSDECODER_WORKFLOW_NAME,
    project_mkdtemp,
    require_path,
    run_tool,
    transdecoder_env,
)
from flytetest.manifest import build_manifest_envelope, write_json as _write_json
from flytetest.tasks.pasa import _pasa_assemblies_fasta, _pasa_assemblies_gff3, _sqlite_db_path
from flytetest.types import CodingPredictionResult, PasaAlignmentAssemblyResult, TransDecoderPredictionResult


# Source of truth for the registry-manifest contract: every key this module writes under manifest["outputs"].
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "input_transcripts_fasta",
    "source_pasa_assemblies_fasta",
    "source_pasa_assemblies_gff3",
    "transdecoder_bed",
    "transdecoder_cds",
    "transdecoder_dir",
    "transdecoder_genome_gff3",
    "transdecoder_intermediate_dir",
    "transdecoder_mrna",
    "transdecoder_orfs_gff3",
    "transdecoder_pep",
)


def _as_json_compatible(value: Any) -> Any:
    """Convert nested manifest values into JSON-friendly primitives."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _as_json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_as_json_compatible(item) for item in value]
    if isinstance(value, list):
        return [_as_json_compatible(item) for item in value]
    return value


def _sample_id_from_pasa_results(results_dir: Path) -> str:
    """Read the sample identifier from a PASA results manifest when present."""
    manifest_path = results_dir / "run_manifest.json"
    if not manifest_path.exists():
        return "sample"
    manifest = json.loads(manifest_path.read_text())
    return str(manifest.get("sample_id", "sample"))


def _transdecoder_output(run_dir: Path, transcript_fasta_name: str, suffix: str) -> Path | None:
    """Resolve one optional TransDecoder output by its standard filename suffix."""
    candidate = run_dir / f"{transcript_fasta_name}{suffix}"
    if candidate.exists():
        return candidate
    return None


def _transdecoder_dir(run_dir: Path, transcript_fasta_name: str) -> Path | None:
    """Return the TransDecoder intermediate directory when the stage wrote one."""
    return _transdecoder_output(run_dir, transcript_fasta_name, ".transdecoder_dir")


def _transdecoder_gff3(run_dir: Path, transcript_fasta_name: str) -> Path | None:
    """Return the transcript-coordinate ORF GFF3 when the stage wrote one."""
    return _transdecoder_output(run_dir, transcript_fasta_name, ".transdecoder.gff3")


def _transdecoder_genome_gff3(run_dir: Path, transcript_fasta_name: str) -> Path | None:
    """Return the genome-coordinate ORF GFF3 when the stage wrote one."""
    return _transdecoder_output(run_dir, transcript_fasta_name, ".transdecoder.genome.gff3")


def _transdecoder_bed(run_dir: Path, transcript_fasta_name: str) -> Path | None:
    """Return the TransDecoder BED output when the stage wrote one."""
    return _transdecoder_output(run_dir, transcript_fasta_name, ".transdecoder.bed")


def _transdecoder_cds(run_dir: Path, transcript_fasta_name: str) -> Path | None:
    """Return the predicted CDS FASTA when the stage wrote one."""
    return _transdecoder_output(run_dir, transcript_fasta_name, ".transdecoder.cds")


def _transdecoder_pep(run_dir: Path, transcript_fasta_name: str) -> Path | None:
    """Return the predicted peptide FASTA when the stage wrote one."""
    return _transdecoder_output(run_dir, transcript_fasta_name, ".transdecoder.pep")


def _transdecoder_mrna(run_dir: Path, transcript_fasta_name: str) -> Path | None:
    """Return the predicted mRNA FASTA when the stage wrote one."""
    return _transdecoder_output(run_dir, transcript_fasta_name, ".transdecoder.mRNA")


@transdecoder_env.task
def transdecoder_train_from_pasa(
    pasa_assemblies_fasta: File,
    pasa_assemblies_gff3: File,
    transdecoder_sif: str = "",
    transdecoder_min_protein_length: int = 100,
    transdecoder_genome_orf_script: str = "cdna_alignment_orf_to_genome_orf.pl",
) -> Dir:
    """Run TransDecoder on PASA assemblies and lift ORFs back to genome coordinates.

    Args:
        pasa_assemblies_fasta: PASA assemblies FASTA produced at the transcript
            evidence to PASA boundary.
        pasa_assemblies_gff3: PASA assemblies GFF3 paired with the FASTA above.
        transdecoder_sif: Optional container image for the TransDecoder runtime.
        transdecoder_min_protein_length: Minimum ORF length passed to
            `TransDecoder.LongOrfs`.
        transdecoder_genome_orf_script: Genome-coordinate lift-over script used
            after TransDecoder prediction.

    Returns:
        Directory containing the staged TransDecoder run for the PASA assembly.
    """
    fasta_path = require_path(Path(pasa_assemblies_fasta.download_sync()), "PASA assemblies FASTA")
    gff3_path = require_path(Path(pasa_assemblies_gff3.download_sync()), "PASA assemblies GFF3")

    out_dir = project_mkdtemp("transdecoder_") / "transdecoder"
    out_dir.mkdir(parents=True, exist_ok=True)

    staged_fasta = out_dir / fasta_path.name
    staged_gff3 = out_dir / gff3_path.name
    shutil.copy2(fasta_path, staged_fasta)
    shutil.copy2(gff3_path, staged_gff3)

    bind_paths = [out_dir]
    run_tool(
        [
            "TransDecoder.LongOrfs",
            "-t",
            str(staged_fasta),
            "-m",
            str(transdecoder_min_protein_length),
        ],
        transdecoder_sif,
        bind_paths,
        cwd=out_dir,
    )
    run_tool(
        [
            "TransDecoder.Predict",
            "-t",
            str(staged_fasta),
        ],
        transdecoder_sif,
        bind_paths,
        cwd=out_dir,
    )

    predicted_orfs_gff3 = require_path(
        out_dir / f"{staged_fasta.name}.transdecoder.gff3",
        "TransDecoder ORF GFF3",
    )
    genome_gff3_path = out_dir / f"{staged_fasta.name}.transdecoder.genome.gff3"
    run_tool(
        [
            transdecoder_genome_orf_script,
            str(predicted_orfs_gff3),
            str(staged_gff3),
            str(staged_fasta),
        ],
        transdecoder_sif,
        bind_paths,
        cwd=out_dir,
        stdout_path=genome_gff3_path,
    )

    return Dir(path=str(out_dir))


@transdecoder_env.task
def collect_transdecoder_results(
    pasa_results: Dir,
    transdecoder_run: Dir,
    sample_id: str = "sample",
) -> Dir:
    """Collect PASA-derived TransDecoder outputs into a stable results bundle.

    Args:
        pasa_results: PASA results directory that supplies the source assemblies
            and config metadata.
        transdecoder_run: TransDecoder run directory to archive into the bundle.
        sample_id: Sample label written into the manifest and asset metadata.

    Returns:
        Manifest-bearing bundle for the PASA-derived TransDecoder predictions.
    """
    pasa_results_path = require_path(Path(pasa_results.download_sync()), "PASA results directory")
    transdecoder_run_path = require_path(Path(transdecoder_run.download_sync()), "TransDecoder output directory")

    pasa_dir = require_path(pasa_results_path / "pasa", "PASA output directory")
    config_dir = require_path(pasa_results_path / "config", "PASA config directory")
    database_name = _sqlite_db_path(config_dir).name
    pasa_assemblies_fasta = _pasa_assemblies_fasta(pasa_dir, database_name)
    pasa_assemblies_gff3 = _pasa_assemblies_gff3(pasa_dir, database_name)
    if pasa_assemblies_fasta is None:
        raise FileNotFoundError(
            f"PASA assemblies FASTA not found under {pasa_dir}; expected output from pasa_transcript_alignment."
        )
    if pasa_assemblies_gff3 is None:
        raise FileNotFoundError(
            f"PASA assemblies GFF3 not found under {pasa_dir}; expected output from pasa_transcript_alignment."
        )

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{TRANSDECODER_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_transdecoder_dir = out_dir / "transdecoder"
    shutil.copytree(transdecoder_run_path, copied_transdecoder_dir, dirs_exist_ok=True)

    source_pasa_asset = PasaAlignmentAssemblyResult(
        output_dir=pasa_dir,
        database_name=database_name,
        assemblies_fasta_path=pasa_assemblies_fasta,
        pasa_assemblies_gff3_path=pasa_assemblies_gff3,
        notes=(
            "TransDecoder input comes from the pasa_transcript_alignment results bundle.",
        ),
    )
    transdecoder_asset = CodingPredictionResult(
        output_dir=copied_transdecoder_dir,
        input_transcripts_fasta_path=require_path(
            copied_transdecoder_dir / pasa_assemblies_fasta.name,
            "Staged PASA assemblies FASTA",
        ),
        transdecoder_dir_path=_transdecoder_dir(copied_transdecoder_dir, pasa_assemblies_fasta.name),
        predicted_orfs_gff3_path=_transdecoder_gff3(copied_transdecoder_dir, pasa_assemblies_fasta.name),
        predicted_genome_gff3_path=_transdecoder_genome_gff3(copied_transdecoder_dir, pasa_assemblies_fasta.name),
        predicted_bed_path=_transdecoder_bed(copied_transdecoder_dir, pasa_assemblies_fasta.name),
        cds_fasta_path=_transdecoder_cds(copied_transdecoder_dir, pasa_assemblies_fasta.name),
        peptide_fasta_path=_transdecoder_pep(copied_transdecoder_dir, pasa_assemblies_fasta.name),
        mrna_fasta_path=_transdecoder_mrna(copied_transdecoder_dir, pasa_assemblies_fasta.name),
        source_pasa=source_pasa_asset,
        notes=(
            "This implementation infers a standard TransDecoder LongOrfs -> Predict flow because the notes specify the desired TransDecoder genome GFF3 output but not the exact command sequence.",
            "Genome-coordinate ORF lifting is performed with the configured TransDecoder utility script against the PASA assemblies GFF3.",
        ),
    )

    assumptions = [
        "This stage consumes the pasa_transcript_alignment results bundle and resolves the PASA assemblies FASTA and PASA assemblies GFF3 from its pasa/ directory.",
        "The design notes specify a PASA-derived TransDecoder genome GFF3 for later EVM input, but they do not spell out the exact TransDecoder commands. This implementation therefore infers a standard TransDecoder.LongOrfs followed by TransDecoder.Predict sequence.",
        "Genome-coordinate ORF lifting is performed with the configurable TransDecoder utility script, which defaults to cdna_alignment_orf_to_genome_orf.pl and must be available in the local environment or container image.",
        "This milestone stops at TransDecoder coding-region prediction and does not yet implement Exonerate, BRAKER3 normalization, EVM, PASA update rounds, repeat filtering, BUSCO, EggNOG, AGAT, or submission preparation.",
    ]
    manifest = build_manifest_envelope(
        stage=TRANSDECODER_WORKFLOW_NAME,
        assumptions=assumptions,
        inputs={
            "sample_id": sample_id,
            "source_pasa_results": str(pasa_results_path),
        },
        outputs={
            "transdecoder_dir": str(copied_transdecoder_dir),
            "input_transcripts_fasta": str(transdecoder_asset.input_transcripts_fasta_path),
            "transdecoder_intermediate_dir": str(transdecoder_asset.transdecoder_dir_path)
            if transdecoder_asset.transdecoder_dir_path
            else None,
            "transdecoder_orfs_gff3": str(transdecoder_asset.predicted_orfs_gff3_path)
            if transdecoder_asset.predicted_orfs_gff3_path
            else None,
            "transdecoder_genome_gff3": str(transdecoder_asset.predicted_genome_gff3_path)
            if transdecoder_asset.predicted_genome_gff3_path
            else None,
            "transdecoder_bed": str(transdecoder_asset.predicted_bed_path)
            if transdecoder_asset.predicted_bed_path
            else None,
            "transdecoder_cds": str(transdecoder_asset.cds_fasta_path)
            if transdecoder_asset.cds_fasta_path
            else None,
            "transdecoder_pep": str(transdecoder_asset.peptide_fasta_path)
            if transdecoder_asset.peptide_fasta_path
            else None,
            "transdecoder_mrna": str(transdecoder_asset.mrna_fasta_path)
            if transdecoder_asset.mrna_fasta_path
            else None,
            "source_pasa_assemblies_fasta": str(source_pasa_asset.assemblies_fasta_path)
            if source_pasa_asset.assemblies_fasta_path
            else None,
            "source_pasa_assemblies_gff3": str(source_pasa_asset.pasa_assemblies_gff3_path)
            if source_pasa_asset.pasa_assemblies_gff3_path
            else None,
        },
    )
    manifest["workflow"] = TRANSDECODER_WORKFLOW_NAME
    manifest["sample_id"] = sample_id
    manifest["source_pasa_results"] = str(pasa_results_path)
    manifest["assets"] = _as_json_compatible(
        {
            "source_pasa_alignment_assembly": asdict(source_pasa_asset),
            "coding_prediction": asdict(transdecoder_asset),
            "transdecoder_prediction": asdict(transdecoder_asset),
        }
    )
    manifest["transdecoder_files"] = sorted(path.name for path in copied_transdecoder_dir.glob("*"))
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))
