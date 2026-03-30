from __future__ import annotations

import tempfile
from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import env, require_path, run_tool


@env.task
def fastqc(left: File, right: File, fastqc_sif: str = "") -> Dir:
    left_path = require_path(Path(left.download_sync()), "Read 1 FASTQ")
    right_path = require_path(Path(right.download_sync()), "Read 2 FASTQ")
    out_dir = Path(tempfile.mkdtemp(prefix="fastqc_")) / "qc"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        ["fastqc", "--quiet", str(left_path), str(right_path), "--outdir", str(out_dir)],
        fastqc_sif,
        [left_path.parent, right_path.parent, out_dir.parent],
    )
    return Dir.from_local_sync(str(out_dir))
