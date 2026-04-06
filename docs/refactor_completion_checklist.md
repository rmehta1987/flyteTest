# Refactor Completion Checklist

This checklist tracks milestone completion against the updated
`docs/braker3_evm_notes.md` contract rather than against workflow existence
alone.

Use this file as the shared completion gate before opening any work beyond the
current refactor boundary.

## Completion Rule

A milestone is only complete when:

- code, README claims, registry entries, and manifest language agree
- the implemented artifact contract matches `docs/braker3_evm_notes.md`
- inferred behavior is labeled as inferred behavior
- feasible synthetic or local validation exists for the changed boundary

## Current Stop Rule

Do not begin EggNOG, AGAT, or `table2asn` work until
Milestones 0 through 7 below are all complete against the notes-backed
acceptance criteria.

## Milestone 0

Goal: freeze scope and define the corrected refactor target.

Status: Complete

### Done

- [x] The repo has an explicit active milestone and stop rule in the README.
- [x] The README distinguishes some note-faithful behavior from provisional or
      simplified behavior.
- [x] BRAKER3 is still documented as inferred where the notes do not provide the
      exact command line.

### Still required

- [x] Keep one canonical checklist for milestone completion and use it as the
      gating document for downstream work.
- [x] Reconfirm that README milestone claims match the code after each refactor
      slice lands.
- [x] Reconfirm that no stage is described as fully implemented if it still
      depends on a shortcut that changes the notes-backed contract.

### Acceptance evidence

- Source of truth: `docs/braker3_evm_notes.md`
- Current milestone framing: `README.md`

## Milestone 1

Goal: make the pre-EVM contract match the notes.

Status: Complete

### Done

- [x] The repo now documents the corrected pre-EVM filenames:
      `transcripts.gff3`, `predictions.gff3`, and `proteins.gff3`.
- [x] A dedicated pre-EVM prep stage exists and is described as the handoff into
      EVM.
- [x] The current README says the pre-EVM contract should be built from PASA,
      TransDecoder, protein evidence, and BRAKER3 results.

### Still required

- [x] Verify in code that `transcripts.gff3` is staged from PASA assemblies GFF3
      rather than from upstream Trinity or StringTie intermediates.
- [x] Verify in code that `predictions.gff3` is assembled from
      `braker.gff3` plus the PASA-derived TransDecoder genome GFF3.
- [x] Verify in code that `proteins.gff3` is staged from the protein-evidence
      result contract used by the current Exonerate workflow.
- [x] Add or confirm synthetic tests for exact filename-level pre-EVM contract
      assembly.
- [x] Reconfirm registry descriptions and result manifests match the corrected
      pre-EVM contract.

### Acceptance evidence

- Notes contract lines:
  - `transcripts.gff3` from PASA assemblies
  - `predictions.gff3` from BRAKER plus TransDecoder genome GFF3
  - `proteins.gff3` from Exonerate-derived evidence
- Implementation surface:
  - `src/flytetest/tasks/consensus.py`
  - `src/flytetest/workflows/consensus.py`

## Milestone 2

Goal: align the EVM execution boundary with the notes while keeping
implementation assumptions explicit.

Status: Complete with documented simplifications

### Done

- [x] A dedicated EVM execution workflow now exists downstream of the pre-EVM
      bundle.
- [x] The README states that the repo now runs deterministic EVM partitioning,
      command generation, sequential execution, recombination, and final GFF3
      sorting.
- [x] The current milestone boundary now includes EVM execution before PASA
      post-EVM refinement.

### Still required

- [x] Reconfirm that source-field naming across transcript, protein, ab initio,
      and other prediction channels matches the staged weights assumptions.
- [x] Reconfirm that any local sequential execution shortcuts are documented as a
      deliberate replacement for the notes' `sbatch`-driven partition
      submission pattern.
- [x] Add or confirm synthetic tests for partition listing, command generation,
      recombination, and final sorted GFF3 collection.
- [x] Reconfirm that manifests distinguish note-backed EVM file contracts from
      local execution-policy choices.

### Acceptance evidence

- Source of truth: `docs/braker3_evm_notes.md`
- Implementation surface:
  - `src/flytetest/tasks/consensus.py`
  - `src/flytetest/workflows/consensus.py`

## Milestone 3

Goal: complete PASA post-EVM refinement without moving into later post-PASA
stages.

Status: Complete with documented simplifications

### Done

- [x] The README now treats PASA update rounds as part of the active milestone.
- [x] A dedicated PASA post-EVM refinement workflow exists.
- [x] The current milestone boundary stops before repeat filtering and later
      stages.

### Still required

- [x] Reconfirm that the PASA update workflow consumes the existing PASA
      align/assemble bundle plus the EVM result bundle rather than rebuilding
      transcript or consensus stages.
- [x] Reconfirm that the workflow supports at least two annotation-update rounds
      and that round two loads the first updated GFF3 rather than the original
      EVM file.
- [x] Reconfirm that the original PASA database is preserved and reused as the
      notes require.
- [x] Reconfirm that the final post-PASA GFF3 cleanup and sorting boundary is
      reflected in manifests and tests.
- [x] Add or confirm synthetic validation for post-PASA update-round result
      discovery and final sorted output collection.

### Acceptance evidence

- Notes contract lines:
  - load current annotations into PASA
  - run at least two update rounds
  - reuse the original PASA database
  - sort the final post-PASA GFF3
- Implementation surface:
  - `src/flytetest/tasks/pasa.py`
  - `src/flytetest/workflows/pasa.py`

## Milestone 4

Goal: correct the transcript-evidence to PASA contract without overclaiming the
current transcript branch.

Status: Complete and superseded by the implemented de novo Trinity branch

### Done

- [x] README, registry, and manifests describe transcript evidence as a
      single-sample implementation with documented simplifications rather than
      a full all-sample notes-faithful transcript branch.
- [x] PASA align/assemble now consumes the internally produced de novo Trinity
      FASTA from the transcript-evidence bundle.
- [x] StringTie stays aligned with the note-backed fixed flags currently used by
      the repo.

### Still required

- [x] Reconfirm that transcript-evidence and PASA tests cover the current
      single-sample branch honestly rather than implying all-sample notes
      fidelity.

### Acceptance evidence

- Source of truth: `docs/braker3_evm_notes.md`
- Implementation surface:
  - `src/flytetest/tasks/transcript_evidence.py`
  - `src/flytetest/workflows/transcript_evidence.py`
  - `src/flytetest/workflows/pasa.py`

## Milestone 5

Goal: narrow BRAKER3 inference while keeping the downstream EVM contract
reviewable.

Status: Complete with tutorial-backed runtime and explicit repo policy

### Done

- [x] README and tool references distinguish the notes-backed `braker.gff3`
      downstream contract from the Galaxy tutorial-backed runtime model used by
      this repo.
- [x] BRAKER3 normalization preserves upstream source-column values instead of
      forcing a repo-owned `BRAKER3` label.
- [x] BRAKER3 manifests separate notes-backed, tutorial-backed, and repo-policy
      language.

### Still required

- [x] Reconfirm that BRAKER3 staging still requires explicit local evidence
      inputs and does not silently invent unsupported runtime setup.
- [x] Reconfirm that normalization remains narrow and deterministic.

### Acceptance evidence

- Source of truth: `docs/braker3_evm_notes.md`
- Implementation surface:
  - `src/flytetest/tasks/annotation.py`
  - `src/flytetest/workflows/annotation.py`
  - `docs/tool_refs/braker3.md`

## Milestone 6

Goal: perform the validation and stop/go review of the implemented
transcript-to-PASA-to-EVM-to-post-EVM path before opening repeat filtering and
later downstream work.

Status: Complete

### Done

- [x] Rechecked the implemented path against `docs/braker3_evm_notes.md` from
      constrained transcript evidence through PASA post-EVM refinement.
- [x] Added or tightened synthetic tests for PASA result discovery, TransDecoder
      result discovery, BRAKER3 runtime-boundary and normalization policy,
      exact pre-EVM assembly, deterministic EVM execution stages, and PASA
      post-EVM final collection.
- [x] Ran compile checks and the full unit suite.
- [x] Reconfirmed that README claims, registry entries, tool-reference caveats,
      and manifest language describe the current implemented scope and current
      simplifications honestly.

### Still required

- [x] Keep note-backed, tutorial-backed, and repo-policy assumptions separated
      when the source material or runtime model differs.
- [x] Keep later post-PASA stages blocked until a separate milestone opens them
      explicitly.

### Acceptance evidence

- Source of truth: `docs/braker3_evm_notes.md`
- Implementation surface:
  - `src/flytetest/tasks/annotation.py`
  - `src/flytetest/tasks/consensus.py`
  - `src/flytetest/tasks/pasa.py`
  - `src/flytetest/tasks/transdecoder.py`
  - `src/flytetest/workflows/annotation.py`
  - `src/flytetest/workflows/consensus.py`
  - `src/flytetest/workflows/pasa.py`
  - `src/flytetest/workflows/transdecoder.py`
  - `src/flytetest/registry.py`
  - `README.md`
  - `docs/tool_refs/`
  - `tests/`

## Milestone 7

Goal: add annotation QC with BUSCO strictly downstream of repeat filtering.

Status: Complete

### Done

- [x] Added a narrow `busco_assess_proteins` task representing one BUSCO
      lineage run on the final repeat-filtered protein FASTA.
- [x] Added `annotation_qc_busco` to fan out across explicit lineage inputs and
      collect a stable BUSCO QC bundle.
- [x] Updated README, registry, compatibility exports, and BUSCO docs to expose
      the new post-repeat-filtering QC boundary honestly.
- [x] Added synthetic BUSCO tests covering lineage parsing, command wiring,
      repeat-filter boundary resolution, and multi-lineage result collection.

### Still required

- [x] Keep BUSCO strictly downstream of repeat filtering without reopening the
      validated transcript-to-PASA-to-EVM-to-post-EVM-to-repeat-filter path.
- [x] Keep EggNOG, AGAT, and `table2asn` deferred until a later milestone opens
      them explicitly.

### Acceptance evidence

- Source of truth: `docs/braker3_evm_notes.md`
- Implementation surface:
  - `src/flytetest/tasks/functional.py`
  - `src/flytetest/workflows/functional.py`
  - `src/flytetest/registry.py`
  - `README.md`
  - `docs/tool_refs/busco.md`
  - `docs/tool_refs/stage_index.md`
  - `tests/test_functional.py`

## Verification Commands

Use these commands as a lightweight review baseline after each milestone slice:

```bash
python3 -m py_compile src/flytetest/*.py src/flytetest/tasks/*.py src/flytetest/workflows/*.py flyte_rnaseq_workflow.py tests/*.py
python3 -m unittest
```

If tool binaries are unavailable, use synthetic tests and manifest checks rather
than claiming end-to-end runtime validation.
