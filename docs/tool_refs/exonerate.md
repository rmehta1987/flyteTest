# Exonerate

## Purpose

Align external protein evidence to the genome and convert the results into annotation-support formats.

## Key Inputs

- protein FASTA datasets such as UniProt or RefSeq
- reference genome
- chunking or partition inputs for parallel runs

## Key Outputs

- raw Exonerate alignments
- converted GFF3 evidence suitable for EVidenceModeler

## Pipeline Fit

- protein evidence generation before consensus annotation
- design notes describe chunked execution across many jobs

## Notes And Caveats

- Exonerate is not implemented in FLyteTest yet.
- Raw and converted outputs are both important in the design notes and should remain distinct artifacts.
- Future tasks should model chunk alignment, conversion, and concatenation as separate deterministic steps.
