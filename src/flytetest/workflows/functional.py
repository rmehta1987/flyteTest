"""BUSCO-based annotation-QC workflow entrypoints for FLyteTest.

This module runs multi-lineage BUSCO protein assessments strictly downstream of
the repeat-filtered annotation boundary and stops before EggNOG, AGAT, or
submission-prep work.

Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
input/output expectations follow `docs/tool_refs/busco.md`.
"""

from __future__ import annotations

from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import functional_qc_env, require_path
from flytetest.tasks.functional import (
    DEFAULT_BUSCO_LINEAGES_TEXT,
    _lineages_from_text,
    _repeat_filter_final_proteins,
    busco_assess_proteins,
    collect_busco_results,
)


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@functional_qc_env.task
def annotation_qc_busco(
    repeat_filter_results: Dir,
    busco_lineages_text: str = DEFAULT_BUSCO_LINEAGES_TEXT,
    busco_sif: str = "",
    busco_cpu: int = 8,
) -> Dir:
    """Run the BUSCO QC boundary for the repeat-filtered protein set."""
    repeat_filter_dir = require_path(
        Path(repeat_filter_results.download_sync()),
        "Repeat-filtering results directory",
    )
    proteins_fasta = File(path=str(_repeat_filter_final_proteins(repeat_filter_dir)))
    lineage_datasets = _lineages_from_text(busco_lineages_text)

    busco_runs: list[Dir] = []
    for lineage_dataset in lineage_datasets:
        busco_runs.append(
            busco_assess_proteins(
                proteins_fasta=proteins_fasta,
                lineage_dataset=lineage_dataset,
                busco_sif=busco_sif,
                busco_cpu=busco_cpu,
            )
        )

    return collect_busco_results(
        repeat_filter_results=repeat_filter_results,
        busco_runs=busco_runs,
        busco_lineages_text=",".join(lineage_datasets),
    )


__all__ = ["annotation_qc_busco"]
