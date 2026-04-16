# Post-Milestone 17 Asset Surface Follow-Up Audit

Date: 2026-04-10
Status: Proposed

Related checklist milestone or lane:
- Follow-up cleanup after `docs/realtime_refactor_checklist.md` Milestone 17
- Source audit for Milestones 22 through 25

Implementation note:
- This document is the inventory and rationale source for the narrow
  family-scoped follow-up milestones added after Milestone 17.
- It should be used when a future session wants to continue cleanup of
  tool-branded asset names without breaking historical manifest replay.
- The actual implementation slices now live in separate Milestones 22 through
  25 rather than in one broad repo-wide cleanup milestone.

## Why This Audit Exists

Milestone 14 introduced generic sibling asset names and compatibility aliases.
Milestone 17 then made the generic names the preferred internal surface for the
first three concrete generic/legacy pairs already present in the repo:

- `RnaSeqAlignmentResult` preferred over `StarAlignmentResult`
- `CleanedTranscriptDataset` preferred over `PasaCleanedTranscriptAsset`
- `AbInitioResultBundle` preferred over `Braker3ResultBundle`

That milestone was intentionally narrow. It did not try to rename every
tool-branded asset or every manifest key in the repository.

This audit records what is already in good shape, what still carries
tool-specific naming, and which areas would be the best candidates for later
cleanup if the project wants to continue moving from tool-branded names toward
biology-facing stage names.

## Current State

### What Milestone 17 already cleaned up

The following task families now emit both generic and legacy manifest keys
where a generic/legacy pair already existed, and the generic name is treated as
the preferred internal key:

1. Transcript evidence
   - file: `src/flytetest/tasks/transcript_evidence.py`
   - preferred key: `rna_seq_alignment`
   - legacy compatibility key: `star_alignment`
   - asset types:
     - generic: `RnaSeqAlignmentResult`
     - legacy: `StarAlignmentResult`

2. PASA transcript cleaning
   - file: `src/flytetest/tasks/pasa.py`
   - preferred key: `cleaned_transcript_dataset`
   - legacy compatibility key: `pasa_cleaned_transcripts`
   - asset types:
     - generic: `CleanedTranscriptDataset`
     - legacy: `PasaCleanedTranscriptAsset`

3. BRAKER-compatible ab initio result bundle
   - file: `src/flytetest/tasks/annotation.py`
   - preferred key: `ab_initio_result_bundle`
   - legacy compatibility key: `braker3_result_bundle`
   - asset types:
     - generic: `AbInitioResultBundle`
     - legacy: `Braker3ResultBundle`

Planner-adapter compatibility was also extended so legacy-only BRAKER manifests
continue to load through the generic-first adapter path:

- file: `src/flytetest/planner_adapters.py`

### What is already acceptable without immediate cleanup

Some areas still have explicit tool or stage names, but they are already
internally consistent and are not yet blocked on a generic rename:

1. EVM and consensus bundles
   - files:
     - `src/flytetest/tasks/consensus.py`
     - `src/flytetest/types/assets.py`
   - examples:
     - `evm_transcript_input_bundle`
     - `evm_input_preparation_bundle`
     - `evm_consensus_result_bundle`
   - reason to leave alone for now:
     these are explicit stage-boundary names rather than one-off internal
     aliases, and the project does not yet support multiple consensus engines
     that would force a more generic layer immediately.

2. Protein evidence top-level result bundle
   - files:
     - `src/flytetest/tasks/protein_evidence.py`
     - `src/flytetest/types/assets.py`
   - example:
     - `protein_evidence_result_bundle`
   - reason to leave alone for now:
     the top-level name is already reasonably biology-facing even though some
     nested members are still Exonerate-specific.

3. Core biology assets
   - file: `src/flytetest/types/assets.py`
   - examples:
     - `ReferenceGenome`
     - `ReadPair`
     - `MergedBamAsset`
     - `ProteinReferenceDatasetAsset`
   - reason to leave alone for now:
     these are already generic enough for the current planner and manifest use.

## Inventory Of Remaining Tool-Branded Cleanup Candidates

The table below records the most visible follow-up candidates found during the
audit.

### Candidate 1: TransDecoder assets

Files:
- `src/flytetest/tasks/transdecoder.py`
- `src/flytetest/types/assets.py`

Current emitted asset keys:
- `transdecoder_prediction`
- `source_pasa_alignment_assembly`

Current type names:
- `TransDecoderPredictionResult`
- `PasaAlignmentAssemblyResult`

Why this is a candidate:
- The emitted keys and types still speak in tool names instead of biological
  meaning.
- If the planner later wants to talk about a more general “coding prediction
  from transcript assemblies” boundary, the current naming will feel too
  tool-specific.

Why it is not urgent:
- The current repo still only supports the TransDecoder-backed implementation
  for this step.
- No generic sibling type exists yet, so any rename would need a deliberate
  design pass rather than just repeating the Milestone 17 pattern.

Suggested future direction:
- Define whether the biology-facing concept is:
  - coding-sequence prediction from transcript assemblies
  - ORF prediction from transcript assemblies
  - transcript-derived coding evidence
- Introduce a generic sibling type only after that biological boundary is named
  clearly enough to survive future tool variation.

Suggested generic naming examples to evaluate later:
- `TranscriptCodingPredictionResult`
- `CodingPredictionFromTranscriptAssembly`

### Candidate 2: Protein evidence nested Exonerate outputs

Files:
- `src/flytetest/tasks/protein_evidence.py`
- `src/flytetest/types/assets.py`

Current emitted asset keys:
- `raw_exonerate_chunk_results`
- `concatenated_raw_exonerate`

Current type names:
- `ExonerateChunkAlignmentResult`
- `EvmProteinEvidenceGff3Asset`

Why this is a candidate:
- The stage as a whole is biology-facing protein evidence alignment, but some
  nested asset names still expose the implementation tool directly.
- If the project later supports another protein-to-genome aligner, the current
  nested names will be awkward to generalize.

Why it is not urgent:
- The top-level bundle name `protein_evidence_result_bundle` is already good.
- The Exonerate-specific names are still truthful and useful because the repo
  currently only runs Exonerate here.

Suggested future direction:
- Keep the top-level bundle as is.
- Consider adding generic sibling names only for the nested raw alignment and
  converted-evidence chunk assets.

Suggested generic naming examples to evaluate later:
- `ProteinGenomeAlignmentChunkResult`
- `ProteinAlignmentEvidenceGff3Asset`

### Candidate 3: PASA post-EVM refinement assets

Files:
- `src/flytetest/tasks/pasa.py`
- `src/flytetest/types/assets.py`

Current emitted asset keys:
- `pasa_gene_model_update_inputs`
- `pasa_gene_model_update_round`
- `pasa_gene_model_update_bundle`

Current type names:
- `PasaGeneModelUpdateInputBundleAsset`
- `PasaGeneModelUpdateRoundResult`
- `PasaGeneModelUpdateResultBundle`

Why this is a candidate:
- These names are tightly bound to PASA even though the biology-facing stage is
  broader: annotation refinement after consensus annotation.
- If the planner later wants a generic “annotation refinement” stage, these
  names may become too narrow.

Why it is not urgent:
- The current repo is explicitly PASA-backed at this refinement boundary.
- The biological step and the implementation tool are still closely coupled in
  the current code and docs.

Suggested future direction:
- Only generalize this family if the project has a real need to represent
  “annotation refinement” independently from PASA itself.
- If PASA remains the only supported implementation for the foreseeable future,
  leaving these names alone may be the better choice.

Suggested generic naming examples to evaluate later:
- `AnnotationRefinementInputBundle`
- `AnnotationRefinementRoundResult`
- `AnnotationRefinementResultBundle`

### Candidate 4: EVM-prefixed consensus-prep and consensus-result assets

Files:
- `src/flytetest/tasks/consensus.py`
- `src/flytetest/types/assets.py`

Current emitted asset keys:
- `evm_transcript_input_bundle`
- `evm_protein_input_bundle`
- `evm_prediction_input_bundle`
- `evm_input_preparation_bundle`
- `evm_execution_input_bundle`
- `evm_partition_bundle`
- `evm_command_set`
- `evm_consensus_result_bundle`

Current type names:
- `EvmTranscriptInputBundleAsset`
- `EvmProteinInputBundleAsset`
- `EvmPredictionInputBundleAsset`
- `EvmInputPreparationBundle`
- `EvmExecutionInputBundleAsset`
- `EvmPartitionBundleAsset`
- `EvmCommandSetAsset`
- `EvmConsensusResultBundle`

Why this is a candidate:
- The project may eventually want a more generic consensus-annotation contract
  if another consensus engine is added.
- The current EVM names mix “consensus stage boundary” meaning with one
  implementation tool.

Why it is lower priority than the items above:
- The current pipeline is explicitly EVM-backed.
- These names are already structurally consistent and easy to understand.
- Generalizing them too early could create abstraction churn without any real
  implementation benefit.

Suggested future direction:
- Do not rename this family unless a second consensus-engine path is actually
  being introduced.
- If a second path appears, design the generic layer from the biological stage
  outward instead of doing piecemeal aliasing.

Suggested generic naming examples to evaluate later:
- `ConsensusTranscriptInputBundle`
- `ConsensusInputPreparationBundle`
- `ConsensusExecutionInputBundle`
- `ConsensusResultBundle`

## Prioritization Recommendation

If the repo continues generic-asset cleanup later, the recommended order is:

1. TransDecoder follow-up
2. Protein-evidence nested Exonerate assets
3. PASA post-EVM refinement assets
4. EVM / consensus assets

Reasoning:

1. TransDecoder is the most clearly tool-branded remaining output family that
   may plausibly want a biology-facing abstraction later.
2. Protein evidence already has a good top-level generic bundle, so cleaning up
   the nested Exonerate names would be a modest, bounded improvement.
3. PASA refinement should only be generalized if the project truly wants a
   broader annotation-refinement abstraction.
4. EVM asset cleanup should wait until the repo has a real second-engine reason
   to introduce a generic consensus layer.

## Decision Rules For Future Cleanup

Future sessions should only genericize a tool-branded asset family when at
least one of these conditions is true:

1. A generic sibling type already exists and the work is just key/adoption
   cleanup, like Milestone 17.
2. The current tool-branded name is actively blocking planner, resolver, or
   workflow-composition work.
3. The project is preparing to support more than one implementation tool for
   the same biological stage.

Future sessions should avoid genericizing a family when:

1. The tool name is still the clearest truthful description of the stage.
2. No stable biology-facing concept has been named yet.
3. The rename would create a compatibility burden without helping planning,
   manifest reuse, or future composition.

## Suggested Refactor Pattern

When one of the candidate families is eventually cleaned up, use the same
pattern that worked for Milestone 17:

1. Introduce or confirm the generic sibling type in `src/flytetest/types/assets.py`.
2. Keep the legacy type name available as an alias or thin wrapper.
3. Update new manifest emitters to prefer the generic key.
4. Keep the legacy key available in emitted manifests when replay compatibility
   matters.
5. Update provenance metadata so `source_manifest_key` points at the generic key.
6. Update planner adapters and any resolver helpers to load the generic key
   first and legacy keys second.
7. Add tests for:
   - generic-name round-tripping
   - legacy-only manifest loading
   - current manifest emitters writing the new generic key
8. Update README and capability docs only after the code truth lands.

## Validation Expectations For Future Cleanup

When a future cleanup slice is implemented, validation should include at least:

- `python3 -m py_compile` on touched Python files
- focused unit tests for:
  - the touched task module
  - planner adapters and resolver code if manifest loading changed
  - any manifest-shape contract tests
- `git diff --check`

Recommended test targets for most future asset-cleanup slices:

- `python3 -m unittest tests.test_planner_types`
- `python3 -m unittest tests.test_resolver`
- family-specific workflow or task tests for the touched module

## Blockers Or Assumptions

- This audit assumes historical manifests must remain replayable.
- It assumes the repo should prefer additive compatibility aliases over hard
  renames.
- It assumes genericization is only worthwhile when it improves planner
  reasoning, stage reuse, or future tool interchangeability.
- It does not recommend introducing generic aliases merely for aesthetic
  consistency when there is no concrete planning or compatibility benefit.
