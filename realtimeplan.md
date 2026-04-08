## Realtime Branch Design With Comparative Positioning

### Summary

Rewrite [DESIGN.md](/home/rmeht/Projects/flyteTest/DESIGN.md) on branch `realtime` as an evolution of the current FLyteTest pipeline, not a copy of Stargazer. The new design should preserve the current registered BUSCO-era pipeline as the canonical baseline, while adding a runtime-generation architecture that is biologically typed, provenance-first, and competitive with the operational strengths that attract users to Nextflow and Snakemake.

The core architectural choice stays:

- registered workflows remain the default path
- runtime-generated tasks/workflows are a controlled fallback
- generated entities are typed runtime specs first, not Python codegen first
- planner-facing dataclasses must model biological analogs rather than raw file plumbing

### Comparison And Positioning

- `FLyteTest current state`
  - Current assets in [assets.py](/home/rmeht/Projects/flyteTest/src/flytetest/types/assets.py) are still local-path-centric and explicitly say there is no remote fetch/query/update or runtime asset-graph mutation.
  - Current planning in [planning.py](/home/rmeht/Projects/flyteTest/src/flytetest/planning.py) is narrow, explicit-path based, and tied to a tiny hard-coded execution surface.
  - Current registry in [registry.py](/home/rmeht/Projects/flyteTest/src/flytetest/registry.py) is static metadata, not an execution-aware compatibility graph.

- `Stargazer current state`
  - Stargazer already has typed `Asset` subclasses, query-based assembly, and an architecture that treats storage, tasks, workflows, and MCP as first-class layers: [overview.md](/home/rmeht/Projects/stargazer/docs/architecture/overview.md), [asset.py](/home/rmeht/Projects/stargazer/src/stargazer/assets/asset.py), [registry.py](/home/rmeht/Projects/stargazer/src/stargazer/registry.py).
  - It is the right inspiration for typed biological objects, registry introspection, and planner/executor separation.
  - It should not be copied verbatim because FLyteTest has different constraints: a notes-faithful genome annotation pipeline, existing milestone contracts, and a current local-first `File`/`Dir` execution surface.

- `Competitive target versus Nextflow and Snakemake`
  - Nextflow’s pull is strong HPC execution, per-process resources, container portability, caching/resume, DAG/reporting, and now lineage metadata. Sources: [Nextflow executors](https://www.nextflow.io/docs/latest/executor.html), [containers](https://nextflow.io/docs/latest/container.html), [cache/resume](https://www.nextflow.io/docs/latest/cache-and-resume.html), [reports](https://nextflow.io/docs/latest/reports.html), [data lineage](https://nextflow.io/docs/stable/tutorials/data-lineage.html).
  - Snakemake’s pull is simple rule authoring, explicit resources, strong SLURM/HPC ergonomics, and easy Apptainer/container integration. Sources: [Snakemake rules/resources](https://snakemake.readthedocs.io/en/v8.21.0/snakefiles/rules.html), [cluster execution](https://snakemake.readthedocs.io/en/v7.19.1/executing/cluster.html), [deployment/containers](https://snakemake.readthedocs.io/en/v9.1.5/snakefiles/deployment.html), [CLI Apptainer](https://snakemake.readthedocs.io/en/v9.17.0/executing/cli.html).
  - The `realtime` design should explicitly target parity on:
    - per-task resource declarations and overrides
    - per-task container/runtime selection
    - replayable provenance and resumability
    - graph visibility and previewability
    - explicit HPC-friendly execution mode
  - The differentiator should be typed biological planning and runtime workflow synthesis, not just “another workflow DSL.”

### Required Design Changes

- `Biological dataclass model`
  - Redefine the public planning/binding type system around biological objects such as `ReferenceGenome`, `ReadSet`, `TranscriptEvidenceSet`, `ProteinEvidenceSet`, `PasaAssembly`, `BrakerPredictions`, `ConsensusAnnotationInputs`, `RepeatFilteredAnnotation`, and `BuscoAssessmentTarget`.
  - Path fields remain execution bindings, not the primary conceptual identity.
  - The design should explicitly say these dataclasses represent the biological analog of task/workflow inputs.

- `Runtime spec model`
  - Add first-class `TaskSpec`, `WorkflowSpec`, `BindingPlan`, `ResourceSpec`, `RuntimeImageSpec`, and `GeneratedEntityRecord`.
  - `TaskSpec` must declare biological purpose, typed inputs, typed outputs, resource requirements, runtime/container requirements, and deterministic execution contract.
  - `WorkflowSpec` must declare DAG shape, typed edges, fanout/fanin behavior, stage ordering, and final output contract.
  - Generated specs must be replayable from manifest data alone.

- `Registry redesign`
  - The registry must evolve from catalog metadata into a compatibility graph over biological dataclasses.
  - Each entry must declare:
    - biological stage
    - accepted dataclass inputs
    - produced dataclass outputs
    - synthesis eligibility
    - resource/runtime defaults
    - compatibility constraints
  - Checked-in workflows remain the initial seed set and compatibility surface.

- `Planner redesign`
  - The planner must resolve prompts in this order:
    1. existing registered workflow
    2. composition of registered tasks
    3. generated `WorkflowSpec`
  - The planner must reject underspecified biology instead of inventing unsupported steps.
  - The planner must operate over biological dataclasses first, not prompt-extracted filesystem paths first.

- `Executor design`
  - V1 executor for `realtime` is a local typed-spec executor over existing registered tasks.
  - Generated Python module emission is explicitly deferred.
  - The design should preserve the current `flyte run --local` path for registered workflows while introducing a second execution path for generated specs.

- `Provenance and competitiveness`
  - Result manifests must record registered vs generated mode, bound biological dataclasses, task/workflow spec identity, generation prompt, assumptions, resources, runtime image choices, and replay metadata.
  - The design should add a DAG/preview/reporting section so the future system competes directly with the visibility users expect from Nextflow and Snakemake.

### Test And Acceptance Criteria

- `Design acceptance`
  - New `DESIGN.md` clearly distinguishes FLyteTest current state, `realtime` target state, and deferred features.
  - New `DESIGN.md` names Stargazer as inspiration for typed assets/registry/planner layering without adopting its storage model wholesale.
  - New `DESIGN.md` explicitly states the competitive goals versus Nextflow/Snakemake: HPC resources, containers, reproducibility, visibility, and resumability.

- `Architecture scenarios the design must cover`
  - Existing BUSCO-era workflows still run as registered workflows with unchanged milestone contracts.
  - A prompt that is not covered by a workflow but is covered by task composition produces a valid `WorkflowSpec`.
  - A prompt that implies unsupported biology is rejected or marked inferred rather than silently generated.
  - A generated workflow can be re-run from saved spec plus manifest metadata.
  - Planner-facing dataclasses can describe the annotation pipeline without requiring the user to think in raw filenames.

### Assumptions And Defaults

- Branch name is `realtime`.
- This is an in-place architectural evolution, not a replacement repo.
- Biological dataclasses become first-class in planner and registry first; execution signatures can continue to use `flyte.io.File` and `flyte.io.Dir` during migration.
- V1 runtime generation uses typed specs and a controlled executor, not codegen-first workflows.
- FLyteTest should borrow Stargazer’s typed-asset and registry ideas, but not its content-addressable storage architecture as a prerequisite.
- Competitive focus is specifically against the strengths users value in Nextflow and Snakemake, not against their DSL syntax.
- Branch creation and committing the current staged state remain separate follow-up actions once git identity is configured.
