Use this prompt when starting Step 04 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§4)

Context:

- This is Step 04. Pure-additive — no existing code is touched. The server
  only learns about `list_bundles` / `load_bundle` in Step 25.

Key decisions already made (do not re-litigate):

- No module-level `_validate_bundles()` call. Availability is checked at
  call-time inside `list_bundles` / `load_bundle` so the server boots
  regardless of whether every seeded bundle's backing data is present.
- Bundles are keyed by planner-type name and inherit environment metadata
  from the registry entry's `execution_defaults` (§3c) — bundles should list
  only overrides / scientist-facing inputs, not duplicate the entry's defaults.
- Seed-bundle reality check (are the backing paths present under data/?) is
  Step 30 — do not audit in this step; stub as many bundles as seem useful.

Task:

1. Create `src/flytetest/bundles.py` matching the code in §4 of the master
   plan: `ResourceBundle` dataclass, `BundleAvailability` dataclass,
   `_check_bundle_availability(b)`, `list_bundles(pipeline_family=None)`,
   `load_bundle(name)`.

2. Seed with at least these entries (audit in Step 30 may drop some):
   `braker3_small_eukaryote`, `m18_busco_demo`, `protein_evidence_demo`,
   `rnaseq_paired_demo`. Each seed points at fixtures already present under
   `data/`; bundle paths are relative to the repo root.

3. `_check_bundle_availability` validates:
   - every `bindings[type][field]` ending in `_path` exists on disk,
   - every `runtime_images[key]` path exists,
   - every `tool_databases[key]` path exists,
   - every `applies_to` entry exists in the registry AND accepts the bundle's
     binding types AND shares the declared `pipeline_family`.

4. `load_bundle` raises `KeyError` for unknown names (with the list of
   available names in the message) and returns a `supported=False` reply
   with structured reasons for a known-but-unavailable bundle.

Tests to add (tests/test_bundles.py):

- `list_bundles()` returns every bundle with an availability flag.
- `list_bundles(pipeline_family="annotation")` filters.
- `load_bundle("m18_busco_demo")` happy path returns typed bindings + inputs
  + runtime_images + tool_databases + description + pipeline_family.
- `load_bundle("nonexistent")` raises `KeyError` with the available names.
- A monkeypatched bundle with a missing container returns supported=False
  with the path in `reasons`.
- `python -c "import flytetest.server"` still works when a bundle's backing
  path is removed (startup robustness invariant).

Verification:

- `python -m compileall src/flytetest/bundles.py`
- `pytest tests/test_bundles.py`
- `python -c "import flytetest.server"` succeeds

Commit message: "bundles: add curated ResourceBundle module (call-time availability)".

Then mark Step 04 Complete in docs/mcp_reshape/checklist.md.
```
