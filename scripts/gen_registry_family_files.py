#!/usr/bin/env python3
"""One-time script: generate registry family files from the monolith.

Run from the project root with the venv active:
    python3 scripts/gen_registry_family_files.py

Writes 7 family files into src/flytetest/registry/.
Safe to re-run; overwrites any existing output.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flytetest.registry import REGISTRY_ENTRIES, RegistryCompatibilityMetadata  # noqa: E402

# ---------------------------------------------------------------------------
# Family assignments  (workflow first, then tasks in logical pipeline order)
# ---------------------------------------------------------------------------

FAMILY_ASSIGNMENTS: dict[str, list[str]] = {
    "_transcript_evidence": [
        "transcript_evidence_generation",
        "trinity_denovo_assemble",
        "star_genome_index",
        "star_align_sample",
        "samtools_merge_bams",
        "trinity_genome_guided_assemble",
        "stringtie_assemble",
        "collect_transcript_evidence_results",
    ],
    "_consensus": [
        "pasa_transcript_alignment",
        "transdecoder_from_pasa",
        "annotation_refinement_pasa",
        "pasa_accession_extract",
        "combine_trinity_fastas",
        "pasa_seqclean",
        "pasa_create_sqlite_db",
        "pasa_align_assemble",
        "collect_pasa_results",
        "prepare_pasa_update_inputs",
        "pasa_load_current_annotations",
        "pasa_update_gene_models",
        "finalize_pasa_update_outputs",
        "collect_pasa_update_results",
        "transdecoder_train_from_pasa",
        "collect_transdecoder_results",
    ],
    "_protein_evidence": [
        "protein_evidence_alignment",
        "stage_protein_fastas",
        "chunk_protein_fastas",
        "exonerate_align_chunk",
        "exonerate_to_evm_gff3",
        "exonerate_concat_results",
    ],
    "_annotation": [
        "ab_initio_annotation_braker3",
        "stage_braker3_inputs",
        "braker3_predict",
        "normalize_braker3_for_evm",
        "collect_braker3_results",
    ],
    "_evm": [
        "consensus_annotation_evm_prep",
        "consensus_annotation_evm",
        "prepare_evm_transcript_inputs",
        "prepare_evm_protein_inputs",
        "prepare_evm_prediction_inputs",
        "collect_evm_prep_results",
        "prepare_evm_execution_inputs",
        "evm_partition_inputs",
        "evm_write_commands",
        "evm_execute_commands",
        "evm_recombine_outputs",
        "collect_evm_results",
    ],
    "_postprocessing": [
        "annotation_repeat_filtering",
        "annotation_qc_busco",
        "annotation_functional_eggnog",
        "annotation_postprocess_agat",
        "annotation_postprocess_agat_conversion",
        "annotation_postprocess_agat_cleanup",
        "annotation_postprocess_table2asn",
        "repeatmasker_out_to_bed",
        "gffread_proteins",
        "funannotate_remove_bad_models",
        "remove_overlap_repeat_models",
        "funannotate_repeat_blast",
        "remove_repeat_blast_hits",
        "collect_repeat_filter_results",
        "busco_assess_proteins",
        "collect_busco_results",
        "eggnog_map",
        "collect_eggnog_results",
        "agat_statistics",
        "agat_convert_sp_gxf2gxf",
        "agat_cleanup_gff3",
    ],
    "_rnaseq": [
        "rnaseq_qc_quant",
        "salmon_index",
        "fastqc",
        "salmon_quant",
        "collect_results",
    ],
}

TUPLE_NAMES: dict[str, str] = {
    "_transcript_evidence": "TRANSCRIPT_EVIDENCE_ENTRIES",
    "_consensus": "CONSENSUS_ENTRIES",
    "_protein_evidence": "PROTEIN_EVIDENCE_ENTRIES",
    "_annotation": "ANNOTATION_ENTRIES",
    "_evm": "EVM_ENTRIES",
    "_postprocessing": "POSTPROCESSING_ENTRIES",
    "_rnaseq": "RNASEQ_ENTRIES",
}

FAMILY_LABELS: dict[str, str] = {
    "_transcript_evidence": "transcript-evidence",
    "_consensus": "consensus",
    "_protein_evidence": "protein-evidence",
    "_annotation": "annotation",
    "_evm": "evm",
    "_postprocessing": "postprocessing",
    "_rnaseq": "rnaseq",
}

# ---------------------------------------------------------------------------
# Code generation helpers
# ---------------------------------------------------------------------------

_DEFAULT_COMPAT = RegistryCompatibilityMetadata()


def _fmt_tuple_of_strs(t: tuple[str, ...]) -> str:
    if not t:
        return "()"
    items = ", ".join(repr(x) for x in t)
    return f"({items},)"


def _fmt_exec_defaults(d: dict) -> str:
    """Render execution_defaults dict with nested dict support."""
    if not d:
        return "{}"
    lines: list[str] = ["{"]
    for k, v in d.items():
        if isinstance(v, dict):
            inner = ", ".join(f"{repr(ik)}: {repr(iv)}" for ik, iv in v.items())
            lines.append(f"            {repr(k)}: {{{inner}}},")
        else:
            lines.append(f"            {repr(k)}: {repr(v)},")
    lines.append("        }")
    return "\n".join(lines)


def _fmt_compat(c: RegistryCompatibilityMetadata) -> str:
    parts: list[str] = ["RegistryCompatibilityMetadata("]
    if c.biological_stage != _DEFAULT_COMPAT.biological_stage:
        parts.append(f"            biological_stage={repr(c.biological_stage)},")
    if c.accepted_planner_types != _DEFAULT_COMPAT.accepted_planner_types:
        parts.append(f"            accepted_planner_types={_fmt_tuple_of_strs(c.accepted_planner_types)},")
    if c.produced_planner_types != _DEFAULT_COMPAT.produced_planner_types:
        parts.append(f"            produced_planner_types={_fmt_tuple_of_strs(c.produced_planner_types)},")
    if c.reusable_as_reference != _DEFAULT_COMPAT.reusable_as_reference:
        parts.append(f"            reusable_as_reference={c.reusable_as_reference!r},")
    if c.execution_defaults != _DEFAULT_COMPAT.execution_defaults:
        parts.append(f"            execution_defaults={_fmt_exec_defaults(c.execution_defaults)},")
    if c.supported_execution_profiles != _DEFAULT_COMPAT.supported_execution_profiles:
        parts.append(
            f"            supported_execution_profiles={_fmt_tuple_of_strs(c.supported_execution_profiles)},"
        )
    if c.synthesis_eligible != _DEFAULT_COMPAT.synthesis_eligible:
        parts.append(f"            synthesis_eligible={c.synthesis_eligible!r},")
    if c.composition_constraints != _DEFAULT_COMPAT.composition_constraints:
        parts.append(f"            composition_constraints={_fmt_tuple_of_strs(c.composition_constraints)},")
    if c.pipeline_family != _DEFAULT_COMPAT.pipeline_family:
        parts.append(f"            pipeline_family={repr(c.pipeline_family)},")
    if c.pipeline_stage_order != _DEFAULT_COMPAT.pipeline_stage_order:
        parts.append(f"            pipeline_stage_order={c.pipeline_stage_order!r},")
    parts.append("        )")
    return "\n".join(parts)


def _fmt_interface_fields(fields: tuple) -> str:
    lines: list[str] = []
    for f in fields:
        lines.append(
            f"            InterfaceField({repr(f.name)}, {repr(f.type)}, {repr(f.description)}),"
        )
    return "\n".join(lines)


def _fmt_entry(entry) -> str:
    lines: list[str] = ["    RegistryEntry("]
    lines.append(f"        name={repr(entry.name)},")
    lines.append(f"        category={repr(entry.category)},")
    lines.append(f"        description={repr(entry.description)},")

    if entry.inputs:
        lines.append("        inputs=(")
        lines.append(_fmt_interface_fields(entry.inputs))
        lines.append("        ),")
    else:
        lines.append("        inputs=(),")

    if entry.outputs:
        lines.append("        outputs=(")
        lines.append(_fmt_interface_fields(entry.outputs))
        lines.append("        ),")
    else:
        lines.append("        outputs=(),")

    lines.append(f"        tags={repr(entry.tags)},")

    if entry.compatibility != _DEFAULT_COMPAT:
        lines.append(f"        compatibility={_fmt_compat(entry.compatibility)},")

    lines.append("    ),")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

entry_map = {e.name: e for e in REGISTRY_ENTRIES}
output_dir = os.path.join(
    os.path.dirname(__file__), "..", "src", "flytetest", "registry"
)

# Verify all assignments cover the full 73 entries
all_assigned = [name for names in FAMILY_ASSIGNMENTS.values() for name in names]
assert len(all_assigned) == 73, f"Expected 73 entries, got {len(all_assigned)}"
assert set(all_assigned) == {e.name for e in REGISTRY_ENTRIES}, (
    f"Missing: {set(e.name for e in REGISTRY_ENTRIES) - set(all_assigned)}\n"
    f"Extra: {set(all_assigned) - set(e.name for e in REGISTRY_ENTRIES)}"
)

for module_name, entry_names in FAMILY_ASSIGNMENTS.items():
    tuple_name = TUPLE_NAMES[module_name]
    label = FAMILY_LABELS[module_name]

    body_lines: list[str] = [
        f'"""Registry entries for the {label} pipeline family."""',
        "",
        "from __future__ import annotations",
        "",
        "from flytetest.registry._types import (",
        "    InterfaceField,",
        "    RegistryCompatibilityMetadata,",
        "    RegistryEntry,",
        ")",
        "",
        "",
        f"{tuple_name}: tuple[RegistryEntry, ...] = (",
    ]
    for name in entry_names:
        body_lines.append(_fmt_entry(entry_map[name]))
    body_lines.append(")")
    body_lines.append("")

    outpath = os.path.join(output_dir, f"{module_name}.py")
    with open(outpath, "w") as fh:
        fh.write("\n".join(body_lines))
    print(f"  Wrote {module_name}.py  ({len(entry_names)} entries)")

print(f"\nTotal assigned: {len(all_assigned)} / 73")
print("Done.")
