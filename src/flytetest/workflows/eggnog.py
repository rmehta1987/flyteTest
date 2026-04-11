"""EggNOG functional-annotation workflow entrypoint for FLyteTest.

    This module keeps the post-BUSCO functional-annotation boundary explicit while
    preserving the deterministic local collector pattern used by the other stages.

    Stage ordering follows `docs/braker3_evm_notes.md`. Tool-level command and
    input/output expectations follow `docs/tool_refs/eggnog-mapper.md`.
"""

from __future__ import annotations

from flyte.io import Dir

from flytetest.config import eggnog_env
from flytetest.tasks.eggnog import collect_eggnog_results, eggnog_map


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@eggnog_env.task
def annotation_functional_eggnog(
    repeat_filter_results: Dir,
    eggnog_data_dir: str,
    eggnog_sif: str = "",
    eggnog_cpu: int = 24,
    eggnog_database: str = "Diptera",
) -> Dir:
    """Perform downstream functional orthology assignment and functional annotation of predicted proteins.

    Args:
        repeat_filter_results: A directory path used by the helper.
        eggnog_data_dir: A directory path used by the helper.
        eggnog_sif: A value used by the helper.
        eggnog_cpu: A value used by the helper.
        eggnog_database: A value used by the helper.

    Returns:
        The returned `Dir` value used by the caller.
"""
    eggnog_run = eggnog_map(
        repeat_filter_results=repeat_filter_results,
        eggnog_data_dir=eggnog_data_dir,
        eggnog_sif=eggnog_sif,
        eggnog_cpu=eggnog_cpu,
        eggnog_database=eggnog_database,
    )
    return collect_eggnog_results(
        repeat_filter_results=repeat_filter_results,
        eggnog_run=eggnog_run,
    )


__all__ = ["annotation_functional_eggnog"]
