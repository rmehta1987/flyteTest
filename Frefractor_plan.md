**Refactor Plan**

The project should pause at a single near-term milestone: make the repo fully faithful to the updated pre-EVM pipeline in [docs/braker3_evm_notes.md](/home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md) before adding any post-EVM stages. That means we should not start PASA update rounds, repeat filtering, BUSCO, EggNOG, AGAT, or `table2asn` work until the current transcript/PASA/TransDecoder/protein/BRAKER3/EVM-prep path is corrected.

1. Milestone 0: Freeze scope and define the corrected target contract  
   Deliverable: one short design addendum in [DESIGN.md](/home/rmeht/Projects/flyteTest/DESIGN.md) and the notes table in [README.md](/home/rmeht/Projects/flyteTest/README.md) updated to say the active milestone is “notes-faithful pre-EVM refactor.”  
   Scope:
   - Freeze all downstream work after EVM.
   - Mark current shortcuts as temporary where they differ from the notes.
   - Define the exact required pre-EVM artifacts:
     - `transcripts.gff3` from PASA assemblies
     - `predictions.gff3` from `braker.gff3` + TransDecoder genome GFF3
     - `proteins.gff3` from converted Exonerate outputs
   Exit criteria:
   - README stage table matches actual implementation status.
   - No module claims “EVM-ready” unless it matches the notes-backed contract.

2. Milestone 1: Refactor the EVM-prep workflow around the correct upstream products  
   Primary files: [src/flytetest/workflows/consensus.py](/home/rmeht/Projects/flyteTest/src/flytetest/workflows/consensus.py), [src/flytetest/tasks/consensus.py](/home/rmeht/Projects/flyteTest/src/flytetest/tasks/consensus.py), [src/flytetest/registry.py](/home/rmeht/Projects/flyteTest/src/flytetest/registry.py), [README.md](/home/rmeht/Projects/flyteTest/README.md).  
   Scope:
   - Change the consensus-prep inputs so it consumes `pasa_results`, `transdecoder_results`, `protein_evidence_results`, and `braker3_results`.
   - Build exact staged files named:
     - `predictions.gff3`
     - `proteins.gff3`
     - `transcripts.gff3`
   - Stop staging `trinity_gg.fasta` and `stringtie.gtf` as the final transcript EVM channel.
   - Record EVM source-field expectations in the manifest, without running EVM yet.
   Exit criteria:
   - Consensus prep output shape mirrors the notes.
   - Registry and README describe the corrected contract.
   - Tests cover the file assembly logic.

3. Milestone 2: Refactor TransDecoder to match the updated notes more closely  
   Primary files: [src/flytetest/tasks/transdecoder.py](/home/rmeht/Projects/flyteTest/src/flytetest/tasks/transdecoder.py), [src/flytetest/workflows/transdecoder.py](/home/rmeht/Projects/flyteTest/src/flytetest/workflows/transdecoder.py), [README.md](/home/rmeht/Projects/flyteTest/README.md).  
   Scope:
   - Replace the current generic “LongOrfs then Predict” claim with a notes-faithful wrapper around the PASA training-set path.
   - Support the script boundary the notes describe around `pasa_asmbls_to_training_set.dbi`.
   - Keep any remaining helper inference explicit in manifests and docs.
   Exit criteria:
   - README no longer says the notes do not specify the TransDecoder path.
   - Manifests clearly separate note-backed steps from any remaining environment assumptions.

4. Milestone 3: Refactor protein evidence so the conversion matches the notes  
   Primary files: [src/flytetest/tasks/protein_evidence.py](/home/rmeht/Projects/flyteTest/src/flytetest/tasks/protein_evidence.py), [src/flytetest/workflows/protein_evidence.py](/home/rmeht/Projects/flyteTest/src/flytetest/workflows/protein_evidence.py), [README.md](/home/rmeht/Projects/flyteTest/README.md), [tests/test_protein_evidence.py](/home/rmeht/Projects/flyteTest/tests/test_protein_evidence.py).  
   Scope:
   - Add note-backed Exonerate chunk controls for query chunk id and total.
   - Convert outputs through the EVM helper boundary the notes name, instead of treating raw 9-column lines as fully sufficient.
   - Preserve both raw Exonerate outputs and converted EVM GFF3 outputs.
   - Implement empty-file filtering, deterministic concatenation, and blank-line cleanup.
   - Normalize source-field handling to match later EVM weights expectations.
   Exit criteria:
   - `proteins.gff3` is produced from the same logical steps the notes describe.
   - README stops overclaiming “downstream-ready” if any shortcut remains.

5. Milestone 4: Correct the transcript-evidence to PASA contract  
   Primary files: [src/flytetest/tasks/transcript_evidence.py](/home/rmeht/Projects/flyteTest/src/flytetest/tasks/transcript_evidence.py), [src/flytetest/workflows/transcript_evidence.py](/home/rmeht/Projects/flyteTest/src/flytetest/workflows/transcript_evidence.py), [src/flytetest/workflows/pasa.py](/home/rmeht/Projects/flyteTest/src/flytetest/workflows/pasa.py), [README.md](/home/rmeht/Projects/flyteTest/README.md).  
   Scope:
   - Decide one of two acceptable paths and encode it clearly:
     - implement de novo Trinity as a real upstream workflow stage, or
     - require external de novo Trinity input and mark PASA as only partially implemented until that exists
   - Revisit the current single-sample STAR/BAM-merge placeholder, because the notes describe aligning all samples then merging all BAMs.
   - Keep StringTie parameters aligned with the notes if we expose them.
   Exit criteria:
   - PASA no longer appears “fully implemented” if required upstream evidence is still external.
   - The transcript branch is either implemented or explicitly constrained.

6. Milestone 5: Revisit BRAKER3 only after upstream EVM-prep is corrected  
   Primary files: [src/flytetest/tasks/annotation.py](/home/rmeht/Projects/flyteTest/src/flytetest/tasks/annotation.py), [README.md](/home/rmeht/Projects/flyteTest/README.md).  
   Scope:
   - Keep BRAKER3 as inferred, but make the inference narrower and more honest.
   - Recheck whether source-field normalization should remain `BRAKER3` or preserve upstream values for EVM compatibility.
   - Ensure manifests clearly distinguish “notes-backed” from “repo policy.”
   Exit criteria:
   - BRAKER remains intentionally inferred, but not over-normalized or overclaimed.

7. Milestone 6: Validation and stop/go review before any downstream work  
   Scope:
   - Add synthetic tests for PASA result discovery, TransDecoder result discovery, BRAKER normalization, and consensus file assembly.
   - Run compile checks and unit tests.
   - Perform one review pass specifically against [docs/braker3_evm_notes.md](/home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md).
   Exit criteria:
   - The pre-EVM path is coherent end to end on paper and in code.
   - README, registry, manifests, and tests all agree.
   - Only then do we open the next milestone: actual EVM execution.

**Stop Rule**

Until Milestone 6 is complete, we should not add:
- PASA post-EVM update rounds
- RepeatMasker/funannotate filtering
- BUSCO
- EggNOG
- AGAT
- NCBI submission prep

**Recommended implementation order**

1. Milestone 0  
2. Milestone 1  
3. Milestone 3  
4. Milestone 2  
5. Milestone 4  
6. Milestone 5  
7. Milestone 6

That order fixes the biggest architectural mismatch first: the repo currently prepares the wrong inputs for the EVM boundary.

If you want, I can turn this into a task-by-task execution checklist with exact file edits for Milestone 0 and Milestone 1.