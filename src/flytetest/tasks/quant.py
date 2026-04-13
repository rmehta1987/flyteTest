"""Quantification tasks for the original FLyteTest RNA-seq workflow.

This module keeps the Salmon index, quantification, and collection boundaries
used by the compatibility entrypoint. Tool-level command and input/output
expectations follow `docs/tool_refs/salmon.md`.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import (
    RESULTS_PREFIX,
    RESULTS_ROOT,
    WORKFLOW_NAME,
    project_mkdtemp,
    require_path,
    rnaseq_qc_quant_env,
    run_tool,
)


@rnaseq_qc_quant_env.task
def salmon_index(ref: File, salmon_sif: str = "") -> Dir:
    """Build the Salmon index directory from the reference transcriptome."""
    ref_path = require_path(Path(ref.download_sync()), "Reference transcriptome")
    out_dir = project_mkdtemp("salmon_index_") / "index"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        ["salmon", "index", "-t", str(ref_path), "-i", str(out_dir)],
        salmon_sif,
        [ref_path.parent, out_dir.parent],
    )
    return Dir(path=str(out_dir))


@rnaseq_qc_quant_env.task
def salmon_quant(
    index: Dir,
    left: File,
    right: File,
    salmon_sif: str = "",
) -> Dir:
    """Quantify the paired-end reads against a prepared Salmon index."""
    index_path = require_path(Path(index.download_sync()), "Salmon index directory")
    left_path = require_path(Path(left.download_sync()), "Read 1 FASTQ")
    right_path = require_path(Path(right.download_sync()), "Read 2 FASTQ")
    out_dir = project_mkdtemp("salmon_quant_") / "quant"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        [
            "salmon",
            "quant",
            "-i",
            str(index_path),
            "-l",
            "A",
            "-1",
            str(left_path),
            "-2",
            str(right_path),
            "--validateMappings",
            "-o",
            str(out_dir),
        ],
        salmon_sif,
        [index_path.parent, left_path.parent, right_path.parent, out_dir.parent],
    )
    return Dir(path=str(out_dir))


@rnaseq_qc_quant_env.task
def collect_results(qc: Dir, quant: Dir) -> Dir:
    """Collect FastQC and Salmon outputs into the compatibility result bundle."""
    qc_path = require_path(Path(qc.download_sync()), "FastQC output directory")
    quant_path = require_path(Path(quant.download_sync()), "Salmon quantification directory")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path.cwd() / RESULTS_ROOT / f"{RESULTS_PREFIX}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    shutil.copytree(qc_path, out_dir / "qc", dirs_exist_ok=True)
    shutil.copytree(quant_path, out_dir / "quant", dirs_exist_ok=True)

    manifest = {
        "workflow": WORKFLOW_NAME,
        "outputs": {
            "qc_dir": str(out_dir / "qc"),
            "quant_dir": str(out_dir / "quant"),
            "salmon_quant_file": str(out_dir / "quant" / "quant.sf"),
        },
        "qc_files": sorted(path.name for path in (out_dir / "qc").glob("*")),
        "quant_files": sorted(path.name for path in (out_dir / "quant").glob("*")),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return Dir(path=str(out_dir))
