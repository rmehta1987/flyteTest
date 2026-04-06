# FLyteTest (temporary name): A Genomic Studies Platform for Reproducible Research on HPC

## Introduction

FLyteTest is an open-source, Flyte-based platform for genomic studies in non-traditional model organisms. The project is being developed to make genome annotation and RNA-seq analysis easier to run on HPC systems, easier to extend with new tasks and workflows, and easier to use for students and computational biologists who need reproducible research tools without editing Python code.

The platform is designed around a simple idea: users should be able to describe an analysis goal in plain language, select a supported workflow, and run a deterministic pipeline that is already registered in the codebase. That makes the system more approachable for training and day-to-day research while keeping the implementation inspectable, reproducible, and suitable for shared lab environments.

## Project Goals

The current goals of the project are to:

* provide a modular, open-source workflow system for genome annotation and RNA-seq analysis
* support HPC and containerized execution in a way that is predictable for shared institutional compute environments
* expand the library of reusable Flyte tasks and workflows instead of relying on ad hoc scripts
* make the platform approachable for students, trainees, and computational biologists who need practical research workflows
* preserve reproducibility through deterministic task boundaries, typed inputs and outputs, and stable result bundles
* document each stage clearly so collaborators can understand what is implemented now versus what is planned next

## Current Direction

The repository is evolving from a single RNA-seq example into a broader genome annotation workflow system. The current implementation already includes task and workflow pieces for:

* RNA-seq quality control and quantification
* transcript evidence generation
* PASA transcript alignment and assembly
* TransDecoder coding prediction from PASA outputs
* protein evidence alignment
* BRAKER3 as an upstream ab initio annotation source
* early consensus-annotation preparation around the EVM boundary

The near-term focus is to keep these stages faithful to the working notes in `docs/braker3_evm_notes.md` while improving the registry, documentation, and workflow structure so additional stages can be added cleanly.

## MCP-Compatible Prompting

Users can interact with FLyteTest through an MCP-compatible client, such as OpenCode, ChatGPT, Claude, or a custom client they configure themselves. In practice, this means a researcher can ask for a supported workflow in plain language and have the platform map that request to an existing Flyte task or workflow.

That same prompting style can also be used for ad hoc experimentation with the registered tasks and workflows. The user does not need to write new pipeline code to explore a supported analysis path; they can request the desired stage and provide the relevant inputs and compute requirements.

### Example: Transcript Evidence Generation

A user with a `TranscriptomeReference` and RNA-seq reads can ask the platform to run transcript evidence generation for downstream annotation. The platform can then select the supported transcript evidence workflow and return the resulting assembly and evidence artifacts.

Example request:

* “Using my `TranscriptomeReference` and RNA-seq reads, run transcript evidence generation for downstream annotation.”

HPC-oriented version:

* “Using my `TranscriptomeReference` and RNA-seq reads, run transcript evidence generation on HPC with 32 CPU cores, 128 GB RAM, containerized execution, and output written to a shared project directory.”

### Example: BRAKER3 Gene Annotation

A user can also request BRAKER3-based gene annotation by providing a `ReferenceGenome` and protein evidence. The platform can select the supported BRAKER3 workflow, produce `braker.gff3`, and prepare the output for later consensus annotation steps.

Example request:

* “Using this `ReferenceGenome` and protein evidence, run BRAKER3 for gene annotation and return the resulting `braker.gff3` output for downstream consensus annotation.”

HPC-oriented version:

* “Using this `ReferenceGenome` and protein evidence, run BRAKER3 with Slurm scheduling, 64 CPU cores, a 256 GB memory allocation, containerized execution, and return `braker.gff3` plus the run manifest.”

## Near-Term Milestones

The next milestones are aimed at making the platform more useful for real research teams and easier for new users to adopt:

* finish the notes-faithful pre-EVM boundary so transcript, protein, and ab initio evidence are assembled into predictable inputs for later consensus annotation
* continue splitting logic into narrow, reusable tasks and stage-specific workflows
* improve HPC-oriented runtime metadata, container assumptions, and result manifests
* strengthen the documentation so students and scientists can follow the pipeline without reconstructing the call graph
* keep the task and workflow registry aligned with the actual code surface so the prompt-driven layer can select from supported analysis options

## Eventual Milestones

Once the current upstream annotation boundary is stable, the platform can grow toward the broader annotation and curation workflow described in the project notes. Eventual milestones include:

* consensus annotation with EVidenceModeler
* PASA-based gene model updates
* repeat filtering and cleanup
* functional annotation and quality control with tools such as BUSCO and EggNOG-mapper
* a user-facing prompt-to-workflow layer that helps researchers choose supported analyses without writing code

## Broader Impact

The long-term aim is to provide a shared platform that is useful in both research and teaching settings. For researchers, that means a reproducible, open-source workflow system that can support collaborative genome annotation and analysis on HPC resources. For students, it means a clearer path into computational genomics through documented stages, sample data, and predictable outputs. For computational biologists, it means a maintainable platform that can grow with the needs of a lab or research group without becoming a one-off pipeline.

In short, FLyteTest is intended to become a practical, extensible foundation for genomic studies: open source, HPC-friendly, easier to learn, and easier to adapt for real-world research.

## Existing Grant Solicitations

The project can be positioned for several active or recent funding opportunities that align with infrastructure, genomics, and computational biology:

* NSF 23-578: Infrastructure Innovation for Biological Research (Innovation)  
  https://www.nsf.gov/funding/opportunities/innovation-infrastructure-innovation-biological-research/nsf23-578/solicitation
* NSF 23-580: Infrastructure Capacity for Biological Research (Capacity)  
  https://www.nsf.gov/funding/opportunities/capacity-infrastructure-capacity-biological-research/nsf23-580/solicitation
* NIH Computational Genomics and Data Science Program, National Human Genome Research Institute  
  https://www.genome.gov/Funded-Programs-Projects/Computational-Genomics-and-Data-Science-Program
* NIH PAR 25-228: Investigator Initiated Innovation in Computational Genomics and Data Science (R01)  
  https://grants.nih.gov/grants/guide/pa-files/PAR-25-228.html
* NIH PAR 25-229: Investigator Initiated Innovation in Computational Genomics and Data Science (R21)  
  https://grants.nih.gov/grants/guide/pa-files/PAR-25-229.html
* NSF Enabling Discovery Through Genomics (EDGE)  
  https://www.nsf.gov/funding/opportunities/edge-enabling-discovery-through-genomics
* NIH PA-25-301: Research Project Grant R01  
  https://grants.nih.gov/grants/guide/pa-files/PA-25-301.html

These solicitations are best treated as possible proposal targets while the platform matures, especially as the project moves from the current pre-EVM milestone toward consensus annotation, functional annotation, and submission-preparation milestones.
