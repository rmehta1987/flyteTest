"""Quantification tasks for the original FLyteTest RNA-seq workflow.

    This module keeps the current Salmon indexing, quantification, and result
    collection boundaries used by the compatibility entrypoint.

    Tool-level command and input/output expectations follow `docs/tool_refs/salmon.md`.
    That reference matches the Salmon stage implemented here.
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
    """Build a Salmon index from a reference transcriptome FASTA file.

    Args:
        ref: A value used by the helper.
        salmon_sif: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
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
    """Quantify transcript abundance for a paired-end RNA-seq sample using Salmon.

    Args:
        index: A value used by the helper.
        left: A value used by the helper.
        right: A value used by the helper.
        salmon_sif: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
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
    """Consolidate FastQC and Salmon quantification outputs into a manifest-bearing result bundle.

    Args:
        qc: A value used by the helper.
        quant: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
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
