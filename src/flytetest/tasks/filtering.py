"""Repeat-filtering and cleanup tasks for the post-PASA FLyteTest milestone.

This module starts from the PASA-updated annotation boundary, converts an
external RepeatMasker `.out` file into interval data, runs the gffread and
funannotate cleanup steps, and collects stable final repeat-filtered outputs
before functional annotation.

Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
input/output expectations follow the tool references under `docs/tool_refs/`
(notably `repeatmasker.md`, `gffread.md`, and `funannotate.md`).
Those refs match the repeat-filtering slices implemented here.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from flyte.io import Dir, File

from flytetest.config import (
    REPEAT_FILTER_RESULTS_PREFIX,
    REPEAT_FILTER_WORKFLOW_NAME,
    RESULTS_ROOT,
    project_mkdtemp,
    repeat_filter_env,
    require_path,
    run_tool,
)
from flytetest.gff3 import attribute_values as _attribute_values, parse_attributes as _parse_attributes
from flytetest.manifest_io import (
    as_json_compatible as _as_json_compatible,
    copy_file as _copy_file,
    copy_tree as _copy_tree,
    read_json as _read_json,
    write_json as _write_json,
)


def _manifest_path(directory: Path, label: str) -> Path:
    """Resolve the manifest file expected within a stage output directory."""
    return require_path(directory / "run_manifest.json", f"{label} manifest")


def _pasa_update_sorted_gff3(results_dir: Path) -> Path:
    """Resolve the PASA-sorted GFF3 annotation file that feeds repeat filtering."""
    return require_path(results_dir / "post_pasa_updates.sort.gff3", "PASA-updated sorted GFF3")


def _pasa_update_reference_genome(results_dir: Path) -> Path:
    """Resolve the reference genome FASTA from the PASA result bundle."""
    return require_path(
        results_dir / "staged_inputs" / "reference" / "genome.fa",
        "PASA-update reference genome FASTA",
    )


def _repeatmasker_gff3_path(results_dir: Path) -> Path:
    """Resolve the RepeatMasker GFF3 file converted from the `.out` format."""
    return require_path(results_dir / "repeatmasker.gff3", "RepeatMasker-derived GFF3")


def _repeatmasker_bed_path(results_dir: Path) -> Path:
    """Resolve the RepeatMasker BED interval file (three-column format)."""
    return require_path(results_dir / "repeatmasker.bed", "RepeatMasker BED")


def _gffread_protein_fasta(results_dir: Path) -> Path:
    """Resolve the primary protein FASTA emitted by gffread during extraction."""
    candidates = sorted(results_dir.glob("*.proteins.fa"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single gffread proteins FASTA under {results_dir}")


def _sanitized_protein_fasta(results_dir: Path) -> Path:
    """Resolve the period-stripped protein FASTA used for repeat diamond blasting."""
    candidates = sorted(results_dir.glob("*.proteins.no_periods.fa"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(
        f"Unable to resolve a single period-stripped proteins FASTA under {results_dir}"
    )


def _clean_gff3_path(results_dir: Path) -> Path:
    """Resolve the clean GFF3 annotation emitted by the funannotate overlap filter."""
    candidates = sorted(results_dir.glob("*.clean.gff3"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single clean GFF3 under {results_dir}")


def _models_to_remove_path(results_dir: Path) -> Path:
    """Resolve the overlap-removal list emitted by funannotate RemoveBadModels."""
    exact_candidates = [
        results_dir / "genome.repeats.to.remove.gff3",
        results_dir / "genome.repeats.to.remove.gff",
    ]
    for candidate in exact_candidates:
        if candidate.exists():
            return candidate

    glob_candidates = sorted(results_dir.glob("*.repeats.to.remove.gff*"))
    if len(glob_candidates) == 1:
        return glob_candidates[0]
    raise FileNotFoundError(
        f"Unable to resolve the overlap-removal list emitted by funannotate under {results_dir}"
    )


def _filtered_gff3_path(results_dir: Path) -> Path:
    """Resolve the single filtered GFF3 produced by a deterministic removal step."""
    candidates = sorted(path for path in results_dir.glob("*.gff3") if path.name != "run_manifest.json")
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Unable to resolve a single filtered GFF3 under {results_dir}")


def _repeat_blast_hits_path(results_dir: Path) -> Path:
    """Resolve the repeat blast hits file emitted by funannotate RepeatBlast."""
    return require_path(results_dir / "repeat.dmnd.blast.txt", "repeat.dmnd blast hits")


def _write_repeatmasker_bed(gff3_path: Path, bed_path: Path) -> Path:
    """Extract and write a three-column BED file from RepeatMasker GFF3."""
    bed_lines: list[str] = []
    for raw_line in gff3_path.read_text().splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        fields = raw_line.split("\t")
        if len(fields) != 9:
            continue
        # The notes use `awk '{print $1 "\t" $4 "\t" $5}'`, so this repo
        # preserves that exact three-column extraction instead of normalizing
        # coordinates to stricter BED conventions.
        bed_lines.append(f"{fields[0]}\t{fields[3]}\t{fields[4]}")
    bed_path.write_text("\n".join(bed_lines) + ("\n" if bed_lines else ""))
    return bed_path


def _strip_periods_from_fasta(input_fasta: Path, output_fasta: Path) -> Path:
    """Remove periods from protein FASTA sequences while preserving headers."""
    cleaned_lines: list[str] = []
    for raw_line in input_fasta.read_text().splitlines():
        if raw_line.startswith(">"):
            cleaned_lines.append(raw_line)
            continue
        cleaned_lines.append(raw_line.replace(".", ""))
    output_fasta.write_text("\n".join(cleaned_lines) + ("\n" if cleaned_lines else ""))
    return output_fasta


def _remove_exact_feature_lines(annotation_gff3: Path, removal_list: Path, output_gff3: Path) -> Path:
    """Remove exact feature lines matching entries in a removal list from GFF3."""
    removal_lines = {
        line.rstrip("\n")
        for line in removal_list.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    kept_lines = [
        raw_line
        for raw_line in annotation_gff3.read_text().splitlines()
        if raw_line.startswith("#") or raw_line not in removal_lines
    ]
    output_gff3.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""))
    return output_gff3


def _remove_repeat_blast_ids(annotation_gff3: Path, repeat_blast_hits: Path, output_gff3: Path) -> Path:
    """Remove blast-hit gene models from GFF3 using ID and Parent attribute filtering."""
    blast_ids = {
        line.split()[0]
        for line in repeat_blast_hits.read_text().splitlines()
        if line.strip()
    }
    translated_ids = {identifier.replace("evm.model", "evm.TU") for identifier in blast_ids}

    kept_lines: list[str] = []
    for raw_line in annotation_gff3.read_text().splitlines():
        if not raw_line or raw_line.startswith("#"):
            kept_lines.append(raw_line)
            continue
        fields = raw_line.split("\t")
        if len(fields) != 9:
            kept_lines.append(raw_line)
            continue
        attributes = _parse_attributes(fields[8])
        feature_ids = set(_attribute_values(attributes, "ID"))
        parent_ids = set(_attribute_values(attributes, "Parent"))
        if feature_ids & blast_ids:
            continue
        if parent_ids & blast_ids:
            continue
        if feature_ids & translated_ids:
            continue
        kept_lines.append(raw_line)

    output_gff3.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""))
    return output_gff3


@repeat_filter_env.task
def repeatmasker_out_to_bed(
    repeatmasker_out: File,
    rmout_to_gff3_script: str = "rmOutToGFF3.pl",
    repeat_filter_sif: str = "",
) -> Dir:
    """Convert a RepeatMasker `.out` file into a downstream GFF3 and BED pair."""
    repeatmasker_out_path = require_path(Path(repeatmasker_out.download_sync()), "RepeatMasker .out file")
    out_dir = project_mkdtemp("repeatmasker_convert_") / "repeatmasker"
    out_dir.mkdir(parents=True, exist_ok=True)

    staged_out_path = _copy_file(repeatmasker_out_path, out_dir / repeatmasker_out_path.name)
    converted_gff3 = out_dir / "repeatmasker.gff3"
    run_tool(
        ["perl", rmout_to_gff3_script, str(staged_out_path)],
        repeat_filter_sif,
        [out_dir],
        cwd=out_dir,
        stdout_path=converted_gff3,
    )
    bed_path = _write_repeatmasker_bed(converted_gff3, out_dir / "repeatmasker.bed")

    manifest = {
        "stage": "repeatmasker_out_to_bed",
        "assumptions": [
            "Native RepeatMasker runs consume a genome FASTA plus a configured repeat source and emit `.masked`, `.out`, `.tbl`, and optional GFF outputs.",
            "This FLyteTest task is only the downstream adapter for an already generated RepeatMasker `.out` file; running RepeatMasker itself remains upstream of this milestone.",
            "The GFF3 conversion uses the RepeatMasker utility `rmOutToGFF3.pl`.",
            "The BED output preserves the existing BRaker/EVM notes' raw `awk '{print $1 \"\\t\" $4 \"\\t\" $5}'` extraction, so coordinates are copied directly from the converted GFF3 instead of being normalized further.",
        ],
        "inputs": {
            "repeatmasker_out": str(repeatmasker_out_path),
            "rmout_to_gff3_script": rmout_to_gff3_script,
            "repeat_filter_sif": repeat_filter_sif,
        },
        "outputs": {
            "staged_repeatmasker_out": str(staged_out_path),
            "repeatmasker_gff3": str(converted_gff3),
            "repeatmasker_bed": str(bed_path),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@repeat_filter_env.task
def gffread_proteins(
    annotation_gff3: File,
    genome_fasta: File,
    protein_output_stem: str = "annotation",
    gffread_binary: str = "gffread",
    repeat_filter_sif: str = "",
) -> Dir:
    """Extract protein sequences from GFF3 annotation and sanitize for repeat blasting."""
    annotation_path = require_path(Path(annotation_gff3.download_sync()), "Annotation GFF3")
    genome_path = require_path(Path(genome_fasta.download_sync()), "Reference genome FASTA")
    out_dir = project_mkdtemp("gffread_proteins_") / "proteins"
    out_dir.mkdir(parents=True, exist_ok=True)

    proteins_fasta = out_dir / f"{protein_output_stem}.proteins.fa"
    run_tool(
        [gffread_binary, "-y", str(proteins_fasta), "-g", str(genome_path), str(annotation_path)],
        repeat_filter_sif,
        [annotation_path.parent, genome_path.parent, out_dir],
    )
    sanitized_fasta = _strip_periods_from_fasta(
        proteins_fasta,
        out_dir / f"{protein_output_stem}.proteins.no_periods.fa",
    )

    manifest = {
        "stage": "gffread_proteins",
        "assumptions": [
            "The notes use `gffread -y ... -g genome.fa annotation.gff3` to derive proteins from the current annotation GFF3.",
            "The notes then remove periods from the emitted protein sequences before funannotate repeat blasting because downstream diamond parsing is sensitive to `.` residues.",
        ],
        "inputs": {
            "annotation_gff3": str(annotation_path),
            "genome_fasta": str(genome_path),
            "protein_output_stem": protein_output_stem,
            "gffread_binary": gffread_binary,
            "repeat_filter_sif": repeat_filter_sif,
        },
        "outputs": {
            "proteins_fasta": str(proteins_fasta),
            "sanitized_proteins_fasta": str(sanitized_fasta),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@repeat_filter_env.task
def funannotate_remove_bad_models(
    annotation_gff3: File,
    proteins_fasta: File,
    repeatmasker_bed: File,
    clean_output_name: str = "annotation.clean.gff3",
    funannotate_python: str = "python3",
    repeat_filter_sif: str = "",
    min_protlen: int = 50,
) -> Dir:
    """Run the funannotate overlap filter to identify repeat-overlapping gene models."""
    annotation_path = require_path(Path(annotation_gff3.download_sync()), "Annotation GFF3")
    proteins_path = require_path(Path(proteins_fasta.download_sync()), "Protein FASTA for overlap filtering")
    repeatmasker_bed_path = require_path(Path(repeatmasker_bed.download_sync()), "RepeatMasker BED")
    out_dir = project_mkdtemp("funannotate_overlap_") / "funannotate_overlap"
    out_dir.mkdir(parents=True, exist_ok=True)

    clean_gff3 = out_dir / clean_output_name
    blast_hits_path = out_dir / "repeat.dmnd.blast.txt"
    python_code = "\n".join(
        [
            "import funannotate.library as lib",
            f"lib.setupLogging({str('Find_bed_repeats.log')!r})",
            (
                "lib.RemoveBadModels("
                f"{str(proteins_path)!r}, "
                f"{str(annotation_path)!r}, "
                f"{min_protlen}, "
                f"{str(repeatmasker_bed_path)!r}, "
                f"{str(blast_hits_path.name)!r}, "
                f"{str('.')!r}, "
                "['overlap'], "
                f"{str(clean_gff3.name)!r}"
                ")"
            ),
        ]
    )
    run_tool(
        [funannotate_python, "-c", python_code],
        repeat_filter_sif,
        [annotation_path.parent, proteins_path.parent, repeatmasker_bed_path.parent, out_dir],
        cwd=out_dir,
    )
    removal_list = _models_to_remove_path(out_dir)

    manifest = {
        "stage": "funannotate_remove_bad_models",
        "assumptions": [
            "The notes show this boundary as a Python wrapper around `funannotate.library.RemoveBadModels` with `repeat_filter=['overlap']`, not as a documented standalone CLI command.",
            "This task therefore calls the library entry point through a deterministic local Python command and records that wrapper choice as an inference from the notes.",
            "The notes show inconsistent overlap-removal-list suffixes (`.gff3` in one place and `.gff` in another), so this task resolves either emitted filename and records the exact path in the manifest.",
        ],
        "inputs": {
            "annotation_gff3": str(annotation_path),
            "proteins_fasta": str(proteins_path),
            "repeatmasker_bed": str(repeatmasker_bed_path),
            "clean_output_name": clean_output_name,
            "funannotate_python": funannotate_python,
            "repeat_filter_sif": repeat_filter_sif,
            "min_protlen": min_protlen,
        },
        "outputs": {
            "clean_gff3": str(clean_gff3),
            "models_to_remove": str(removal_list),
            "repeat_blast_placeholder": str(blast_hits_path) if blast_hits_path.exists() else None,
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@repeat_filter_env.task
def remove_overlap_repeat_models(
    annotation_gff3: File,
    models_to_remove: File,
    output_name: str = "bed_repeats_removed.gff3",
) -> Dir:
    """Remove exact overlap-listed feature lines from the annotation GFF3."""
    annotation_path = require_path(Path(annotation_gff3.download_sync()), "Annotation GFF3")
    removal_path = require_path(Path(models_to_remove.download_sync()), "Overlap removal list")
    out_dir = project_mkdtemp("overlap_removed_") / "overlap_removed"
    out_dir.mkdir(parents=True, exist_ok=True)

    filtered_gff3 = _remove_exact_feature_lines(annotation_path, removal_path, out_dir / output_name)
    manifest = {
        "stage": "remove_overlap_repeat_models",
        "assumptions": [
            "The notes remove RepeatMasker-overlap models with a shell helper built around `grep -vFf` against the overlap-removal file emitted by funannotate.",
            "This task implements the same stage as a deterministic exact-line filter so the removed models remain inspectable without depending on shell-specific behavior.",
        ],
        "inputs": {
            "annotation_gff3": str(annotation_path),
            "models_to_remove": str(removal_path),
        },
        "outputs": {
            "filtered_gff3": str(filtered_gff3),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@repeat_filter_env.task
def funannotate_repeat_blast(
    proteins_fasta: File,
    funannotate_db_path: str,
    funannotate_python: str = "python3",
    repeat_filter_sif: str = "",
    repeat_blast_cpu: int = 1,
    repeat_blast_evalue: float = 1e-10,
) -> Dir:
    """Run the funannotate repeat-blasting stage against the repeats DIAMOND database."""
    proteins_path = require_path(Path(proteins_fasta.download_sync()), "Protein FASTA for repeat blasting")
    fundb_path = require_path(Path(funannotate_db_path), "funannotate database root")
    out_dir = project_mkdtemp("repeat_blast_") / "repeat_blast"
    out_dir.mkdir(parents=True, exist_ok=True)

    blast_hits_path = out_dir / "repeat.dmnd.blast.txt"
    python_code = "\n".join(
        [
            "import funannotate.library as lib",
            f"lib.setupLogging({str('blast_db.log')!r})",
            (
                "lib.RepeatBlast("
                f"{str(proteins_path)!r}, "
                f"{repeat_blast_cpu}, "
                f"{repeat_blast_evalue}, "
                f"{str(fundb_path)!r}, "
                f"{str('.')!r}, "
                f"{str(blast_hits_path.name)!r}"
                ")"
            ),
        ]
    )
    run_tool(
        [funannotate_python, "-c", python_code],
        repeat_filter_sif,
        [proteins_path.parent, fundb_path, out_dir],
        cwd=out_dir,
    )

    manifest = {
        "stage": "funannotate_repeat_blast",
        "assumptions": [
            "The notes show repeat blasting as a Python wrapper around `funannotate.library.RepeatBlast` rather than a fully specified standalone command line.",
            "This task therefore treats `funannotate_db_path` as an explicit local runtime requirement and records the library-wrapper invocation as an inferred implementation detail.",
        ],
        "inputs": {
            "proteins_fasta": str(proteins_path),
            "funannotate_db_path": str(fundb_path),
            "funannotate_python": funannotate_python,
            "repeat_filter_sif": repeat_filter_sif,
            "repeat_blast_cpu": repeat_blast_cpu,
            "repeat_blast_evalue": repeat_blast_evalue,
        },
        "outputs": {
            "repeat_blast_hits": str(_repeat_blast_hits_path(out_dir)),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@repeat_filter_env.task
def remove_repeat_blast_hits(
    annotation_gff3: File,
    repeat_blast_results: Dir,
    output_name: str = "all_repeats_removed.gff3",
) -> Dir:
    """Remove repeat-blast-hit gene models from GFF3 using attribute filtering rules."""
    annotation_path = require_path(Path(annotation_gff3.download_sync()), "Annotation GFF3")
    repeat_blast_dir = require_path(Path(repeat_blast_results.download_sync()), "Repeat blast results directory")
    blast_hits_path = _repeat_blast_hits_path(repeat_blast_dir)
    out_dir = project_mkdtemp("blast_removed_") / "blast_removed"
    out_dir.mkdir(parents=True, exist_ok=True)

    filtered_gff3 = _remove_repeat_blast_ids(annotation_path, blast_hits_path, out_dir / output_name)
    manifest = {
        "stage": "remove_repeat_blast_hits",
        "assumptions": [
            "The notes remove repeat-blast hits with a shell helper that filters `Parent=` and `ID=` attributes, then repeats the `ID=` filter after translating `evm.model` identifiers to `evm.TU`.",
            "This task implements that shell helper as a deterministic attribute-aware transform so the removal logic remains inspectable and testable.",
        ],
        "inputs": {
            "annotation_gff3": str(annotation_path),
            "repeat_blast_results": str(repeat_blast_dir),
            "repeat_blast_hits": str(blast_hits_path),
        },
        "outputs": {
            "filtered_gff3": str(filtered_gff3),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


@repeat_filter_env.task
def collect_repeat_filter_results(
    pasa_update_results: Dir,
    repeatmasker_conversion: Dir,
    initial_proteins: Dir,
    overlap_filter: Dir,
    overlap_removed: Dir,
    bed_filtered_proteins: Dir,
    repeat_blast: Dir,
    blast_removed: Dir,
    final_proteins: Dir,
) -> Dir:
    """Collect repeat-filtering stages into a unified manifest-bearing results bundle."""
    pasa_update_dir = require_path(Path(pasa_update_results.download_sync()), "PASA update results directory")
    repeatmasker_dir = require_path(Path(repeatmasker_conversion.download_sync()), "RepeatMasker conversion directory")
    initial_proteins_dir = require_path(Path(initial_proteins.download_sync()), "Initial gffread directory")
    overlap_filter_dir = require_path(Path(overlap_filter.download_sync()), "funannotate overlap directory")
    overlap_removed_dir = require_path(Path(overlap_removed.download_sync()), "Overlap-removed directory")
    bed_filtered_proteins_dir = require_path(
        Path(bed_filtered_proteins.download_sync()),
        "Bed-filtered proteins directory",
    )
    repeat_blast_dir = require_path(Path(repeat_blast.download_sync()), "Repeat blast directory")
    blast_removed_dir = require_path(Path(blast_removed.download_sync()), "Blast-removed directory")
    final_proteins_dir = require_path(Path(final_proteins.download_sync()), "Final proteins directory")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{REPEAT_FILTER_RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_repeatmasker_dir = _copy_tree(repeatmasker_dir, out_dir / "repeatmasker")
    copied_initial_proteins_dir = _copy_tree(initial_proteins_dir, out_dir / "initial_proteins")
    copied_overlap_filter_dir = _copy_tree(overlap_filter_dir, out_dir / "overlap_filter")
    copied_overlap_removed_dir = _copy_tree(overlap_removed_dir, out_dir / "overlap_removed")
    copied_bed_filtered_proteins_dir = _copy_tree(
        bed_filtered_proteins_dir,
        out_dir / "bed_filtered_proteins",
    )
    copied_repeat_blast_dir = _copy_tree(repeat_blast_dir, out_dir / "repeat_blast")
    copied_blast_removed_dir = _copy_tree(blast_removed_dir, out_dir / "blast_removed")
    copied_final_proteins_dir = _copy_tree(final_proteins_dir, out_dir / "final_proteins")

    reference_dir = out_dir / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    copied_genome = _copy_file(_pasa_update_reference_genome(pasa_update_dir), reference_dir / "genome.fa")

    source_boundary_dir = out_dir / "source_boundary"
    source_boundary_dir.mkdir(parents=True, exist_ok=True)
    copied_post_pasa_gff3 = _copy_file(
        _pasa_update_sorted_gff3(pasa_update_dir),
        source_boundary_dir / "post_pasa_updates.sort.gff3",
    )

    source_manifests_dir = out_dir / "source_manifests"
    source_manifests_dir.mkdir(parents=True, exist_ok=True)
    copied_pasa_manifest = _copy_file(
        _manifest_path(pasa_update_dir, "PASA update bundle"),
        source_manifests_dir / "pasa_update.run_manifest.json",
    )

    copied_repeatmasker_gff3 = _copy_file(
        _repeatmasker_gff3_path(copied_repeatmasker_dir),
        out_dir / "repeatmasker.gff3",
    )
    copied_repeatmasker_bed = _copy_file(
        _repeatmasker_bed_path(copied_repeatmasker_dir),
        out_dir / "repeatmasker.bed",
    )
    copied_initial_proteins = _copy_file(
        _gffread_protein_fasta(copied_initial_proteins_dir),
        out_dir / "post_pasa_updates.proteins.fa",
    )
    copied_initial_sanitized_proteins = _copy_file(
        _sanitized_protein_fasta(copied_initial_proteins_dir),
        out_dir / "post_pasa_updates.proteins.no_periods.fa",
    )
    copied_clean_gff3 = _copy_file(
        _clean_gff3_path(copied_overlap_filter_dir),
        out_dir / "post_pasa_updates.clean.gff3",
    )
    copied_models_to_remove = _copy_file(
        _models_to_remove_path(copied_overlap_filter_dir),
        out_dir / _models_to_remove_path(copied_overlap_filter_dir).name,
    )
    copied_overlap_removed_gff3 = _copy_file(
        _filtered_gff3_path(copied_overlap_removed_dir),
        out_dir / "bed_repeats_removed.gff3",
    )
    copied_bed_filtered_proteins = _copy_file(
        _gffread_protein_fasta(copied_bed_filtered_proteins_dir),
        out_dir / "bed_repeats_removed.proteins.fa",
    )
    copied_bed_filtered_sanitized = _copy_file(
        _sanitized_protein_fasta(copied_bed_filtered_proteins_dir),
        out_dir / "bed_repeats_removed.proteins.no_periods.fa",
    )
    copied_repeat_blast_hits = _copy_file(
        _repeat_blast_hits_path(copied_repeat_blast_dir),
        out_dir / "repeat.dmnd.blast.txt",
    )
    copied_all_repeats_removed_gff3 = _copy_file(
        _filtered_gff3_path(copied_blast_removed_dir),
        out_dir / "all_repeats_removed.gff3",
    )
    copied_final_proteins = _copy_file(
        _gffread_protein_fasta(copied_final_proteins_dir),
        out_dir / "all_repeats_removed.proteins.fa",
    )
    copied_final_sanitized_proteins = _copy_file(
        _sanitized_protein_fasta(copied_final_proteins_dir),
        out_dir / "all_repeats_removed.proteins.no_periods.fa",
    )

    manifest = {
        "workflow": REPEAT_FILTER_WORKFLOW_NAME,
        "assumptions": [
            "This milestone starts from the PASA-updated sorted GFF3 boundary and a user-supplied RepeatMasker `.out` file; it does not run RepeatMasker itself.",
            "The notes show funannotate overlap filtering and repeat blasting through Python library wrappers, so this repo exposes those as explicit task boundaries and records the wrapper choice as inferred behavior.",
            "The overlap-removal and blast-hit-removal shell helpers in the notes are preserved as deterministic local file transforms here instead of opaque shell scripts.",
            "This milestone stops after repeat-filtered GFF3 and protein FASTA creation; BUSCO, EggNOG, AGAT, and `table2asn` remain deferred.",
        ],
        "source_bundle": {
            "pasa_update_results": str(pasa_update_dir),
        },
        "copied_source_manifests": {
            "pasa_update": str(copied_pasa_manifest),
        },
        "copied_stage_dirs": {
            "repeatmasker": str(copied_repeatmasker_dir),
            "initial_proteins": str(copied_initial_proteins_dir),
            "overlap_filter": str(copied_overlap_filter_dir),
            "overlap_removed": str(copied_overlap_removed_dir),
            "bed_filtered_proteins": str(copied_bed_filtered_proteins_dir),
            "repeat_blast": str(copied_repeat_blast_dir),
            "blast_removed": str(copied_blast_removed_dir),
            "final_proteins": str(copied_final_proteins_dir),
        },
        "inputs": {
            "reference_genome": str(copied_genome),
            "post_pasa_sorted_gff3": str(copied_post_pasa_gff3),
        },
        "outputs": {
            "repeatmasker_gff3": str(copied_repeatmasker_gff3),
            "repeatmasker_bed": str(copied_repeatmasker_bed),
            "initial_proteins_fasta": str(copied_initial_proteins),
            "initial_sanitized_proteins_fasta": str(copied_initial_sanitized_proteins),
            "clean_gff3": str(copied_clean_gff3),
            "models_to_remove": str(copied_models_to_remove),
            "bed_repeats_removed_gff3": str(copied_overlap_removed_gff3),
            "bed_filtered_proteins_fasta": str(copied_bed_filtered_proteins),
            "bed_filtered_sanitized_proteins_fasta": str(copied_bed_filtered_sanitized),
            "repeat_blast_hits": str(copied_repeat_blast_hits),
            "all_repeats_removed_gff3": str(copied_all_repeats_removed_gff3),
            "final_proteins_fasta": str(copied_final_proteins),
            "final_sanitized_proteins_fasta": str(copied_final_sanitized_proteins),
        },
        "stage_manifests": {
            "repeatmasker": _read_json(_manifest_path(copied_repeatmasker_dir, "Copied RepeatMasker conversion")),
            "initial_proteins": _read_json(_manifest_path(copied_initial_proteins_dir, "Copied initial proteins")),
            "overlap_filter": _read_json(_manifest_path(copied_overlap_filter_dir, "Copied overlap filter")),
            "overlap_removed": _read_json(_manifest_path(copied_overlap_removed_dir, "Copied overlap removal")),
            "bed_filtered_proteins": _read_json(
                _manifest_path(copied_bed_filtered_proteins_dir, "Copied bed-filtered proteins")
            ),
            "repeat_blast": _read_json(_manifest_path(copied_repeat_blast_dir, "Copied repeat blast")),
            "blast_removed": _read_json(_manifest_path(copied_blast_removed_dir, "Copied blast removal")),
            "final_proteins": _read_json(_manifest_path(copied_final_proteins_dir, "Copied final proteins")),
        },
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return Dir(path=str(out_dir))


__all__ = [
    "collect_repeat_filter_results",
    "funannotate_remove_bad_models",
    "funannotate_repeat_blast",
    "gffread_proteins",
    "remove_overlap_repeat_models",
    "remove_repeat_blast_hits",
    "repeatmasker_out_to_bed",
]
