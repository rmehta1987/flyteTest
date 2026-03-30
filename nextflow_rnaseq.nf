#!/usr/bin/env nextflow
nextflow.enable.dsl=2

// Define pipeline input parameters 
// note: input files require the use of absolute paths
params.ref = '/data/transcriptome.fa'
params.left = '/data/reads_1.fq.gz'
params.right = '/data/reads_2.fq.gz'
params.outdir = 'results'


// Create reference transcriptome index using Salmom
process SALMON_INDEX {
  input: 
    path ref
  output:
    path index

  """
    salmon index -t '${ref}' -i index
  """
}


// Transcriptome alignment and quantification using Salmon
process SALMON_ALIGN_QUANT {
  publishDir params.outdir

  input:
    path index
    path left 
    path right
  output:
    path 'quant'

  """
    salmon quant -i $index -l A -1 '${left}' -2 '${right}' --validateMappings -o quant
  """
}

// FastQC
process FASTQC {
  publishDir params.outdir

  input:
    path index
    path left
    path right
  output:
    path 'qc'

  """
    mkdir qc && fastqc --quiet '${params.left}' '${params.right}' --outdir qc
  """
}

workflow {
  SALMON_INDEX(params.ref)
  SALMON_ALIGN_QUANT( SALMON_INDEX.out, params.left, params.right )
  FASTQC( SALMON_INDEX.out, params.left, params.right )
}