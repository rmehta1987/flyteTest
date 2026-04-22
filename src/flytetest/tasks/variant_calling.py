"""GATK4 variant calling task implementations for Milestone A."""

from __future__ import annotations

from pathlib import Path

from flyte.io import File

from flytetest.config import (
    variant_calling_env,
    project_mkdtemp,
    require_path,
    run_tool,
)
from flytetest.manifest_envelope import build_manifest_envelope
from flytetest.manifest_io import write_json as _write_json


# Source of truth for the registry-manifest contract: every key this module
# writes under manifest["outputs"].  Grows as each task lands.
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "sequence_dict",
    "feature_index",
)


@variant_calling_env.task
def create_sequence_dictionary(
    reference_fasta: File,
    gatk_sif: str = "",
) -> File:
    """Emit a GATK sequence dictionary (.dict) next to the reference FASTA."""
    ref_path = require_path(Path(reference_fasta.download_sync()),
                            "Reference genome FASTA")
    out_dir = project_mkdtemp("gatk_seqdict_")
    dict_path = out_dir / f"{ref_path.stem}.dict"

    cmd = ["gatk", "CreateSequenceDictionary",
           "-R", str(ref_path), "-O", str(dict_path)]
    bind_paths = [ref_path.parent, out_dir]
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

    require_path(dict_path, "GATK CreateSequenceDictionary output")

    manifest = build_manifest_envelope(
        stage="create_sequence_dictionary",
        assumptions=[
            "Reference FASTA is readable and has no pre-existing "
            ".dict that would conflict; GATK overwrites -O when run.",
        ],
        inputs={"reference_fasta": str(ref_path)},
        outputs={"sequence_dict": str(dict_path)},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return File(path=str(dict_path))


@variant_calling_env.task
def index_feature_file(
    vcf: File,
    gatk_sif: str = "",
) -> File:
    """Emit a GATK4 feature-file index (.idx or .tbi) next to a VCF/GVCF."""
    vcf_path = require_path(Path(vcf.download_sync()),
                            "VCF/GVCF input for IndexFeatureFile")
    out_dir = project_mkdtemp("gatk_index_")

    if vcf_path.suffix == ".gz":
        expected_index = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
    else:
        expected_index = vcf_path.with_suffix(vcf_path.suffix + ".idx")

    cmd = ["gatk", "IndexFeatureFile", "-I", str(vcf_path)]
    bind_paths = [vcf_path.parent, out_dir]
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

    require_path(expected_index, "GATK IndexFeatureFile output index")

    manifest = build_manifest_envelope(
        stage="index_feature_file",
        assumptions=[
            "VCF is readable; GATK writes the index next to the VCF.",
        ],
        inputs={"vcf": str(vcf_path)},
        outputs={"feature_index": str(expected_index)},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return File(path=str(expected_index))
