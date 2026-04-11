# Tool References

This directory is a local, manual tool-reference set for FLyteTest task authors and prompt-planning agents.

If you know the biological stage you want but not the exact tool file yet, start with [stage_index.md](/home/rmeht/Projects/flyteTest/docs/tool_refs/stage_index.md).

Use these files as tool-contract context, not as proof that a feature is
currently runnable. For implemented-vs-deferred status, check `README.md`,
`src/flytetest/registry.py`, and the relevant task or workflow module.

This project is intentionally taking a staged approach:

- these files are static markdown checked into the repo
- they are meant to support design, planning, and task implementation
- they are not a remote knowledge system
- they do not include fetch/query/update behavior
- they do not imply a full asset or MCP integration layer

Each reference file captures the standalone tool contract:

- purpose
- source inputs and outputs
- primary official documentation links
- tutorial or training references when they materially help
- repo-oriented native command context
- repo-oriented Apptainer command context
- a per-tool prompt template for future sessions
- important caveats or implementation notes

Human-readable role:

- explain what a bioinformatics tool does in its own native contract
- show the input and output shapes FLyteTest cares about for that tool
- make assumptions visible without turning the file into a full external manual

Coding-agent role:

- help select the right tool boundary before editing code
- provide repo-oriented command context for implementation or smoke-test plans
- supply prompt scaffolding while still requiring registry/code checks for exact
  supported names and current scope
- keep dynamic workflow generation grounded in typed, replayable plans rather
  than invented one-off tool chains

These notes are concise working references, not replacements for official manuals. When the native tool contract is incomplete, this directory should say so explicitly rather than filling in undocumented details.

Preferred structure for each tool reference:

- `Purpose`
- `Input Data`
- `Output Data`
- `Key Inputs`
- `Key Outputs`
- `Pipeline Fit`
- `Official Documentation`
- `Tutorial References`
- `Code Reference`
- `Native Command Context`
- `Apptainer Command Context`
- `Prompt Template`
- `Notes And Caveats`

Many existing references still use `Key Inputs` / `Key Outputs` instead of
`Input Data` / `Output Data`; that is acceptable as long as the file still makes
the native tool contract explicit and does not fold in stage wiring.

Use `Tutorial References` as the standard heading name for any section that
points to training material. Older `Tutorial And Training` variants are still
understandable, but new or touched files should prefer the shorter title so the
set stays visually consistent.

The command-context sections should stay short and repo-oriented:

- show the kinds of files FLyteTest passes to the tool
- use local fixture or results-bundle paths where that helps
- prefer command patterns over full executable walkthroughs
- state clearly when a command shape is inferred from official docs, the repo's
  own implementation, or staged-order notes
- avoid turning the file into a full external tool manual

The prompt-template sections should be practical handoff blocks for the tool
boundary itself:

- keep them copy-pasteable
- name the relevant FLyteTest task or workflow boundary when known
- mention the expected local file context for the tool inputs and outputs
- call out whether the tool is implemented, partial, or future work
- ask for assumptions to be surfaced explicitly instead of silently invented

Stage composition, workflow order, and exact upstream/downstream boundary
expectations belong in the stage-specific workflow docs and prompt templates,
not in the native tool contract itself. For example, a tool ref should explain
what RepeatMasker, AGAT, or Salmon expects and emits, while a separate stage
doc can explain how FLyteTest wires that tool into a repeat-filtering,
annotation-cleanup, or quantification workflow.

Current milestone note:

- the EVM-related docs now split the boundary into input preparation and explicit EVidenceModeler execution
- the repeat-filtering docs now split RepeatMasker conversion, gffread protein extraction, and funannotate cleanup into explicit task-stage references
- see `evidencemodeler.md` for the consensus-stage reference, the new repeat-filtering tool refs for the post-PASA cleanup stage, and the main README for the implemented workflow surfaces
- see `stage_index.md` for the stage-oriented entrypoint that groups prompt templates by transcript evidence, PASA, protein evidence, BRAKER3, EVM, repeat filtering, QC, functional annotation, AGAT, and submission-prep intent
