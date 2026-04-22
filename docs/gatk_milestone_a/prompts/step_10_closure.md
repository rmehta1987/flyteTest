Use this prompt when starting Step 10 or when handing it off to another session.

Model: Sonnet sufficient — mechanical consolidation + docs sweep.

```text
You are closing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.4, §8)

Context:

- This is Step 10 (Closure). Depends on Steps 01–09 (all planner types,
  env, registry, and seven tasks land).
- Consolidates contract tests, emits a tool-reference doc, refreshes
  agent-context docs, writes the final CHANGELOG entry, and produces a
  Milestone A submission prompt.

Key decisions already made (do not re-litigate):

- Tool-reference doc is separate from the plan (per-command rationale +
  Stargazer citation; mirrors `docs/tool_refs/` convention).
- Submission prompt format mirrors prior
  `docs/realtime_refactor_milestone_*_submission_prompt.md` files.
- Agent-context docs (`AGENTS.md`, `.codex/registry.md`, `DESIGN.md`)
  get only the minimal updates needed to document the new family.

Task:

1. Registry manifest-contract coverage. Extend
   `tests/test_registry_manifest_contract.py` (or the current contract
   test file — `rg "MANIFEST_OUTPUT_KEYS" tests/` to confirm) so each
   of the seven variant_calling task module exports matches its
   `RegistryEntry.outputs[*].name` set. Ensure a single parametrized
   test covers all seven entries.

2. Create `docs/tool_refs/gatk4.md`:
   - One `## <task_name>` section per task, in pipeline stage order.
   - For each section: GATK tool name, FLyteTest task function path,
     command shape, key argument rationale, Stargazer source citation
     (`stargazer/src/stargazer/tasks/gatk/<file>.py:<line-range>`),
     and Milestone A scope notes (e.g., "whole-genome only",
     "requires indexed known-sites").

3. Agent-context refresh:
   - `AGENTS.md` Project Structure — under `Registry package`, add
     `_variant_calling.py — GATK4 germline variant calling family`.
     Under Tasks section, add `variant_calling.py` to the family list.
   - `.codex/registry.md` — list `variant_calling` as a supported family
     (if the file enumerates families).
   - `DESIGN.md` — add a one-paragraph note under the pipeline-family
     section describing Milestone A's BAM-in, VCF-out surface and
     pointing at `docs/gatk_milestone_a/`.

4. Grep gate (guardrail against Stargazer-pattern bleed-in):
   - `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB|_storage\.default_client" src/flytetest/tasks/variant_calling.py`
     → zero hits. If anything matches, fix before closing.

5. CHANGELOG.md milestone-level closing entry under `## Unreleased`:

   ```
   ### GATK Milestone A — Germline variant calling task foundation (YYYY-MM-DD)

   Closes Milestone A of the Phase 3 GATK port (tracker:
   `docs/gatk_milestone_a/checklist.md`). Lands the AlignmentSet /
   VariantCallSet / KnownSites planner types, the variant_calling_env +
   registry family, and seven GATK4 tasks that turn an aligned, dedup'd
   BAM into a joint-called VCF (BQSR → HaplotypeCaller → CombineGVCFs →
   GenomicsDBImport + GenotypeGVCFs). Alignment/dedup and VQSR are out
   of scope and deferred to Milestones B / C.

   - [x] YYYY-MM-DD planner types + registry + seven tasks landed
   - [x] YYYY-MM-DD tool reference doc at docs/tool_refs/gatk4.md
   - [x] YYYY-MM-DD agent-context refresh (AGENTS.md, .codex/registry.md, DESIGN.md)
   - [x] YYYY-MM-DD full pytest green; import smoke clean on fresh clone
   ```

6. Submission prompt at `docs/gatk_milestone_a_submission_prompt.md`:
   - Short doc (≤100 lines) describing the milestone, its exit
     criteria, and pointing at `docs/gatk_milestone_a/` for detail.
   - Lists the seven tasks and the three planner types by name.
   - States Milestone B and C as the next scoping targets.

Tests to add / extend:

- Parametrized `test_variant_calling_manifest_output_keys_align` in the
  registry contract test file — covers all seven tasks.
- Confirm full suite green: `pytest -xvs`.

Verification (the §8 gates in the master plan — all must pass):

- `python -m compileall src/flytetest/`
- `pytest tests/test_variant_calling.py -xvs`
- `pytest tests/test_registry_manifest_contract.py -xvs`
- `pytest tests/test_planner_types.py -xvs`
- `pytest` — full suite green.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py`
  → zero hits.
- `rg "variant_calling" src/flytetest/registry/__init__.py` → matches.
- `python -c "import flytetest.server"` → clean on fresh clone.
- MCP `list_entries(pipeline_family="variant_calling")` returns all
  seven tasks with typed interface fields.

Commit message: "variant_calling: close Milestone A — contract tests, tool ref, agent-context sweep".

Then mark Step 10 Complete in docs/gatk_milestone_a/checklist.md and
set the milestone status to Complete at the top of that file.
```
