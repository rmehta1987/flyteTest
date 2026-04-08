"""Workflow exports for the implemented FLyteTest entrypoints.

This package-level module preserves one import surface for composed biological
stage entrypoints while optional workflow families remain modular.
"""

from importlib.util import find_spec

if find_spec("flytetest.workflows.annotation") is not None:
    from flytetest.workflows.annotation import ab_initio_annotation_braker3

    _annotation_workflows = ("ab_initio_annotation_braker3",)
else:
    _annotation_workflows = ()

if find_spec("flytetest.workflows.consensus") is not None:
    from flytetest.workflows.consensus import consensus_annotation_evm, consensus_annotation_evm_prep

    _consensus_workflows = ("consensus_annotation_evm", "consensus_annotation_evm_prep")
else:
    _consensus_workflows = ()

if find_spec("flytetest.workflows.filtering") is not None:
    from flytetest.workflows.filtering import annotation_repeat_filtering

    _filtering_workflows = ("annotation_repeat_filtering",)
else:
    _filtering_workflows = ()

if find_spec("flytetest.workflows.functional") is not None:
    from flytetest.workflows.functional import annotation_qc_busco

    _functional_workflows = ("annotation_qc_busco",)
else:
    _functional_workflows = ()

if find_spec("flytetest.workflows.eggnog") is not None:
    from flytetest.workflows.eggnog import annotation_functional_eggnog

    _eggnog_workflows = ("annotation_functional_eggnog",)
else:
    _eggnog_workflows = ()

if find_spec("flytetest.workflows.agat") is not None:
    from flytetest.workflows.agat import (
        annotation_postprocess_agat,
        annotation_postprocess_agat_cleanup,
        annotation_postprocess_agat_conversion,
    )

    _agat_workflows = (
        "annotation_postprocess_agat",
        "annotation_postprocess_agat_cleanup",
        "annotation_postprocess_agat_conversion",
    )
else:
    _agat_workflows = ()

from flytetest.workflows.pasa import annotation_refinement_pasa, pasa_transcript_alignment
from flytetest.workflows.rnaseq_qc_quant import rnaseq_qc_quant
from flytetest.workflows.transdecoder import transdecoder_from_pasa
from flytetest.workflows.transcript_evidence import transcript_evidence_generation

if find_spec("flytetest.workflows.protein_evidence") is not None:
    from flytetest.workflows.protein_evidence import protein_evidence_alignment

    _protein_workflows = ("protein_evidence_alignment",)
else:
    _protein_workflows = ()

__all__ = [
    *_annotation_workflows,
    *_consensus_workflows,
    *_filtering_workflows,
    *_functional_workflows,
    *_eggnog_workflows,
    *_agat_workflows,
    "annotation_refinement_pasa",
    "pasa_transcript_alignment",
    "rnaseq_qc_quant",
    *_protein_workflows,
    "transdecoder_from_pasa",
    "transcript_evidence_generation",
]
