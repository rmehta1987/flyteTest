"""PASA task implementations for FLyteTest transcript and post-EVM refinement.

This module covers PASA transcript preparation and align/assemble using the
internally collected Trinity transcript branch, plus downstream post-EVM PASA
update rounds.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir, File

from flytetest.config import (
    PASA_RESULTS_PREFIX,
    PASA_UPDATE_RESULTS_PREFIX,
    PASA_UPDATE_WORKFLOW_NAME,
    PASA_WORKFLOW_NAME,
    RESULTS_ROOT,
    pasa_env,
    pasa_update_env,
    require_path,
    run_tool,
)
from flytetest.types import (
    CombinedTrinityTranscriptAsset,
    PasaAlignmentAssemblyResult,
    PasaCleanedTranscriptAsset,
    PasaGeneModelUpdateInputBundleAsset,
    PasaGeneModelUpdateResultBundle,
    PasaGeneModelUpdateRoundResult,
    PasaSqliteConfigAsset,
    ReferenceGenome,
    StringTieAssemblyResult,
    TrinityDeNovoTranscriptAsset,
    TrinityGenomeGuidedAssemblyResult,
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


def _trinity_gg_fasta(trinity_dir: Path) -> Path:
    """Resolve the primary genome-guided Trinity FASTA from a task output directory."""
    for candidate in (
        trinity_dir / "Trinity-GG.fasta",
        trinity_dir / "Trinity.fasta",
    ):
        if candidate.exists():
            return candidate

    fasta_candidates = sorted(trinity_dir.glob("*.fasta"))
    if len(fasta_candidates) == 1:
        return fasta_candidates[0]
    raise FileNotFoundError(
        f"Genome-guided Trinity FASTA not found in expected locations under {trinity_dir}"
    )


def _trinity_denovo_fasta(trinity_dir: Path) -> Path:
    """Resolve the primary de novo Trinity FASTA from a task output directory."""
    for candidate in (
        trinity_dir / "Trinity.fasta",
        trinity_dir / "trinity_denovo.Trinity.fasta",
    ):
        if candidate.exists():
            return candidate

    named_candidates = sorted(trinity_dir.glob("*.Trinity.fasta"))
    if len(named_candidates) == 1:
        return named_candidates[0]

    fasta_candidates = sorted(trinity_dir.glob("*.fasta"))
    if len(fasta_candidates) == 1:
        return fasta_candidates[0]
    raise FileNotFoundError(
        f"De novo Trinity FASTA not found in expected locations under {trinity_dir}"
    )


def _stringtie_gtf(stringtie_dir: Path) -> Path:
    """Resolve the main StringTie transcript GTF used as PASA input."""
    return require_path(stringtie_dir / "transcripts.gtf", "StringTie transcripts GTF")


def _stringtie_abundance(stringtie_dir: Path) -> Path | None:
    """Return StringTie's gene abundance table when it is present."""
    candidate = stringtie_dir / "gene_abund.tab"
    if candidate.exists():
        return candidate
    return None


def _seqclean_clean_fasta(seqclean_dir: Path) -> Path:
    """Resolve the single cleaned transcript FASTA produced by `seqclean`."""
    clean_candidates = sorted(seqclean_dir.glob("*.clean"))
    if len(clean_candidates) == 1:
        return clean_candidates[0]
    raise FileNotFoundError(f"seqclean output FASTA not found under {seqclean_dir}")


def _pasa_config_path(config_dir: Path) -> Path:
    """Resolve the rewritten PASA align-and-assemble config file."""
    return require_path(config_dir / "pasa.alignAssembly.config", "PASA align/assemble config")


def _sqlite_db_path(config_dir: Path) -> Path:
    """Resolve the single SQLite database file created for a PASA run."""
    candidates = sorted(
        path
        for path in config_dir.iterdir()
        if path.is_file() and (path.suffix in {".sqlite", ".db"} or path.name.endswith(".sqlite"))
    )
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single SQLite database file under {config_dir}")


def _first_existing(directory: Path, suffixes: tuple[str, ...], prefixes: tuple[str, ...]) -> Path | None:
    """Return the first PASA output that matches the allowed prefixes and suffixes."""
    for prefix in prefixes:
        for suffix in suffixes:
            candidate = directory / f"{prefix}{suffix}"
            if candidate.exists():
                return candidate
    return None


def _pasa_output_prefixes(database_name: str) -> tuple[str, ...]:
    """Return PASA filename prefixes compatible with a database name and its stem."""
    stem = Path(database_name).stem
    if stem == database_name:
        return (database_name,)
    return (database_name, stem)


def _pasa_assemblies_fasta(pasa_dir: Path, database_name: str) -> Path | None:
    """Resolve the PASA assemblies FASTA if the run produced one."""
    return _first_existing(pasa_dir, (".assemblies.fasta",), _pasa_output_prefixes(database_name))


def _pasa_assemblies_gff3(pasa_dir: Path, database_name: str) -> Path | None:
    """Resolve the PASA assemblies GFF3 if the run produced one."""
    return _first_existing(
        pasa_dir,
        (".pasa_assemblies.gff3", ".assemblies.gff3"),
        _pasa_output_prefixes(database_name),
    )


def _pasa_assemblies_gtf(pasa_dir: Path, database_name: str) -> Path | None:
    """Resolve the PASA assemblies GTF if the run produced one."""
    return _first_existing(
        pasa_dir,
        (".pasa_assemblies.gtf", ".assemblies.gtf"),
        _pasa_output_prefixes(database_name),
    )


def _pasa_alt_splicing_support(pasa_dir: Path, database_name: str) -> Path | None:
    """Resolve PASA alt-splicing support output when it is present."""
    return _first_existing(
        pasa_dir,
        (".alt_splicing_supporting_evidence.txt",),
        _pasa_output_prefixes(database_name),
    )


def _pasa_polyasites_fasta(pasa_dir: Path, database_name: str) -> Path | None:
    """Resolve PASA polyA-site FASTA output when it is present."""
    return _first_existing(
        pasa_dir,
        (".polyAsites.fasta",),
        _pasa_output_prefixes(database_name),
    )


def _sample_id_from_transcript_evidence(results_dir: Path) -> str:
    """Extract the sample identifier from a transcript-evidence manifest when available."""
    manifest_path = results_dir / "run_manifest.json"
    if not manifest_path.exists():
        return "sample"
    manifest = json.loads(manifest_path.read_text())
    return str(manifest.get("sample_id", "sample"))


@pasa_env.task
def pasa_accession_extract(
    denovo_trinity_fasta: File,
    pasa_sif: str = "",
) -> File:
    """Extract PASA TDN accessions from the de novo Trinity FASTA."""
    denovo_path = require_path(Path(denovo_trinity_fasta.download_sync()), "De novo Trinity FASTA")
    out_dir = Path(tempfile.mkdtemp(prefix="pasa_accs_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    accession_path = out_dir / "tdn.accs"

    run_tool(
        ["perl", "accession_extractor.pl", str(denovo_path), str(accession_path)],
        pasa_sif,
        [denovo_path.parent, out_dir],
    )
    return File.from_local_sync(str(accession_path))


@pasa_env.task
def combine_trinity_fastas(
    genome_guided_trinity_fasta: File,
    denovo_trinity_fasta: File,
) -> File:
    """Concatenate de novo and genome-guided Trinity FASTAs for PASA input."""
    gg_path = require_path(Path(genome_guided_trinity_fasta.download_sync()), "Genome-guided Trinity FASTA")
    denovo_path = require_path(Path(denovo_trinity_fasta.download_sync()), "De novo Trinity FASTA")

    out_dir = Path(tempfile.mkdtemp(prefix="pasa_combined_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    combined_path = out_dir / "trinity_transcripts.fa"

    with combined_path.open("wb") as handle:
        for input_path in (denovo_path, gg_path):
            with input_path.open("rb") as input_handle:
                shutil.copyfileobj(input_handle, handle)
            handle.write(b"\n")

    return File.from_local_sync(str(combined_path))


@pasa_env.task
def pasa_seqclean(
    transcripts: File,
    univec_fasta: File,
    pasa_sif: str = "",
    seqclean_threads: int = 4,
) -> Dir:
    """Run `seqclean` on the combined Trinity transcript FASTA."""
    transcripts_path = require_path(Path(transcripts.download_sync()), "Combined Trinity transcript FASTA")
    univec_path = require_path(Path(univec_fasta.download_sync()), "UniVec FASTA")

    out_dir = Path(tempfile.mkdtemp(prefix="pasa_seqclean_")) / "seqclean"
    out_dir.mkdir(parents=True, exist_ok=True)
    staged_transcripts = out_dir / transcripts_path.name
    shutil.copy2(transcripts_path, staged_transcripts)

    run_tool(
        [
            "seqclean",
            str(staged_transcripts),
            "-v",
            str(univec_path),
            "-c",
            str(seqclean_threads),
        ],
        pasa_sif,
        [out_dir, univec_path.parent],
        cwd=out_dir,
    )
    return Dir.from_local_sync(str(out_dir))


@pasa_env.task
def pasa_create_sqlite_db(
    pasa_config_template: File,
    pasa_db_name: str = "pasa.sqlite",
) -> Dir:
    """Create a SQLite-backed PASA config directory from a user template."""
    template_path = require_path(Path(pasa_config_template.download_sync()), "PASA align/assemble template config")
    out_dir = Path(tempfile.mkdtemp(prefix="pasa_config_")) / "config"
    out_dir.mkdir(parents=True, exist_ok=True)

    database_path = out_dir / pasa_db_name
    sqlite3.connect(database_path).close()

    copied_template_path = out_dir / template_path.name
    shutil.copy2(template_path, copied_template_path)
    config_path = out_dir / "pasa.alignAssembly.config"

    replaced_database = False
    rendered_lines: list[str] = []
    for line in template_path.read_text().splitlines():
        # The design notes only require a usable PASA database target, so this
        # milestone rewrites the DATABASE entry without inventing other config edits.
        if line.startswith("DATABASE="):
            rendered_lines.append(f"DATABASE={database_path}")
            replaced_database = True
        else:
            rendered_lines.append(line)

    if not replaced_database:
        raise ValueError(
            "The supplied PASA template config does not contain a DATABASE= line to rewrite."
        )

    config_path.write_text("\n".join(rendered_lines) + "\n")
    return Dir.from_local_sync(str(out_dir))


@pasa_env.task
def pasa_align_assemble(
    genome: File,
    cleaned_transcripts: Dir,
    unclean_transcripts: File,
    stringtie_gtf: File,
    pasa_config: Dir,
    tdn_accs: File,
    pasa_sif: str = "",
    pasa_aligners: str = "blat,gmap,minimap2",
    pasa_cpu: int = 4,
    pasa_max_intron_length: int = 100000,
) -> Dir:
    """Run PASA align-and-assemble with required de novo and genome-guided Trinity evidence."""
    genome_path = require_path(Path(genome.download_sync()), "Reference genome FASTA")
    cleaned_dir = require_path(Path(cleaned_transcripts.download_sync()), "seqclean output directory")
    clean_fasta_path = _seqclean_clean_fasta(cleaned_dir)
    unclean_transcripts_path = require_path(Path(unclean_transcripts.download_sync()), "Combined Trinity transcript FASTA")
    stringtie_gtf_path = require_path(Path(stringtie_gtf.download_sync()), "StringTie transcripts GTF")
    config_dir = require_path(Path(pasa_config.download_sync()), "PASA config directory")
    config_path = _pasa_config_path(config_dir)
    accession_path = require_path(Path(tdn_accs.download_sync()), "PASA de novo accession list")

    out_dir = Path(tempfile.mkdtemp(prefix="pasa_run_")) / "pasa"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "perl",
        "Launch_PASA_pipeline.pl",
        "--config",
        str(config_path),
        "--ALIGNERS",
        pasa_aligners,
        "--MAX_INTRON_LENGTH",
        str(pasa_max_intron_length),
        "--trans_gtf",
        str(stringtie_gtf_path),
        "--create",
        "--run",
        "--ALT_SPLICE",
        "--CPU",
        str(pasa_cpu),
        "--stringent_alignment_overlap",
        "30.0",
        "-T",
        "-u",
        str(unclean_transcripts_path),
        "--genome",
        str(genome_path),
        "--transcripts",
        str(clean_fasta_path),
        "--TDN",
        str(accession_path),
    ]

    bind_paths = [
        genome_path.parent,
        cleaned_dir,
        unclean_transcripts_path.parent,
        stringtie_gtf_path.parent,
        config_dir,
        out_dir,
        accession_path.parent,
    ]

    run_tool(cmd, pasa_sif, bind_paths, cwd=out_dir)
    return Dir.from_local_sync(str(out_dir))


@pasa_env.task
def collect_pasa_results(
    genome: File,
    transcript_evidence_results: Dir,
    univec_fasta: File,
    combined_trinity: File,
    seqclean: Dir,
    pasa_config: Dir,
    pasa_run: Dir,
    stringtie_gtf: File,
    trinity_denovo_fasta: File,
    tdn_accs: File,
    sample_id: str = "sample",
) -> Dir:
    """Collect PASA preparation outputs into a stable manifest-bearing results bundle."""
    genome_input = Path(str(genome.path))
    transcript_evidence_path = require_path(
        Path(transcript_evidence_results.download_sync()),
        "Transcript evidence results directory",
    )
    univec_input = Path(str(univec_fasta.path))
    combined_path = require_path(Path(combined_trinity.download_sync()), "Combined Trinity FASTA")
    seqclean_path = require_path(Path(seqclean.download_sync()), "seqclean output directory")
    config_path = require_path(Path(pasa_config.download_sync()), "PASA config directory")
    pasa_run_path = require_path(Path(pasa_run.download_sync()), "PASA output directory")
    stringtie_gtf_path = require_path(Path(stringtie_gtf.download_sync()), "StringTie transcripts GTF")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{PASA_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_combined_dir = out_dir / "combined_trinity"
    copied_seqclean_dir = out_dir / "seqclean"
    copied_config_dir = out_dir / "config"
    copied_pasa_dir = out_dir / "pasa"
    copied_accession_dir = out_dir / "accessions"

    copied_combined_dir.mkdir(parents=True, exist_ok=True)
    copied_combined_path = copied_combined_dir / combined_path.name
    shutil.copy2(combined_path, copied_combined_path)
    shutil.copytree(seqclean_path, copied_seqclean_dir, dirs_exist_ok=True)
    shutil.copytree(config_path, copied_config_dir, dirs_exist_ok=True)
    shutil.copytree(pasa_run_path, copied_pasa_dir, dirs_exist_ok=True)

    accession_path = require_path(Path(tdn_accs.download_sync()), "PASA de novo accession list")
    copied_accession_dir.mkdir(parents=True, exist_ok=True)
    copied_accession_path = copied_accession_dir / accession_path.name
    shutil.copy2(accession_path, copied_accession_path)

    trinity_gg_dir = require_path(
        transcript_evidence_path / "trinity_gg",
        "Transcript evidence Trinity genome-guided directory",
    )
    stringtie_dir = require_path(
        transcript_evidence_path / "stringtie",
        "Transcript evidence StringTie directory",
    )

    reference_asset = ReferenceGenome(fasta_path=genome_input)
    genome_guided_asset = TrinityGenomeGuidedAssemblyResult(
        output_dir=trinity_gg_dir,
        assembly_fasta_path=_trinity_gg_fasta(trinity_gg_dir),
        notes=(
            "Genome-guided Trinity input comes from the transcript_evidence_generation results bundle.",
        ),
    )
    denovo_input_path = require_path(Path(trinity_denovo_fasta.download_sync()), "De novo Trinity FASTA")
    denovo_asset = TrinityDeNovoTranscriptAsset(
        fasta_path=denovo_input_path,
        notes=(
            "De novo Trinity input comes from the transcript_evidence_generation results bundle.",
        ),
    )
    combined_asset = CombinedTrinityTranscriptAsset(
        fasta_path=copied_combined_path,
        genome_guided_transcripts=genome_guided_asset,
        de_novo_transcripts=denovo_asset,
        notes=(
            "The combined transcript FASTA follows the note order: de novo Trinity first, then Trinity-GG.",
        ),
    )
    cleaned_asset = PasaCleanedTranscriptAsset(
        output_dir=copied_seqclean_dir,
        clean_fasta_path=_seqclean_clean_fasta(copied_seqclean_dir),
        input_transcripts=combined_asset,
        univec_fasta_path=univec_input,
        notes=(
            "seqclean output is staged in its own directory because PASA tooling writes auxiliary files beside the cleaned FASTA.",
        ),
    )
    sqlite_database_path = _sqlite_db_path(copied_config_dir)
    database_asset = PasaSqliteConfigAsset(
        config_dir=copied_config_dir,
        config_path=_pasa_config_path(copied_config_dir),
        database_path=sqlite_database_path,
        template_path=next(
            (
                path
                for path in copied_config_dir.iterdir()
                if path.is_file()
                and path.name != "pasa.alignAssembly.config"
                and path != sqlite_database_path
            ),
            None,
        ),
        notes=(
            "This milestone prepares a SQLite-backed PASA config by rewriting only the DATABASE= line in a user-supplied PASA template.",
        ),
    )
    stringtie_asset = StringTieAssemblyResult(
        output_dir=stringtie_dir,
        transcript_gtf_path=stringtie_gtf_path,
        gene_abundance_path=_stringtie_abundance(stringtie_dir),
        notes=(
            "StringTie input comes from the transcript_evidence_generation results bundle.",
        ),
    )
    pasa_asset = PasaAlignmentAssemblyResult(
        output_dir=copied_pasa_dir,
        database_name=database_asset.database_path.name,
        assemblies_fasta_path=_pasa_assemblies_fasta(copied_pasa_dir, database_asset.database_path.name),
        pasa_assemblies_gff3_path=_pasa_assemblies_gff3(copied_pasa_dir, database_asset.database_path.name),
        pasa_assemblies_gtf_path=_pasa_assemblies_gtf(copied_pasa_dir, database_asset.database_path.name),
        alt_splicing_support_path=_pasa_alt_splicing_support(copied_pasa_dir, database_asset.database_path.name),
        polyasites_fasta_path=_pasa_polyasites_fasta(copied_pasa_dir, database_asset.database_path.name),
        cleaned_transcripts=cleaned_asset,
        stringtie_gtf_path=stringtie_asset.transcript_gtf_path,
        database_config=database_asset,
        notes=(
            "The PASA align/assemble invocation mirrors the flags shown in the attached notes for aligners, max intron length, ALT_SPLICE, create/run, -T, and stringent alignment overlap.",
        ),
    )

    manifest = {
        "workflow": PASA_WORKFLOW_NAME,
        "sample_id": sample_id,
        "source_transcript_evidence_results": str(transcript_evidence_path),
        "notes_alignment": {
            "status": "implemented_with_documented_simplifications",
            "requires_external_denovo_trinity": False,
            "reason": "PASA now consumes both internally produced Trinity branches from the transcript-evidence bundle, while that upstream bundle still keeps the notes-backed all-sample STAR/BAM path simplified to one paired-end sample.",
        },
        "assumptions": [
            "This workflow consumes the transcript_evidence_generation bundle, specifically trinity_denovo/, trinity_gg/, and stringtie/ outputs.",
            "The combined Trinity transcript FASTA follows the note order: de novo Trinity first, then Trinity-GG.",
            "A user-supplied PASA alignAssembly template is required because the exact PASA config file content is environment-specific in the notes.",
            "The SQLite database file is created locally with Python's sqlite3 library, then referenced from the rewritten PASA config template.",
            "The PASA align/assemble invocation follows the note flags: --ALIGNERS blat,gmap,minimap2, --MAX_INTRON_LENGTH 100000, --create, --run, --ALT_SPLICE, --CPU, --stringent_alignment_overlap 30.0, and -T.",
            "The upstream transcript bundle now includes both Trinity branches required before PASA, but STAR alignment and BAM merge still remain single-sample simplifications relative to the notes.",
            "TransDecoder, Exonerate, BRAKER3, and EVM are not part of this PASA milestone.",
        ],
        "outputs": {
            "source_trinity_denovo_fasta": str(denovo_asset.fasta_path),
            "combined_trinity_fasta": str(copied_combined_path),
            "seqclean_dir": str(copied_seqclean_dir),
            "seqclean_clean_fasta": str(cleaned_asset.clean_fasta_path),
            "config_dir": str(copied_config_dir),
            "pasa_config": str(database_asset.config_path),
            "sqlite_database": str(database_asset.database_path),
            "pasa_output_dir": str(copied_pasa_dir),
            "pasa_assemblies_fasta": str(pasa_asset.assemblies_fasta_path) if pasa_asset.assemblies_fasta_path else None,
            "pasa_assemblies_gff3": str(pasa_asset.pasa_assemblies_gff3_path) if pasa_asset.pasa_assemblies_gff3_path else None,
            "pasa_assemblies_gtf": str(pasa_asset.pasa_assemblies_gtf_path) if pasa_asset.pasa_assemblies_gtf_path else None,
            "alt_splicing_support": str(pasa_asset.alt_splicing_support_path) if pasa_asset.alt_splicing_support_path else None,
            "polyasites_fasta": str(pasa_asset.polyasites_fasta_path) if pasa_asset.polyasites_fasta_path else None,
            "tdn_accs": str(copied_accession_path),
            "source_stringtie_gtf": str(stringtie_asset.transcript_gtf_path),
        },
        "assets": _as_json_compatible(
            {
                "reference_genome": asdict(reference_asset),
                "trinity_genome_guided": asdict(genome_guided_asset),
                "trinity_de_novo": asdict(denovo_asset),
                "combined_trinity": asdict(combined_asset),
                "stringtie": asdict(stringtie_asset),
                "pasa_cleaned_transcripts": asdict(cleaned_asset),
                "pasa_database_config": asdict(database_asset),
                "pasa_alignment_assembly": asdict(pasa_asset),
            }
        ),
        "combined_trinity_files": sorted(path.name for path in copied_combined_dir.glob("*")),
        "seqclean_files": sorted(path.name for path in copied_seqclean_dir.glob("*")),
        "config_files": sorted(path.name for path in copied_config_dir.glob("*")),
        "pasa_files": sorted(path.name for path in copied_pasa_dir.glob("*")),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir.from_local_sync(str(out_dir))


def _read_json(path: Path) -> dict[str, Any]:
    """Read one JSON manifest into a dictionary."""
    return json.loads(path.read_text())


def _manifest_path(results_dir: Path, label: str) -> Path:
    """Resolve the run manifest path for one staged or collected directory."""
    return require_path(results_dir / "run_manifest.json", f"{label} manifest")


def _manifest_output_path(manifest: dict[str, Any], key: str, description: str) -> Path | None:
    """Resolve one manifest-recorded output path when present."""
    output_path = manifest.get("outputs", {}).get(key)
    if not output_path:
        return None
    return require_path(Path(str(output_path)), description)


def _copy_file(source: Path, destination: Path) -> Path:
    """Copy one file into a deterministic destination and return the copy path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _copy_tree(source: Path, destination: Path) -> Path:
    """Copy one directory tree into a deterministic destination and return it."""
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return destination


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write one JSON payload with indentation and return the file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _pasa_clean_fasta_from_results(results_dir: Path, manifest: dict[str, Any]) -> Path:
    """Resolve the cleaned Trinity transcript FASTA from a PASA results bundle."""
    manifest_path = _manifest_output_path(
        manifest,
        "seqclean_clean_fasta",
        "PASA cleaned transcript FASTA recorded in the PASA manifest",
    )
    if manifest_path is not None:
        return manifest_path
    seqclean_dir = require_path(results_dir / "seqclean", "PASA seqclean directory")
    return _seqclean_clean_fasta(seqclean_dir)


def _pasa_align_config_from_results(results_dir: Path, manifest: dict[str, Any]) -> Path:
    """Resolve the PASA alignAssembly config from a PASA results bundle."""
    manifest_path = _manifest_output_path(
        manifest,
        "pasa_config",
        "PASA alignAssembly config recorded in the PASA manifest",
    )
    if manifest_path is not None:
        return manifest_path
    return _pasa_config_path(require_path(results_dir / "config", "PASA config directory"))


def _pasa_database_from_results(results_dir: Path, manifest: dict[str, Any]) -> Path:
    """Resolve the PASA SQLite database from a PASA results bundle."""
    manifest_path = _manifest_output_path(
        manifest,
        "sqlite_database",
        "PASA SQLite database recorded in the PASA manifest",
    )
    if manifest_path is not None:
        return manifest_path
    return _sqlite_db_path(require_path(results_dir / "config", "PASA config directory"))


def _evm_sorted_gff3_from_results(results_dir: Path, manifest: dict[str, Any]) -> Path:
    """Resolve the final sorted EVM GFF3 from an EVM results bundle."""
    manifest_path = _manifest_output_path(
        manifest,
        "sorted_gff3",
        "Sorted EVM GFF3 recorded in the EVM manifest",
    )
    if manifest_path is not None:
        return manifest_path
    return require_path(results_dir / "EVM.all.sort.gff3", "Sorted EVM GFF3")


def _evm_reference_genome_from_results(results_dir: Path) -> Path:
    """Resolve the authoritative reference genome copied through the EVM bundle."""
    for candidate in (
        results_dir / "evm_execution_inputs" / "genome.fa",
        results_dir / "pre_evm_bundle" / "reference" / "genome.fa",
    ):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Unable to resolve a reference genome FASTA from the EVM results bundle {results_dir}."
    )


def _pasa_update_workspace_annotations(workspace_dir: Path) -> Path:
    """Resolve the canonical current-annotations GFF3 within an update workspace."""
    return require_path(
        workspace_dir / "annotations" / "current_annotations.gff3",
        "PASA update current annotations GFF3",
    )


def _pasa_update_align_config(workspace_dir: Path) -> Path:
    """Resolve the copied PASA alignAssembly config within an update workspace."""
    return require_path(
        workspace_dir / "config" / "pasa.alignAssembly.config",
        "PASA update alignAssembly config",
    )


def _pasa_update_annot_compare_config(workspace_dir: Path) -> Path:
    """Resolve the copied PASA annotCompare config within an update workspace."""
    return require_path(
        workspace_dir / "config" / "pasa.annotCompare.config",
        "PASA update annotCompare config",
    )


def _pasa_update_database(workspace_dir: Path) -> Path:
    """Resolve the copied PASA SQLite database within an update workspace."""
    return _sqlite_db_path(require_path(workspace_dir / "config", "PASA update config directory"))


def _pasa_update_cleaned_transcripts(workspace_dir: Path) -> Path:
    """Resolve the copied cleaned transcript FASTA within an update workspace."""
    transcripts_dir = require_path(workspace_dir / "transcripts", "PASA update transcripts directory")
    clean_candidates = sorted(transcripts_dir.glob("*.clean"))
    if len(clean_candidates) == 1:
        return clean_candidates[0]
    raise FileNotFoundError(
        f"Unable to resolve a single cleaned transcript FASTA under {transcripts_dir}."
    )


def _pasa_update_reference_genome(workspace_dir: Path) -> Path:
    """Resolve the copied reference genome FASTA within an update workspace."""
    return require_path(
        workspace_dir / "reference" / "genome.fa",
        "PASA update reference genome FASTA",
    )


def _render_database_config(template_path: Path, destination: Path, database_path: Path) -> Path:
    """Rewrite only the DATABASE line in a PASA config template."""
    rendered_lines: list[str] = []
    replaced_database = False
    for line in template_path.read_text().splitlines():
        if line.startswith("DATABASE="):
            rendered_lines.append(f"DATABASE={database_path}")
            replaced_database = True
        else:
            rendered_lines.append(line)
    if not replaced_database:
        raise ValueError(
            f"The PASA config template {template_path} does not contain a DATABASE= line to rewrite."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(rendered_lines) + "\n")
    return destination


def _prepare_pasa_update_bin(bin_dir: Path, fasta36_binary_path: str) -> Path | None:
    """Create the note-described `bin/fasta` symlink when a fasta36 binary is supplied."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    if not fasta36_binary_path:
        return None
    source_binary = require_path(Path(fasta36_binary_path), "fasta36 binary for PASA update")
    link_path = bin_dir / "fasta"
    if link_path.exists() or link_path.is_symlink():
        link_path.unlink()
    link_path.symlink_to(source_binary)
    return link_path


def _optional_fasta_symlink_target(workspace_dir: Path) -> Path | None:
    """Resolve the external fasta36 target when the workspace preserves a bin/fasta symlink."""
    link_path = workspace_dir / "bin" / "fasta"
    if not link_path.is_symlink():
        return None
    return require_path(link_path.resolve(), "PASA update fasta symlink target")


def _pasa_update_gff3_candidates(workspace_dir: Path) -> list[Path]:
    """Resolve raw PASA post-update GFF3 candidates in deterministic relative-path order."""
    candidates = sorted(
        (
            path
            for path in workspace_dir.rglob("*gene_structures_post_PASA_updates*.gff3")
            if ".removed." not in path.name and ".sort." not in path.name
        ),
        key=lambda path: str(path.relative_to(workspace_dir)),
    )
    return candidates


def _pasa_update_bed_candidates(workspace_dir: Path) -> list[Path]:
    """Resolve PASA post-update BED candidates in deterministic relative-path order."""
    return sorted(
        workspace_dir.rglob("*gene_structures_post_PASA_updates*.bed"),
        key=lambda path: str(path.relative_to(workspace_dir)),
    )


def _new_round_output(
    before_paths: set[str],
    after_paths: list[Path],
    workspace_dir: Path,
    description: str,
) -> Path:
    """Resolve the single new round output by comparing before and after path sets."""
    new_paths = [
        path
        for path in after_paths
        if str(path.relative_to(workspace_dir)) not in before_paths
    ]
    if len(new_paths) == 1:
        return new_paths[0]
    if len(after_paths) == 1 and not before_paths:
        return after_paths[0]
    raise FileNotFoundError(
        f"Unable to resolve a single new {description} under {workspace_dir}."
    )


def _write_blank_line_filtered_gff3(source: Path, destination: Path) -> Path:
    """Remove blank lines from a GFF3 file while preserving record order."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    filtered_lines = [line for line in source.read_text().splitlines() if line.strip()]
    destination.write_text("\n".join(filtered_lines) + "\n")
    return destination


@pasa_update_env.task
def prepare_pasa_update_inputs(
    pasa_results: Dir,
    evm_results: Dir,
    pasa_annot_compare_template: File,
    fasta36_binary_path: str = "",
) -> Dir:
    """Stage the PASA database state and sorted EVM GFF3 for post-EVM refinement."""
    pasa_results_dir = require_path(Path(pasa_results.download_sync()), "PASA results directory")
    evm_results_dir = require_path(Path(evm_results.download_sync()), "EVM results directory")
    annot_compare_template_path = require_path(
        Path(pasa_annot_compare_template.download_sync()),
        "PASA annotCompare template config",
    )
    pasa_manifest = _read_json(_manifest_path(pasa_results_dir, "PASA"))
    evm_manifest = _read_json(_manifest_path(evm_results_dir, "EVM"))

    cleaned_fasta = _pasa_clean_fasta_from_results(pasa_results_dir, pasa_manifest)
    align_config = _pasa_align_config_from_results(pasa_results_dir, pasa_manifest)
    sqlite_database = _pasa_database_from_results(pasa_results_dir, pasa_manifest)
    evm_sorted_gff3 = _evm_sorted_gff3_from_results(evm_results_dir, evm_manifest)
    genome_fasta = _evm_reference_genome_from_results(evm_results_dir)

    out_dir = Path(tempfile.mkdtemp(prefix="pasa_update_inputs_")) / "pasa_update_inputs"
    config_dir = out_dir / "config"
    transcripts_dir = out_dir / "transcripts"
    reference_dir = out_dir / "reference"
    annotations_dir = out_dir / "annotations"
    source_manifests_dir = out_dir / "source_manifests"
    config_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)
    annotations_dir.mkdir(parents=True, exist_ok=True)
    source_manifests_dir.mkdir(parents=True, exist_ok=True)

    copied_align_config = _copy_file(align_config, config_dir / "pasa.alignAssembly.config")
    copied_database = _copy_file(sqlite_database, config_dir / sqlite_database.name)
    copied_annot_compare_template = _copy_file(
        annot_compare_template_path,
        config_dir / annot_compare_template_path.name,
    )
    annot_compare_config = _render_database_config(
        copied_annot_compare_template,
        config_dir / "pasa.annotCompare.config",
        copied_database,
    )
    copied_cleaned_fasta = _copy_file(cleaned_fasta, transcripts_dir / cleaned_fasta.name)
    copied_genome = _copy_file(genome_fasta, reference_dir / "genome.fa")
    copied_evm_sorted_gff3 = _copy_file(evm_sorted_gff3, annotations_dir / "EVM.all.sort.gff3")
    current_annotations = _copy_file(
        copied_evm_sorted_gff3,
        annotations_dir / "current_annotations.gff3",
    )
    copied_pasa_manifest = _copy_file(
        _manifest_path(pasa_results_dir, "PASA"),
        source_manifests_dir / "pasa.run_manifest.json",
    )
    copied_evm_manifest = _copy_file(
        _manifest_path(evm_results_dir, "EVM"),
        source_manifests_dir / "evm.run_manifest.json",
    )
    fasta_symlink = _prepare_pasa_update_bin(out_dir / "bin", fasta36_binary_path)

    input_asset = PasaGeneModelUpdateInputBundleAsset(
        workspace_dir=out_dir,
        reference_genome_fasta_path=copied_genome,
        current_annotations_gff3_path=current_annotations,
        cleaned_transcripts_fasta_path=copied_cleaned_fasta,
        align_config_path=copied_align_config,
        annot_compare_config_path=annot_compare_config,
        database_path=copied_database,
        source_pasa_results_dir=pasa_results_dir,
        source_evm_results_dir=evm_results_dir,
        notes=(
            "This staged workspace consumes the existing PASA and EVM result bundles directly instead of re-deriving upstream evidence.",
            "Because the earlier PASA bundle preserves only the alignAssembly config, the annotCompare config must be supplied as an external template and is rewritten only at DATABASE=.",
        ),
    )
    manifest = {
        "stage": "prepare_pasa_update_inputs",
        "assumptions": [
            "This milestone consumes the PASA and EVM result bundles directly instead of re-running transcript evidence or EVM generation.",
            "The notes require both pasa.alignAssembly.config and pasa.annotCompare.config, but the current PASA bundle preserves only the alignAssembly config. The annotCompare config is therefore supplied as an external template and rewritten only at DATABASE=.",
            "The sorted EVM GFF3 is staged as both EVM.all.sort.gff3 and current_annotations.gff3 so later PASA rounds can advance a stable canonical annotation path.",
            "If fasta36_binary_path is empty, the workspace still creates bin/ but expects the runtime environment to provide the required `fasta` command behavior separately.",
        ],
        "inputs": {
            "pasa_results": str(pasa_results_dir),
            "evm_results": str(evm_results_dir),
            "pasa_annot_compare_template": str(annot_compare_template_path),
            "fasta36_binary_path": fasta36_binary_path,
        },
        "source_bundle_manifests": {
            "pasa": pasa_manifest,
            "evm": evm_manifest,
        },
        "outputs": {
            "reference_genome_fasta": str(copied_genome),
            "current_annotations_gff3": str(current_annotations),
            "evm_sorted_gff3": str(copied_evm_sorted_gff3),
            "cleaned_transcripts_fasta": str(copied_cleaned_fasta),
            "align_config": str(copied_align_config),
            "annot_compare_config": str(annot_compare_config),
            "sqlite_database": str(copied_database),
            "fasta_symlink": str(fasta_symlink) if fasta_symlink else None,
            "source_manifests_dir": str(source_manifests_dir),
        },
        "assets": _as_json_compatible({"pasa_gene_model_update_inputs": asdict(input_asset)}),
        "copied_source_manifests": {
            "pasa": str(copied_pasa_manifest),
            "evm": str(copied_evm_manifest),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir.from_local_sync(str(out_dir))


@pasa_update_env.task
def pasa_load_current_annotations(
    pasa_update_inputs: Dir,
    round_index: int = 1,
    load_current_annotations_script: str = "Load_Current_Gene_Annotations.dbi",
    pasa_sif: str = "",
) -> Dir:
    """Load the current annotation GFF3 into the staged PASA database for one round."""
    input_dir = require_path(Path(pasa_update_inputs.download_sync()), "PASA update input directory")
    input_manifest = _read_json(_manifest_path(input_dir, "PASA update inputs"))

    out_dir = Path(tempfile.mkdtemp(prefix=f"pasa_load_round_{round_index:02d}_")) / "pasa_load"
    _copy_tree(input_dir, out_dir)

    cmd = [
        "perl",
        load_current_annotations_script,
        "-c",
        str(_pasa_update_align_config(out_dir)),
        "-g",
        str(_pasa_update_reference_genome(out_dir)),
        "-P",
        str(_pasa_update_workspace_annotations(out_dir)),
    ]
    bind_paths = [out_dir]
    fasta_target = _optional_fasta_symlink_target(out_dir)
    if fasta_target is not None:
        bind_paths.append(fasta_target.parent)
    run_tool(cmd, pasa_sif, bind_paths, cwd=out_dir)

    manifest = {
        "stage": "pasa_load_current_annotations",
        "round_index": round_index,
        "assumptions": [
            "The notes load current annotations into the original PASA database before each update round using Load_Current_Gene_Annotations.dbi.",
            "This task does not add unsupported CPU flags to Load_Current_Gene_Annotations.dbi because the notes explicitly warn against doing so.",
        ],
        "inputs": {
            "pasa_update_inputs": str(input_dir),
            "load_current_annotations_script": load_current_annotations_script,
            "pasa_sif": pasa_sif,
        },
        "source_stage_manifest": input_manifest,
        "outputs": {
            "current_annotations_gff3": str(_pasa_update_workspace_annotations(out_dir)),
            "align_config": str(_pasa_update_align_config(out_dir)),
            "sqlite_database": str(_pasa_update_database(out_dir)),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir.from_local_sync(str(out_dir))


@pasa_update_env.task
def pasa_update_gene_models(
    loaded_pasa_update: Dir,
    round_index: int = 1,
    pasa_update_script: str = "Launch_PASA_pipeline.pl",
    pasa_sif: str = "",
    pasa_update_cpu: int = 8,
) -> Dir:
    """Run one PASA annotation-update round and promote its new GFF3 as current annotations."""
    loaded_dir = require_path(Path(loaded_pasa_update.download_sync()), "Loaded PASA update directory")
    loaded_manifest = _read_json(_manifest_path(loaded_dir, "Loaded PASA update directory"))

    out_dir = Path(tempfile.mkdtemp(prefix=f"pasa_update_round_{round_index:02d}_")) / "pasa_update"
    _copy_tree(loaded_dir, out_dir)

    annotations_dir = out_dir / "annotations"
    loaded_annotations_snapshot = _copy_file(
        _pasa_update_workspace_annotations(out_dir),
        annotations_dir / f"loaded_annotations.round_{round_index:02d}.gff3",
    )
    before_gff3_paths = {
        str(path.relative_to(out_dir))
        for path in _pasa_update_gff3_candidates(out_dir)
    }
    before_bed_paths = {
        str(path.relative_to(out_dir))
        for path in _pasa_update_bed_candidates(out_dir)
    }

    cmd = [
        "perl",
        pasa_update_script,
        "-c",
        str(_pasa_update_annot_compare_config(out_dir)),
        "-A",
        "-g",
        str(_pasa_update_reference_genome(out_dir)),
        "-t",
        str(_pasa_update_cleaned_transcripts(out_dir)),
        "--CPU",
        str(pasa_update_cpu),
    ]
    bind_paths = [out_dir]
    fasta_target = _optional_fasta_symlink_target(out_dir)
    if fasta_target is not None:
        bind_paths.append(fasta_target.parent)
    run_tool(cmd, pasa_sif, bind_paths, cwd=out_dir)

    updated_gff3 = _new_round_output(
        before_gff3_paths,
        _pasa_update_gff3_candidates(out_dir),
        out_dir,
        "PASA post-update GFF3",
    )
    updated_bed_candidates = _pasa_update_bed_candidates(out_dir)
    new_bed_candidates = [
        path
        for path in updated_bed_candidates
        if str(path.relative_to(out_dir)) not in before_bed_paths
    ]
    updated_bed = new_bed_candidates[0] if len(new_bed_candidates) == 1 else None
    current_annotations = _copy_file(
        updated_gff3,
        annotations_dir / "current_annotations.gff3",
    )
    if updated_bed is not None:
        _copy_file(updated_bed, annotations_dir / "current_annotations.bed")

    round_asset = PasaGeneModelUpdateRoundResult(
        workspace_dir=out_dir,
        round_index=round_index,
        loaded_annotations_gff3_path=loaded_annotations_snapshot,
        updated_gff3_path=updated_gff3,
        updated_bed_path=updated_bed,
        current_annotations_gff3_path=current_annotations,
        input_bundle=PasaGeneModelUpdateInputBundleAsset(
            workspace_dir=loaded_dir,
            reference_genome_fasta_path=_pasa_update_reference_genome(loaded_dir),
            current_annotations_gff3_path=_pasa_update_workspace_annotations(loaded_dir),
            cleaned_transcripts_fasta_path=_pasa_update_cleaned_transcripts(loaded_dir),
            align_config_path=_pasa_update_align_config(loaded_dir),
            annot_compare_config_path=_pasa_update_annot_compare_config(loaded_dir),
            database_path=_pasa_update_database(loaded_dir),
        ),
        notes=(
            "After each PASA update round, the newly emitted gene-model GFF3 is promoted to annotations/current_annotations.gff3 for the next round.",
        ),
    )
    manifest = {
        "stage": "pasa_update_gene_models",
        "round_index": round_index,
        "assumptions": [
            "The notes require at least two PASA update rounds and specify that round 2 should load the prior round's post-update GFF3 instead of the original EVM GFF3.",
            "This task therefore preserves a canonical annotations/current_annotations.gff3 path that advances after each round.",
        ],
        "inputs": {
            "loaded_pasa_update": str(loaded_dir),
            "pasa_update_script": pasa_update_script,
            "pasa_sif": pasa_sif,
            "pasa_update_cpu": pasa_update_cpu,
        },
        "source_stage_manifest": loaded_manifest,
        "outputs": {
            "loaded_annotations_snapshot": str(loaded_annotations_snapshot),
            "updated_gff3": str(updated_gff3),
            "updated_bed": str(updated_bed) if updated_bed else None,
            "current_annotations_gff3": str(current_annotations),
        },
        "relative_outputs": {
            "loaded_annotations_snapshot": str(loaded_annotations_snapshot.relative_to(out_dir)),
            "updated_gff3": str(updated_gff3.relative_to(out_dir)),
            "updated_bed": str(updated_bed.relative_to(out_dir)) if updated_bed else None,
            "current_annotations_gff3": str(current_annotations.relative_to(out_dir)),
        },
        "assets": _as_json_compatible({"pasa_gene_model_update_round": asdict(round_asset)}),
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir.from_local_sync(str(out_dir))


@pasa_update_env.task
def finalize_pasa_update_outputs(
    pasa_update_round: Dir,
    gff3sort_script: str = "gff3sort.pl",
    pasa_sif: str = "",
) -> Dir:
    """Create stable blank-line-filtered and sorted final GFF3 files from the last update round."""
    round_dir = require_path(Path(pasa_update_round.download_sync()), "PASA update round directory")
    round_manifest = _read_json(_manifest_path(round_dir, "PASA update round directory"))

    out_dir = Path(tempfile.mkdtemp(prefix="pasa_update_finalize_")) / "pasa_update_finalized"
    _copy_tree(round_dir, out_dir)

    raw_final_gff3 = _copy_file(
        _pasa_update_workspace_annotations(out_dir),
        out_dir / "post_pasa_updates.gff3",
    )
    removed_gff3 = _write_blank_line_filtered_gff3(
        raw_final_gff3,
        out_dir / "post_pasa_updates.removed.gff3",
    )
    sorted_gff3 = out_dir / "post_pasa_updates.sort.gff3"
    if gff3sort_script.strip():
        run_tool(
            [
                "perl",
                gff3sort_script,
                "--precise",
                str(removed_gff3),
            ],
            pasa_sif,
            [out_dir],
            cwd=out_dir,
            stdout_path=sorted_gff3,
        )
    else:
        shutil.copy2(removed_gff3, sorted_gff3)

    manifest = {
        "stage": "finalize_pasa_update_outputs",
        "assumptions": [
            "The notes remove blank lines from the final PASA post-update GFF3 and then sort it with gff3sort.pl.",
            "If gff3sort_script is empty, this task copies the blank-line-filtered GFF3 to the final sorted filename and records that sorting was skipped explicitly.",
        ],
        "inputs": {
            "pasa_update_round": str(round_dir),
            "gff3sort_script": gff3sort_script,
            "pasa_sif": pasa_sif,
        },
        "source_stage_manifest": round_manifest,
        "outputs": {
            "raw_final_gff3": str(raw_final_gff3),
            "removed_gff3": str(removed_gff3),
            "sorted_gff3": str(sorted_gff3),
        },
        "sorting_applied": bool(gff3sort_script.strip()),
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir.from_local_sync(str(out_dir))


@pasa_update_env.task
def collect_pasa_update_results(
    pasa_results: Dir,
    evm_results: Dir,
    pasa_update_inputs: Dir,
    load_rounds: list[Dir],
    update_rounds: list[Dir],
    finalized_outputs: Dir,
) -> Dir:
    """Collect staged PASA-update inputs, round outputs, and final files into one bundle."""
    if not load_rounds:
        raise ValueError("collect_pasa_update_results requires at least one PASA load round.")
    if len(load_rounds) != len(update_rounds):
        raise ValueError("PASA load-round and update-round lists must have the same length.")

    pasa_results_dir = require_path(Path(pasa_results.download_sync()), "PASA results directory")
    evm_results_dir = require_path(Path(evm_results.download_sync()), "EVM results directory")
    staged_inputs_dir = require_path(Path(pasa_update_inputs.download_sync()), "PASA update inputs directory")
    finalized_dir = require_path(Path(finalized_outputs.download_sync()), "PASA finalized update directory")
    load_round_dirs = [
        require_path(Path(round_dir.download_sync()), "PASA load round directory")
        for round_dir in load_rounds
    ]
    update_round_dirs = [
        require_path(Path(round_dir.download_sync()), "PASA update round directory")
        for round_dir in update_rounds
    ]

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{PASA_UPDATE_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_staged_inputs_dir = _copy_tree(staged_inputs_dir, out_dir / "staged_inputs")
    copied_load_root = out_dir / "load_rounds"
    copied_update_root = out_dir / "update_rounds"
    copied_load_root.mkdir(parents=True, exist_ok=True)
    copied_update_root.mkdir(parents=True, exist_ok=True)

    copied_load_dirs: list[Path] = []
    for load_dir in sorted(
        load_round_dirs,
        key=lambda path: int(_read_json(_manifest_path(path, "PASA load round"))["round_index"]),
    ):
        round_index = int(_read_json(_manifest_path(load_dir, "PASA load round"))["round_index"])
        copied_load_dirs.append(_copy_tree(load_dir, copied_load_root / f"round_{round_index:02d}"))

    copied_update_dirs: list[Path] = []
    for update_dir in sorted(
        update_round_dirs,
        key=lambda path: int(_read_json(_manifest_path(path, "PASA update round"))["round_index"]),
    ):
        round_index = int(_read_json(_manifest_path(update_dir, "PASA update round"))["round_index"])
        copied_update_dirs.append(_copy_tree(update_dir, copied_update_root / f"round_{round_index:02d}"))

    copied_finalized_dir = _copy_tree(finalized_dir, out_dir / "finalized")
    source_manifests_dir = out_dir / "source_manifests"
    source_manifests_dir.mkdir(parents=True, exist_ok=True)
    copied_pasa_manifest = _copy_file(
        _manifest_path(pasa_results_dir, "PASA"),
        source_manifests_dir / "pasa.run_manifest.json",
    )
    copied_evm_manifest = _copy_file(
        _manifest_path(evm_results_dir, "EVM"),
        source_manifests_dir / "evm.run_manifest.json",
    )

    final_raw_gff3 = _copy_file(
        require_path(copied_finalized_dir / "post_pasa_updates.gff3", "Final PASA post-update GFF3"),
        out_dir / "post_pasa_updates.gff3",
    )
    final_removed_gff3 = _copy_file(
        require_path(
            copied_finalized_dir / "post_pasa_updates.removed.gff3",
            "Final PASA blank-line-filtered GFF3",
        ),
        out_dir / "post_pasa_updates.removed.gff3",
    )
    final_sorted_gff3 = _copy_file(
        require_path(copied_finalized_dir / "post_pasa_updates.sort.gff3", "Final PASA sorted GFF3"),
        out_dir / "post_pasa_updates.sort.gff3",
    )

    staged_asset = PasaGeneModelUpdateInputBundleAsset(
        workspace_dir=copied_staged_inputs_dir,
        reference_genome_fasta_path=_pasa_update_reference_genome(copied_staged_inputs_dir),
        current_annotations_gff3_path=_pasa_update_workspace_annotations(copied_staged_inputs_dir),
        cleaned_transcripts_fasta_path=_pasa_update_cleaned_transcripts(copied_staged_inputs_dir),
        align_config_path=_pasa_update_align_config(copied_staged_inputs_dir),
        annot_compare_config_path=_pasa_update_annot_compare_config(copied_staged_inputs_dir),
        database_path=_pasa_update_database(copied_staged_inputs_dir),
        source_pasa_results_dir=pasa_results_dir,
        source_evm_results_dir=evm_results_dir,
        notes=(
            "The staged PASA-update inputs preserve the original PASA database state together with the final sorted EVM annotation.",
        ),
    )
    round_assets: list[PasaGeneModelUpdateRoundResult] = []
    for copied_update_dir in copied_update_dirs:
        update_manifest = _read_json(_manifest_path(copied_update_dir, "Copied PASA update round"))
        relative_outputs = update_manifest.get("relative_outputs", {})
        round_assets.append(
            PasaGeneModelUpdateRoundResult(
                workspace_dir=copied_update_dir,
                round_index=int(update_manifest["round_index"]),
                loaded_annotations_gff3_path=require_path(
                    copied_update_dir / str(relative_outputs["loaded_annotations_snapshot"]),
                    "Copied PASA loaded-annotation snapshot",
                ),
                updated_gff3_path=require_path(
                    copied_update_dir / str(relative_outputs["updated_gff3"]),
                    "Copied PASA updated GFF3",
                ),
                updated_bed_path=(
                    require_path(
                        copied_update_dir / str(relative_outputs["updated_bed"]),
                        "Copied PASA updated BED",
                    )
                    if relative_outputs.get("updated_bed")
                    else None
                ),
                current_annotations_gff3_path=require_path(
                    copied_update_dir / str(relative_outputs["current_annotations_gff3"]),
                    "Copied PASA current annotations GFF3",
                ),
                input_bundle=staged_asset,
                notes=(
                    "This copied round asset preserves the per-round promoted current annotations path.",
                ),
            )
        )

    result_bundle = PasaGeneModelUpdateResultBundle(
        result_dir=out_dir,
        staged_inputs_dir=copied_staged_inputs_dir,
        load_round_root=copied_load_root,
        update_round_root=copied_update_root,
        finalized_dir=copied_finalized_dir,
        final_updated_gff3_path=final_raw_gff3,
        final_removed_gff3_path=final_removed_gff3,
        final_sorted_gff3_path=final_sorted_gff3,
        manifest_path=out_dir / "run_manifest.json",
        staged_inputs=staged_asset,
        update_rounds=tuple(round_assets),
        notes=(
            "This bundle stops at PASA post-EVM update rounds and does not proceed into repeat filtering or later downstream stages.",
        ),
    )

    manifest = {
        "workflow": PASA_UPDATE_WORKFLOW_NAME,
        "assumptions": [
            "This milestone consumes the existing PASA and EVM result bundles directly instead of rebuilding transcript, protein, prediction, or consensus stages.",
            "The notes require at least two PASA update rounds to improve UTR and alternative-transcript incorporation; the workflow keeps those rounds explicit.",
            "The annotCompare config is supplied as an external template because the earlier PASA bundle does not preserve it.",
            "This milestone stops after PASA post-EVM update GFF3 cleanup and sorting; repeat filtering, BUSCO, EggNOG, AGAT, and table2asn remain deferred.",
        ],
        "source_bundles": {
            "pasa_results": str(pasa_results_dir),
            "evm_results": str(evm_results_dir),
        },
        "copied_source_manifests": {
            "pasa": str(copied_pasa_manifest),
            "evm": str(copied_evm_manifest),
        },
        "copied_stage_dirs": {
            "staged_inputs": str(copied_staged_inputs_dir),
            "load_rounds": str(copied_load_root),
            "update_rounds": str(copied_update_root),
            "finalized": str(copied_finalized_dir),
        },
        "outputs": {
            "final_updated_gff3": str(final_raw_gff3),
            "final_removed_gff3": str(final_removed_gff3),
            "final_sorted_gff3": str(final_sorted_gff3),
        },
        "assets": _as_json_compatible({"pasa_gene_model_update_bundle": asdict(result_bundle)}),
        "load_round_manifests": [
            _read_json(_manifest_path(path, f"Copied PASA load round {index + 1}"))
            for index, path in enumerate(copied_load_dirs)
        ],
        "update_round_manifests": [
            _read_json(_manifest_path(path, f"Copied PASA update round {index + 1}"))
            for index, path in enumerate(copied_update_dirs)
        ],
        "finalized_manifest": _read_json(_manifest_path(copied_finalized_dir, "Copied PASA finalized outputs")),
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir.from_local_sync(str(out_dir))


__all__ = [
    "collect_pasa_results",
    "collect_pasa_update_results",
    "combine_trinity_fastas",
    "finalize_pasa_update_outputs",
    "pasa_accession_extract",
    "pasa_align_assemble",
    "pasa_create_sqlite_db",
    "pasa_load_current_annotations",
    "pasa_seqclean",
    "pasa_update_gene_models",
    "prepare_pasa_update_inputs",
]
