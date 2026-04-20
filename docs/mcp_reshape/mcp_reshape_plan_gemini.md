# Scientist-Centered MCP: Less Heuristic, More Natural, Family-Extensible
*(Critiqued by Gemini for Agent Execution)*

## Context

### Why this change is happening
**Architecture Assessment:** **APPROVED**  
The rationale for moving away from fragile prose-based heuristics (`_extract_prompt_paths`, etc.) and moving towards a typed, data-first conversational approach makes architectural sense. The current orchestration involves too much mental overhead for the end user and violates the core goal outlined in `DESIGN.md`. Proceed with this direction.

### The four pillars this plan preserves
**Architecture Assessment:** **APPROVED**  
These 4 architectural pillars (Typed properties, Frozen specs, Pipeline families, and HPC-first design) represent the invariant truths of FlyteTest. Ensuring this refactor sits firmly on top of them is the correct approach. Do not violate these constraints.

### Two ideas borrowed from `../stargazer/`
**Architecture Assessment:** **CRITIQUE - MISSING EXECUTION**  
The idea to split task vs. workflow and use curated resource bundles is conceptually sound. However, there is a critical gap in execution: the plan mentions `load_bundle("m18_busco_demo")` as a vital element of this transition, but the implementation for the `bundles.py` infrastructure and the actual MCP tool definitions (`list_bundles`, `load_bundle`) are entirely omitted from the "Changes (with concrete code)" section below. You will need to implement this missing layer.

### Family extensibility is load-bearing
**Architecture Assessment:** **APPROVED**  
Decoupling biology concerns (families) from MCP architecture concerns is strong. The callout regarding the lingering `TASK_PARAMETERS` coupling is accurate and deferring it to a later milestone is an acceptable compromise to tightly scope this immediate refactor.

### What already exists (do not reimplement)
**Architecture Assessment:** **APPROVED**  
Leveraging existing tools and registries without rebuilding the wheel is standard best practice.

### Outcome
**Architecture Assessment:** **CRITIQUE - HALLUCINATED DEPENDENCIES**  
The outcome describes an elegant workflow (`list_entries` -> `list_bundles` -> `load_bundle` -> `run_workflow`). Unfortunately, as noted above, half of this outcome relies on hallucinated code in the proposed changes. You must implement the bundle tools to achieve this outcome. Furthermore, the actual API reshaping in the implementation does not match the engine's current state.

### Backward compatibility — intentional coordinated migration
**Architecture Assessment:** **AGREE WITH INTENT, UPDATE EXECUTION**  
The plan calls for a hard-break API change, updating `tests`, `docs`, and dependent scripts all at once. This intentional abandonment of backward compatibility for a cleaner domain model is approved. However, the subsequent code fails to *actually* break compatibility at the lowest level (`plan_typed_request` is left alone and called with incorrect types). **Directive:** You must go further than the original plan and explicitly refactor `plan_typed_request` so it accepts the structured kwargs directly, tearing out the NLP string parsing entirely.

---

## Changes (with concrete code)

### 1. Widen the MCP `list_entries` tool
**Architecture Assessment:** **APPROVED**  
Adding filtering and metadata mapping for `pipeline_family` is correct and fully supported by the existing `RegistryCompatibilityMetadata`. Implement as proposed.

### 2. Reshape `run_task` in place (`server.py:995`)
**Architecture Assessment:** **BLOCKER - REQUIRES DIRECT REFACTOR**  
The suggested implementation code contains a fatal error. It calls:
```python
plan = plan_typed_request(
    biological_goal=entry.compatibility.biological_stage or task_name,
    target_name=task_name,
    explicit_bindings=explicit_bindings,
    ...
)
```
`plan_typed_request` in `src/flytetest/planning.py` currently requires a positional string `request` parameter to run through its intent-matching regex heuristics. It will throw a `TypeError` if called this way. 

**Directive to implementation agent:** You must extend the refactor into `planning.py` and modify `plan_typed_request` (or replace it) so it directly accepts structured targets and skips the `_planning_goal_for_typed_request(request)` text parsing step entirely. Alter `plan_typed_request` directly to support this structural shift.

### 3. Reshape `run_workflow` in place (`server.py:869`) — symmetric with `run_task`
**Architecture Assessment:** **CRITIQUE - INCOMPLETE**  
The argument for keeping `run_workflow` symmetrical with `run_task` is structurally sound. However, the proposed code snippet stops abruptly at `save_workflow_spec_artifact` and fails to include the execution step or the return payload format. Also, it suffers from the exact same `plan_typed_request` hallucination blocker as `run_task`. **Directive:** Ensure `tool_databases` consistency between tasks and workflows, fix the `plan_typed_request` call, and include the actual dispatch logic in your implementation.

### 4. Missing Element: `bundles.py` Implementation
**Architecture Assessment:** **BLOCKER - MISSING IMPLEMENTATION**  
The plan completely omitted the creation of `list_bundles` and `load_bundle` `@mcp.tool()` endpoints and the underlying `src/flytetest/bundles.py` registry. **Directive:** You must implement these tools from scratch to satisfy the requirements of the new data flow.
