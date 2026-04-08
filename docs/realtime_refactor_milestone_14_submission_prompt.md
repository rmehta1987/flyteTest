Historical note: Milestone 14 landed on 2026-04-08 with generic asset sibling
names, `ManifestSerializable`, typed `AssetToolProvenance`, compatibility
exports, and resolver support for generic ab initio bundles.

Use this prompt only when reviewing or repairing the Milestone 14
asset-compatibility slice. For new work, start from the next unchecked
milestone in `docs/realtime_refactor_checklist.md`.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-14-generic-asset-compatibility.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md

If you were assigned a specialist role, also read the matching guide under
`.codex/agent/`.

Context:

- The current local asset layer still uses vendor-specific names such as
  `Braker3ResultBundle`, `StarAlignmentResult`, and
  `PasaCleanedTranscriptAsset`.
- The goal of Milestone 14 is to introduce generic biology-facing names and
  compatibility loaders without breaking manifest replay.
- Do not treat this as a hard rename or a manifest migration.
- Historical `run_manifest.json` files must remain readable and truthful.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-14-generic-asset-compatibility.md`.
2. Investigate the current implementation state in `types/assets.py`,
   `__init__.py`, `planner_adapters.py`, `resolver.py`, and the relevant tests.
3. Introduce generic asset aliases or sibling types while keeping legacy names
   available for backward compatibility.
4. Add a `ManifestSerializable` compatibility helper or mixin if it helps make
   manifest round-tripping more explicit.
5. Update planner adapters and resolver compatibility so the generic names are
   preferred without breaking older manifest shapes.
6. Add typed provenance metadata instead of an untyped catch-all dictionary
   wherever provenance needs to stay inspectable.
7. Add tests that prove legacy manifests still load and replay, and that the
   new generic names round-trip cleanly.
8. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
9. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
10. Stop when blocked, when a compatibility guardrail would be at risk, or
    when the next step would require a larger risky batch that should be split.

Important constraints:

- Keep old `run_manifest.json` files readable.
- Do not delete legacy class names until there is a deliberate migration path
  and compatibility aliases in place.
- Do not rewrite historical manifests in place.
- Keep planner adapters, resolver behavior, README, capability docs, and tests
  aligned.

Report back with:

- checklist item(s) completed
- files changed
- validation run
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```
