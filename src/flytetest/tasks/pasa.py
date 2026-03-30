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
    PASA_WORKFLOW_NAME,
    RESULTS_ROOT,
    pasa_env,
    require_path,
    run_tool,
)
from flytetest.types import (
    CombinedTrinityTranscriptAsset,
    PasaAlignmentAssemblyResult,
    PasaCleanedTranscriptAsset,
    PasaSqliteConfigAsset,
    ReferenceGenome,
    StringTieAssemblyResult,
    TrinityDeNovoTranscriptAsset,
    TrinityGenomeGuidedAssemblyResult,
)


def _as_json_compatible(value: Any) -> Any:
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


def _stringtie_gtf(stringtie_dir: Path) -> Path:
    return require_path(stringtie_dir / "transcripts.gtf", "StringTie transcripts GTF")


def _stringtie_abundance(stringtie_dir: Path) -> Path | None:
    candidate = stringtie_dir / "gene_abund.tab"
    if candidate.exists():
        return candidate
    return None


def _seqclean_clean_fasta(seqclean_dir: Path) -> Path:
    clean_candidates = sorted(seqclean_dir.glob("*.clean"))
    if len(clean_candidates) == 1:
        return clean_candidates[0]
    raise FileNotFoundError(f"seqclean output FASTA not found under {seqclean_dir}")


def _pasa_config_path(config_dir: Path) -> Path:
    return require_path(config_dir / "pasa.alignAssembly.config", "PASA align/assemble config")


def _sqlite_db_path(config_dir: Path) -> Path:
    candidates = sorted(
        path
        for path in config_dir.iterdir()
        if path.is_file() and (path.suffix in {".sqlite", ".db"} or path.name.endswith(".sqlite"))
    )
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single SQLite database file under {config_dir}")


def _first_existing(directory: Path, suffixes: tuple[str, ...], prefixes: tuple[str, ...]) -> Path | None:
    for prefix in prefixes:
        for suffix in suffixes:
            candidate = directory / f"{prefix}{suffix}"
            if candidate.exists():
                return candidate
    return None


def _pasa_output_prefixes(database_name: str) -> tuple[str, ...]:
    stem = Path(database_name).stem
    if stem == database_name:
        return (database_name,)
    return (database_name, stem)


def _pasa_assemblies_fasta(pasa_dir: Path, database_name: str) -> Path | None:
    return _first_existing(pasa_dir, (".assemblies.fasta",), _pasa_output_prefixes(database_name))


def _pasa_assemblies_gff3(pasa_dir: Path, database_name: str) -> Path | None:
    return _first_existing(
        pasa_dir,
        (".pasa_assemblies.gff3", ".assemblies.gff3"),
        _pasa_output_prefixes(database_name),
    )


def _pasa_assemblies_gtf(pasa_dir: Path, database_name: str) -> Path | None:
    return _first_existing(
        pasa_dir,
        (".pasa_assemblies.gtf", ".assemblies.gtf"),
        _pasa_output_prefixes(database_name),
    )


def _pasa_alt_splicing_support(pasa_dir: Path, database_name: str) -> Path | None:
    return _first_existing(
        pasa_dir,
        (".alt_splicing_supporting_evidence.txt",),
        _pasa_output_prefixes(database_name),
    )


def _pasa_polyasites_fasta(pasa_dir: Path, database_name: str) -> Path | None:
    return _first_existing(
        pasa_dir,
        (".polyAsites.fasta",),
        _pasa_output_prefixes(database_name),
    )


def _sample_id_from_transcript_evidence(results_dir: Path) -> str:
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
    denovo_trinity_fasta_path: str = "",
) -> File:
    gg_path = require_path(Path(genome_guided_trinity_fasta.download_sync()), "Genome-guided Trinity FASTA")
    denovo_path = require_path(Path(denovo_trinity_fasta_path), "De novo Trinity FASTA") if denovo_trinity_fasta_path else None

    out_dir = Path(tempfile.mkdtemp(prefix="pasa_combined_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    combined_path = out_dir / "trinity_transcripts.fa"

    with combined_path.open("wb") as handle:
        for input_path in (denovo_path, gg_path):
            if input_path is None:
                continue
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
    pasa_sif: str = "",
    pasa_aligners: str = "blat,gmap,minimap2",
    pasa_cpu: int = 4,
    pasa_max_intron_length: int = 100000,
    tdn_accs_path: str = "",
) -> Dir:
    genome_path = require_path(Path(genome.download_sync()), "Reference genome FASTA")
    cleaned_dir = require_path(Path(cleaned_transcripts.download_sync()), "seqclean output directory")
    clean_fasta_path = _seqclean_clean_fasta(cleaned_dir)
    unclean_transcripts_path = require_path(Path(unclean_transcripts.download_sync()), "Combined Trinity transcript FASTA")
    stringtie_gtf_path = require_path(Path(stringtie_gtf.download_sync()), "StringTie transcripts GTF")
    config_dir = require_path(Path(pasa_config.download_sync()), "PASA config directory")
    config_path = _pasa_config_path(config_dir)
    accession_path = require_path(Path(tdn_accs_path), "PASA de novo accession list") if tdn_accs_path else None

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
    ]
    if accession_path is not None:
        cmd.extend(["--TDN", str(accession_path)])

    bind_paths = [
        genome_path.parent,
        cleaned_dir,
        unclean_transcripts_path.parent,
        stringtie_gtf_path.parent,
        config_dir,
        out_dir,
    ]
    if accession_path is not None:
        bind_paths.append(accession_path.parent)

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
    sample_id: str = "sample",
    trinity_denovo_fasta_path: str = "",
    tdn_accs_path: str = "",
) -> Dir:
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

    copied_accession_path: Path | None = None
    if tdn_accs_path:
        accession_path = require_path(Path(tdn_accs_path), "PASA de novo accession list")
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
    denovo_input_path = (
        require_path(Path(trinity_denovo_fasta_path), "De novo Trinity FASTA")
        if trinity_denovo_fasta_path
        else None
    )
    denovo_asset = (
        TrinityDeNovoTranscriptAsset(
            fasta_path=denovo_input_path,
            notes=(
                "This de novo Trinity FASTA is an optional external input because de novo Trinity is not yet implemented in FLyteTest.",
            ),
        )
        if denovo_input_path is not None
        else None
    )
    combined_asset = CombinedTrinityTranscriptAsset(
        fasta_path=copied_combined_path,
        genome_guided_transcripts=genome_guided_asset,
        de_novo_transcripts=denovo_asset,
        notes=(
            "The combined transcript FASTA follows the note order: de novo Trinity first when provided, then Trinity-GG.",
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
        "assumptions": [
            "This milestone consumes the transcript evidence bundle produced by transcript_evidence_generation, specifically trinity_gg/ and stringtie/ outputs.",
            "A user-supplied PASA alignAssembly template is required because the exact PASA config file content is environment-specific in the notes.",
            "The SQLite database file is created locally with Python's sqlite3 library, then referenced from the rewritten PASA config template.",
            "The PASA align/assemble invocation follows the note flags: --ALIGNERS blat,gmap,minimap2, --MAX_INTRON_LENGTH 100000, --create, --run, --ALT_SPLICE, --CPU, --stringent_alignment_overlap 30.0, and -T.",
            "If no de novo Trinity FASTA is provided, the workflow combines only the genome-guided Trinity FASTA and omits --TDN. This is an explicit simplification because FLyteTest does not yet generate de novo Trinity transcripts.",
            "TransDecoder, Exonerate, BRAKER3, and EVM are not part of this PASA milestone.",
        ],
        "outputs": {
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
            "tdn_accs": str(copied_accession_path) if copied_accession_path else None,
            "source_stringtie_gtf": str(stringtie_asset.transcript_gtf_path),
        },
        "assets": _as_json_compatible(
            {
                "reference_genome": asdict(reference_asset),
                "trinity_genome_guided": asdict(genome_guided_asset),
                "trinity_de_novo": asdict(denovo_asset) if denovo_asset else None,
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
