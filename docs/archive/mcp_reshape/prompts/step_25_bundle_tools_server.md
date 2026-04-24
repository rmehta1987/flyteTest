Use this prompt when starting Step 25 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§4 — bundles server wiring)

Context:

- This is Step 25. Depends on Step 04 (`src/flytetest/bundles.py`). Step 04
  landed the module as pure additions — nothing imports it yet. Step 25
  registers `list_bundles` and `load_bundle` as MCP tools on the server so
  scientists can reach them in the canonical experiment loop
  `list_entries → list_bundles → load_bundle → run_task / run_workflow`.

Key decisions already made (do not re-litigate):

- Availability is checked at call time (NOT at server import). A bundle
  whose backing path is missing surfaces `available=False` in `list_bundles`
  and `supported=False` in `load_bundle` — the server still boots.
- `list_bundles(pipeline_family: str | None = None)` filters by family
  when supplied; no family = all bundles.
- `load_bundle(name)` returns either (a) the typed bundle payload ready to
  spread into `run_task` / `run_workflow` (`bindings`, `inputs`,
  `runtime_images`, `tool_databases`, `description`, `pipeline_family`) or
  (b) a `BundleAvailabilityReply`-shaped decline if the bundle is
  registered but unavailable.
- `load_bundle("nonexistent")` raises `KeyError` with the list of available
  names in the message — the MCP layer catches it and returns a structured
  decline.

Task:

1. In `server.py`, add two `@mcp.tool()` wrappers:
   - `list_bundles(pipeline_family: str | None = None) -> list[dict]` —
     delegates to `bundles.list_bundles`, serializes each
     `BundleAvailability` via `asdict`.
   - `load_bundle(name: str) -> dict` — delegates to `bundles.load_bundle`;
     wraps `KeyError` into a structured decline (`supported=False`,
     `limitations=[<message>]`, `next_steps=["Call list_bundles() for the
     set of available names."]`).

2. Register both tools in `create_mcp_server()`.

3. Update `mcp_contract.py` so these two tools appear in the experiment-loop
   group (§6 — the full reframe lands in Step 27; here we just add the
   entries so they show up in `list_tools()`).

Tests to add (tests/test_server.py — bundles block):

- `list_bundles()` returns every seeded bundle with the expected keys.
- `list_bundles(pipeline_family="annotation")` filters correctly.
- `load_bundle("m18_busco_demo")` happy-path returns `bindings`, `inputs`,
  `runtime_images`, `tool_databases`, `description`, `pipeline_family`.
- `load_bundle` of a known-but-unavailable bundle (monkeypatch a missing
  path) returns `supported=False` with structured `reasons`.
- `load_bundle("nonexistent")` returns a structured `supported=False`
  decline, NOT an uncaught `KeyError`.
- Experiment-loop smoke test: `bundle = load_bundle("braker3_small_eukaryote");
  run_workflow("braker3_annotation_workflow", **bundle, source_prompt="...")`
  succeeds (this exercises the bundle-spread contract from Step 22).

Verification:

- `python -m compileall src/flytetest/server.py`
- `pytest tests/test_server.py`
- `python -c "import flytetest.server"` succeeds even with every bundle's
  backing path removed (regression check on the import-time invariant).

Commit message: "server: register list_bundles and load_bundle MCP tools".

Then mark Step 25 Complete in docs/mcp_reshape/checklist.md.
```
