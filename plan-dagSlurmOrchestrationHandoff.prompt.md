## Plan: DAG Slurm Orchestration Handoff

Build the first dependency-aware scheduler for frozen WorkflowSpec artifacts as a Slurm-native execution path, not as a new always-on MCP-side orchestrator. Reuse the existing typed WorkflowSpec contract, durable run-record model, and replayable saved-artifact flow. The first slice should compile WorkflowSpec edges into a validated DAG, submit coarse stage-level jobs with explicit Slurm dependency clauses, and keep the current async Slurm poll loop focused on reconciliation and recovery rather than normal forward progress. For biology scope, start with the coarse branch structure already implied by docs/braker3_evm_notes.md: transcript evidence, protein evidence, and BRAKER3 can run in parallel; PASA and TransDecoder stay sequential; EVM remains a strict barrier; post-EVM work stays downstream.

**Handoff approach**
1. Use /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md as the primary checklist because this is platform and execution-architecture work. Update /home/rmeht/Projects/flyteTest/docs/refactor_completion_checklist.md only if user-visible biology boundaries or notes-faithful README pipeline claims change.
2. Treat this as a compatibility-preserving executor extension. Do not silently replace the current local or single-script Slurm execution paths until the DAG lane is validated and either gated behind a new path or proven compatible.
3. If implementation materially changes scope, create a dated detailed plan under /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/ and archive superseded plan docs rather than letting the slice drift informally.
4. Preserve inspectability: saved WorkflowSpec and BindingPlan artifacts remain the handoff boundary, and the implementation must not introduce a new DSL, opaque runtime code generation, or hidden biology changes.

**Proposed milestones**
1. Milestone DAG-1: DAG contract and graph compiler.
   - Reuse /home/rmeht/Projects/flyteTest/src/flytetest/specs.py as the source of truth. Compile WorkflowSpec.nodes, WorkflowSpec.edges, ordering_constraints, fanout_behavior, and fanin_behavior into validated dependency maps, deterministic ready sets, and topological ordering.
   - Detect cycles, dangling edges, duplicate node ids, and impossible joins before any execution or Slurm submission.
   - Keep the compiler execution-profile-agnostic so local and Slurm can share the same graph validation later.
   - Exit criteria: frozen specs with simple parallel branches and joins can be compiled offline with deterministic output.
   - Tests: graph compilation unit tests for cycle rejection, missing-node edges, deterministic ordering, and fan-in readiness.
2. Milestone DAG-2: Node-level execution boundary. depends on 1.
   - Refactor /home/rmeht/Projects/flyteTest/src/flytetest/spec_executor.py so the current sequential executor logic is decomposed into reusable helpers for node input binding, node execution, node result persistence, and final binding resolution.
   - Reuse the existing LocalNodeExecutionRequest, LocalNodeExecutionResult, _build_node_inputs(...), manifest helpers, and saved-artifact semantics instead of introducing a second data contract.
   - Exit criteria: one WorkflowNodeSpec or one dependency-ready batch can run independently from a frozen artifact without requiring the entire workflow loop.
   - Tests: unit coverage proving isolated node execution, output persistence, and unchanged result-contract behavior.
3. Milestone DAG-3: Parent DAG run record. depends on 1-2.
   - Add a dedicated parent run-record shape, preferably a new SlurmDagRunRecord or equivalent, that tracks the root DAG submission separately from the existing per-job SlurmRunRecord.
   - Record: DAG run id, artifact path, dependency graph snapshot, per-node state, child run-record paths, child Slurm job ids, aggregate DAG status, and failure or cancellation summaries.
   - Keep existing child SlurmRunRecord history intact so retry, reconciliation, and audit surfaces stay readable.
   - Exit criteria: a single DAG submission can be represented durably without overloading the single-job record semantics.
   - Tests: parent-record serialization, parent-child linkage, state aggregation, and backward-safe coexistence with existing child-job tools.
4. Milestone DAG-4: Slurm-native dependency submission. depends on 2-3.
   - Extend the Slurm submission path in /home/rmeht/Projects/flyteTest/src/flytetest/spec_executor.py so one DAG can render one script per node or per ready batch instead of one script for the whole workflow.
   - Submit root nodes immediately and downstream nodes with explicit Slurm dependency clauses such as afterok:jobid lists when dependencies are fully known at freeze time.
   - Keep /home/rmeht/Projects/flyteTest/src/flytetest/slurm_monitor.py observational: it should reconcile child and parent records, not be the happy-path mechanism that launches downstream jobs.
   - Exit criteria: a static DAG can progress through Slurm dependency chaining even if the MCP client disconnects after submission.
   - Tests: synthetic submission tests proving root jobs have no dependency metadata, downstream jobs carry derived dependency ids, and parent DAG records persist the linkage.
5. Milestone DAG-5: Biology mapping and per-node resource policy. depends on 1-4.
   - Represent the current BRAKER3/EVM baseline as a coarse DAG instead of a mostly linear wrapper over large monolithic stages. Start with transcript evidence, PASA alignment or assembly, TransDecoder, protein evidence, BRAKER3, EVM input prep, EVM execution, and downstream post-EVM packaging.
   - Preserve biological guardrails from /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md. PASA-backed sequencing stays sequential. EVM waits for transcript, protein, and ab initio evidence. Do not externalize chunk-level Exonerate or EVM partition fan-out in the first slice.
   - Add a scheduler-facing per-node resource resolution rule that starts from registry slurm_resource_hints and merges workflow-wide or future node-specific overrides without hardcoding biology-family constants into the scheduler.
   - Exit criteria: one notes-faithful coarse DAG with at least two parallel branches and one barrier can be frozen and submitted with explicit per-node resource choices.
   - Tests: composition or workflow-shape tests for node boundaries, resource-resolution tests, and regression coverage that current stage contracts remain honest.
6. Milestone DAG-6: DAG lifecycle surfaces. depends on 3-5.
   - Extend /home/rmeht/Projects/flyteTest/src/flytetest/server.py and related runtime surfaces so MCP can report DAG-level waiting, running, completed, failed, blocked, and cancelled states.
   - Cancellation should cancel active child jobs and persist the intent in the parent DAG record. Retry should remain conservative: prefer retrying failed child nodes whose dependencies are still satisfied before considering broader replay.
   - Extend list_slurm_run_history or related history surfaces so parent DAG runs and child job runs remain linked and inspectable.
   - Exit criteria: DAG status, cancellation, and history can be inspected without losing the existing child-job view.
   - Tests: server lifecycle tests for DAG-aware run, status, history, filter behavior, cancellation propagation, and conservative retry semantics.
7. Milestone DAG-7: RCC validation and documentation closeout. depends on 4-6.
   - Run one RCC proof that includes at least one parallel branch and one join, and verify that Slurm dependencies advance the graph without manual monitor intervention.
   - Update /home/rmeht/Projects/flyteTest/README.md, /home/rmeht/Projects/flyteTest/docs/mcp_showcase.md, /home/rmeht/Projects/flyteTest/docs/capability_maturity.md, /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md, and /home/rmeht/Projects/flyteTest/CHANGELOG.md to describe the landed behavior honestly.
   - If the milestone creates or materially revises a detailed slice plan, save it under /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/ and archive replaced versions.
   - Exit criteria: one end-to-end DAG proof is documented, tested, and reflected consistently across checklist and user-facing docs.
   - Tests: RCC smoke validation, targeted pytest slices, python -m py_compile on touched files, and git diff --check.

**Possible blockers**
- WorkflowSpec edges may not currently carry enough explicit binding detail for truly isolated node execution; some input resolution may still be implicitly coupled to the sequential executor.
- BindingPlan.resource_spec is currently workflow-level. Honest multi-job Slurm submission needs a clear per-node merge policy before resource selection is trustworthy.
- Static afterok chaining only works when downstream structure is known at freeze time. Runtime-discovered fan-out should stay out of the first slice.
- Parent and child run-record schema must stay readable and must not break current history, retry, and cancellation tooling that assumes one Slurm job per record.
- Some existing workflow modules may package too much biology into one stage to expose DAG boundaries cleanly without a broader refactor.
- Failure propagation needs deterministic blocked-state semantics so partial DAG failure does not look like ambiguous terminal completion.
- If scheduler dependency syntax, log-path management, or job-array behavior on RCC differs from assumptions baked into tests, the RCC validation lane may reveal cluster-specific follow-up work.

**Tests**
1. Graph compiler unit tests in /home/rmeht/Projects/flyteTest/tests/test_spec_executor.py or a new focused DAG test module: cycle rejection, missing edge endpoints, deterministic ready sets, fan-in join readiness, and serialized graph stability.
2. Node execution tests: prove one node can run from a frozen artifact with explicit bound inputs, persist outputs, and preserve manifest shape without the whole sequential workflow loop.
3. Slurm submission tests in /home/rmeht/Projects/flyteTest/tests/test_spec_executor.py and /home/rmeht/Projects/flyteTest/tests/test_server.py: root jobs submit without dependencies, downstream jobs submit with afterok dependency metadata, and parent DAG records link child run records correctly.
4. Monitor aggregation tests in /home/rmeht/Projects/flyteTest/tests/test_slurm_async_monitor.py: parent DAG status moves through waiting, running, completed, failed, blocked, and cancelled based on child states while slurm_poll_loop remains observational.
5. Server lifecycle tests in /home/rmeht/Projects/flyteTest/tests/test_server.py: DAG-aware run, status, history, cancellation, retry, and filter behavior.
6. RCC validation: submit one coarse DAG with parallel transcript and protein or BRAKER branches plus an EVM barrier, confirm automatic downstream advancement, verify durable parent and child history, and confirm cancellation propagation.
7. Hygiene checks: python -m py_compile on touched Python files, targeted pytest slices for executor, server, and monitor coverage, and path-scoped git diff --check.

**Relevant files**
- /home/rmeht/Projects/flyteTest/AGENTS.md — repo rules, Slurm assumptions, checklist and changelog expectations.
- /home/rmeht/Projects/flyteTest/DESIGN.md — architecture source of truth for saved-artifact execution.
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md — biological source plan that defines the branch and barrier structure to preserve.
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md — primary checklist for this slice.
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md — capability framing that should be updated when the DAG lane lands.
- /home/rmeht/Projects/flyteTest/src/flytetest/specs.py — WorkflowSpec and edge metadata contract.
- /home/rmeht/Projects/flyteTest/src/flytetest/spec_executor.py — current sequential executor and current Slurm submission path; main refactor surface.
- /home/rmeht/Projects/flyteTest/src/flytetest/composition.py — existing edge materialization and graph-shape reuse surface.
- /home/rmeht/Projects/flyteTest/src/flytetest/planning.py — typed planning and saved-artifact preparation that must remain inspectable.
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py — source of reusable stage metadata and Slurm resource hints.
- /home/rmeht/Projects/flyteTest/src/flytetest/server.py — MCP execution surface, history, and lifecycle APIs.
- /home/rmeht/Projects/flyteTest/src/flytetest/slurm_monitor.py — async reconciliation layer; should remain observational.
- /home/rmeht/Projects/flyteTest/src/flytetest/workflows/transcript_evidence.py — transcript-stage boundaries and likely DAG decomposition point.
- /home/rmeht/Projects/flyteTest/src/flytetest/workflows/protein_evidence.py — protein-evidence path and internal chunking boundaries.
- /home/rmeht/Projects/flyteTest/src/flytetest/workflows/consensus.py — EVM-oriented barrier and downstream consensus surfaces.
- /home/rmeht/Projects/flyteTest/tests/test_spec_executor.py — executor and DAG compiler regression coverage.
- /home/rmeht/Projects/flyteTest/tests/test_server.py — MCP submission, history, cancellation, and lifecycle regression coverage.
- /home/rmeht/Projects/flyteTest/tests/test_slurm_async_monitor.py — async reconciliation and aggregate-state coverage.

**Scope boundaries**
- Included: static DAG compilation from frozen WorkflowSpec artifacts, Slurm dependency submission for known graphs, parent-child durable run records, coarse stage-level BRAKER3 or EVM DAG mapping, DAG-level status or cancel or history surfaces, and RCC validation for automatic advancement.
- Excluded from the first slice: runtime-discovered fan-out, chunk-level Exonerate or EVM partitions as external DAG nodes, push notifications, cache-hit reuse beyond current resumability gates, remote durable asset indexing, and a new workflow DSL.

**Decisions**
- Scope: generic DAG scheduling for frozen WorkflowSpec artifacts, not a BRAKER3-only orchestrator.
- First execution slice: Slurm-native DAG orchestration first, not a local-first scheduler.
- Recommended advancement style: prefer Slurm afterok dependency chaining when the graph is known at freeze time.
- First biology slice: coarse stage-level parallelism only.
- Polling model: keep slurm_poll_loop observational and reconciliation-focused.
- Compatibility rule: preserve deterministic saved-artifact behavior and existing single-job history semantics while layering DAG support on top.

**Handoff prompt**
Continue the FLyteTest realtime architecture work under /home/rmeht/Projects/flyteTest/AGENTS.md and /home/rmeht/Projects/flyteTest/DESIGN.md. Use /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md as the primary checklist for this slice, and only update /home/rmeht/Projects/flyteTest/docs/refactor_completion_checklist.md if user-visible biology boundaries or notes-faithful README claims change. Read the relevant repo guides under /home/rmeht/Projects/flyteTest/.codex/, especially documentation, testing, tasks, and workflows. Then inspect /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md, /home/rmeht/Projects/flyteTest/docs/capability_maturity.md, /home/rmeht/Projects/flyteTest/src/flytetest/specs.py, /home/rmeht/Projects/flyteTest/src/flytetest/spec_executor.py, /home/rmeht/Projects/flyteTest/src/flytetest/composition.py, /home/rmeht/Projects/flyteTest/src/flytetest/server.py, /home/rmeht/Projects/flyteTest/src/flytetest/slurm_monitor.py, /home/rmeht/Projects/flyteTest/tests/test_spec_executor.py, /home/rmeht/Projects/flyteTest/tests/test_server.py, and /home/rmeht/Projects/flyteTest/tests/test_slurm_async_monitor.py. Implement only the first DAG-orchestration slice with these constraints: generic WorkflowSpec scope, Slurm-native first, coarse stage-level BRAKER3 or EVM nodes only, no new DSL, preserve saved-artifact inspectability, keep slurm_poll_loop observational, and prefer Slurm dependency chaining over an always-on MCP orchestrator. Work in milestone order: DAG compiler, node-level execution boundary, parent DAG run record, Slurm dependency submission, coarse biology mapping plus per-node resource policy, then DAG lifecycle surfaces. Add focused offline tests before any RCC validation. Update README, mcp_showcase, capability_maturity, realtime_refactor_checklist, CHANGELOG, and any new detailed plan doc if behavior changes. Report back with completed milestone slices, files changed, validation run, checklist status, remaining blockers, and any scope reductions or deferred follow-ups.