from __future__ import annotations

from flyte.io import Dir, File

from flytetest.config import env
from flytetest.tasks.qc import fastqc
from flytetest.tasks.quant import collect_results, salmon_index, salmon_quant


# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
@env.task
def rnaseq_qc_quant(
    ref: File,
    left: File,
    right: File,
    salmon_sif: str = "",
    fastqc_sif: str = "",
) -> Dir:
    index = salmon_index(ref=ref, salmon_sif=salmon_sif)
    qc = fastqc(left=left, right=right, fastqc_sif=fastqc_sif)
    quant = salmon_quant(index=index, left=left, right=right, salmon_sif=salmon_sif)
    return collect_results(qc=qc, quant=quant)
