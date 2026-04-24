Use this prompt when starting Step 30 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§13 — seed-bundle reality check)

Context:

- This is Step 30. Depends on Steps 04 (bundles module) and 25 (bundles
  wired into the server). The milestone's final sanity check: confirm
  every seeded bundle is honest on a fresh clone — either available, or
  unavailable with a useful `reasons` list. No hard-fails; no surprises.

Key decisions already made (do not re-litigate):

- Validation is RUNTIME, not import-time (§13 rewrite). The server boots
  regardless of which fixtures are present. `list_bundles()` /
  `load_bundle()` report availability structurally.
- The `demo_only=True` soft-warn flag was REJECTED. No new flag on
  `ResourceBundle`; no audit flag in the module code.
- Criterion: seed bundles alongside their fixtures. If a bundle's backing
  data (tool DBs, containers, typed bindings) is not present in a fresh
  clone, either ship the fixtures in the same commit or drop the bundle
  from `BUNDLES`. `list_bundles()` on a fresh clone should show every
  seeded bundle either `available=True` or `available=False` with a
  scientist-actionable reason.

Task:

1. Clean-clone check:
   - `git clean -ndx` (dry-run — DO NOT auto-delete) to understand what a
     fresh clone looks like relative to the working tree.
   - Better: `git worktree add /tmp/ft-clean main` and run the audit
     inside the clean worktree so the audit does not see your
     scratch/result files. Remove the worktree when done.

2. Inside the clean worktree:
   - `python -c "from flytetest.bundles import list_bundles; import json;
     print(json.dumps([
         {'name': b.name, 'available': b.available, 'reasons': b.reasons}
         for b in list_bundles()
     ], indent=2))"`
   - Inspect the output. For each `available=False` bundle, decide:
     (a) Ship the missing fixture in a same-commit follow-up (preferred
     for bundles tied to biology the scientist will hit in the showcase).
     (b) Drop the bundle from `BUNDLES` (for bundles whose backing data
     is too large to commit, e.g. a full BUSCO lineage or an EVM
     weight matrix).

3. For any bundle you keep with `available=False` because the backing
   data is external (e.g. a large tool database kept under `data/` but
   not in git), ensure the `reasons` list is actionable: the scientist
   should see a specific path to fetch or stage, not just a generic
   "missing".

4. If you drop a bundle from `BUNDLES`, also:
   - Remove references to it from `docs/mcp_showcase.md` /
     `docs/tutorial_context.md` (Step 29 may have cited it).
   - Add a note in the CHANGELOG entry (Step 28) that the bundle was
     considered and dropped pending fixture landing.

5. Re-run the audit. Every bundle in the final `BUNDLES` list must
   either:
   - `available=True` on a fresh clone, OR
   - `available=False` with a `reasons` list that tells the scientist
     which file under `data/` (or which `apptainer pull` command) to
     produce.

Tests to add (tests/test_bundles.py):

- `test_seeded_bundles_report_honestly` — iterate `list_bundles()`; for
  every unavailable bundle, assert `reasons` is non-empty and each reason
  contains either a path or an actionable hint.
- `test_showcase_bundle_is_available_in_repo` — the specific bundle cited
  in `docs/mcp_showcase.md` as the primary worked example is
  `available=True` on a fresh clone (guard against the docs walking a
  scientist into a dead end).

Verification:

- Clean worktree audit: every seeded bundle honest (manual inspection +
  the two tests above).
- `pytest tests/test_bundles.py`
- `python -c "import flytetest.server"` succeeds on a fresh clone even
  with every data fixture absent (regression check on §13).

Commit message: "bundles: audit seed set for fresh-clone honesty".

Then mark Step 30 Complete in docs/mcp_reshape/checklist.md.

Milestone close-out:

- Run the master plan's §Verification gates end-to-end. Every item in
  that block must pass before the milestone ships.
- Update `docs/realtime_refactor_checklist.md` to mark the MCP reshape
  milestone closed; archive the superseded planning docs under
  `docs/realtime_refactor_plans/archive/` per AGENTS.md §Behavior Changes.
```
