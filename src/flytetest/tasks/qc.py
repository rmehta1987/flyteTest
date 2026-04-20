"""QC task implementations for the RNA-seq entry workflow.

This module currently wraps the FastQC boundary at the start of the existing
RNA-seq QC and quantification pipeline. Tool-level command and input/output
expectations follow `docs/tool_refs/fastqc.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import project_mkdtemp, require_path, rnaseq_qc_quant_env, run_tool


# Source of truth for the registry-manifest contract: every key this module writes under manifest["outputs"].
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "qc_dir",
)


@rnaseq_qc_quant_env.task
def fastqc(left: File, right: File, fastqc_sif: str = "") -> Dir:
    """Run FastQC on the paired-end reads that anchor the RNA-seq QC stage.

    Manifest keys written to run_manifest.json: qc_dir.
    """
    left_path = require_path(Path(left.download_sync()), "Read 1 FASTQ")
    right_path = require_path(Path(right.download_sync()), "Read 2 FASTQ")
    out_dir = project_mkdtemp("fastqc_") / "qc"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        ["fastqc", "--quiet", str(left_path), str(right_path), "--outdir", str(out_dir)],
        fastqc_sif,
        [left_path.parent, right_path.parent, out_dir.parent],
    )
    manifest = {
        "stage": "fastqc",
        "inputs": {
            "left": str(left_path),
            "right": str(right_path),
            "fastqc_sif": fastqc_sif,
        },
        "outputs": {
            "qc_dir": str(out_dir),
        },
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))
