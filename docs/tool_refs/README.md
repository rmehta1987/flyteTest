# Tool References

This directory is a local, manual tool-reference set for FLyteTest task authors and prompt-planning agents.

If you know the biological stage you want but not the exact tool file yet, start with [stage_index.md](/home/rmeht/Projects/flyteTest/docs/tool_refs/stage_index.md).

It is similar in spirit to Stargazer-style tool reference directories, but this repo is intentionally taking a staged approach:

- these files are static markdown checked into the repo
- they are meant to support design, planning, and task implementation
- they are not a remote knowledge system
- they do not include fetch/query/update behavior
- they do not imply a full asset or MCP integration layer

Each reference file captures:

- purpose
- key inputs
- key outputs
- where the tool fits in the annotation pipeline
- primary official documentation links
- tutorial or training references when they materially help
- repo-oriented native command context
- repo-oriented Apptainer command context
- a per-tool prompt template for future sessions
- important caveats or implementation notes

These notes are concise working references, not replacements for official manuals. When pipeline notes are incomplete, this directory should say so explicitly rather than filling in undocumented details.

Preferred structure for each tool reference:

- `Purpose`
- `Key Inputs`
- `Key Outputs`
- `Pipeline Fit`
- `Official Documentation`
- `Tutorial References`
- `Native Command Context`
- `Apptainer Command Context`
- `Prompt Template`
- `Notes And Caveats`

The command-context sections should stay short and repo-oriented:

- show the kinds of files FLyteTest passes to the tool
- use local fixture or results-bundle paths where that helps
- prefer command patterns over full executable walkthroughs
- state clearly when a command shape is inferred from notes or current code
- avoid turning the file into a full external tool manual

The prompt-template sections should be practical handoff blocks:

- keep them copy-pasteable
- name the relevant FLyteTest task or workflow boundary when known
- mention the expected local file context
- call out whether the stage is implemented, partial, or future work
- ask for assumptions to be surfaced explicitly instead of silently invented

Current milestone note:

- the EVM-related docs now split the boundary into input preparation and explicit EVidenceModeler execution
- the repeat-filtering docs now split RepeatMasker conversion, gffread protein extraction, and funannotate cleanup into explicit task-stage references
- see `evidencemodeler.md` for the consensus-stage reference, the new repeat-filtering tool refs for the post-PASA cleanup stage, and the main README for the implemented workflow surfaces
- see `stage_index.md` for the stage-oriented entrypoint that groups prompt templates by transcript evidence, PASA, protein evidence, BRAKER3, EVM, repeat filtering, QC, and submission-prep intent
