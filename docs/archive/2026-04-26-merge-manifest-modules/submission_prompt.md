# Submission Prompt — Merge manifest modules into one

## Source

`CRITIQUE_REPORT.md` finding **ENG-03** (secondary track of the
2026-04-25 critique follow-up; deferred from that milestone).

## Goal

Collapse `src/flytetest/manifest_envelope.py` and
`src/flytetest/manifest_io.py` into a single `src/flytetest/manifest.py`
module. Today the two files cooperate but their split is
historical, not principled — readers chase a function across both
files to follow one manifest read or write.

## Read first

1. `AGENTS.md`
2. `src/flytetest/manifest_envelope.py`
3. `src/flytetest/manifest_io.py`
4. `tests/test_manifest_envelope.py`, `tests/test_manifest_io.py`
5. Every importer of either module (use `rg -l 'manifest_envelope|manifest_io' src tests`)

## Architectural intent

- One module owns the on-disk manifest contract end-to-end.
- Importers care about *what they want* (read manifest / write manifest /
  envelope shape), not which file holds the helper.
- No new abstractions. No new public surface. Just consolidation.

## In scope

- Move every public symbol from both modules into `manifest.py`.
- Update every importer to point at `manifest.py`.
- Merge or delete duplicated helpers if any exist (call out which were
  duplicated in the commit message).
- Keep both test files where they are; rename to `tests/test_manifest.py`
  only if combining them is obvious. Otherwise rename each to
  `tests/test_manifest_<read|write|envelope>.py` to keep ownership
  clear.

## Out of scope

- Changing the manifest schema, key set, or validation rules.
- Touching `MANIFEST_OUTPUT_KEYS` ownership (lives elsewhere; leave it).
- Refactoring callers beyond the import-line changes.
- Renaming `EnvelopeSerializable` or any other type in the public surface.

## Acceptance

- `rg -l 'manifest_envelope|manifest_io' src tests` returns zero hits
  (other than this prompt and the CHANGELOG history line).
- Full test suite passes: `PYTHONPATH=src python3 -m pytest tests/ -q
  --ignore=tests/test_compatibility_exports.py`.
- Test count is unchanged (or `+/- 0` after merging duplicate tests
  with explicit notes).

## Risk and stop conditions

- If the two modules import each other in a tight cycle that doesn't
  flatten cleanly, stop and report; don't paper over the cycle by
  introducing a third module.
- If a public symbol from either module is referenced by an external
  scripts directory you weren't expecting, stop and ask before deleting.

## Commit

`secondary-cleanup: merge manifest_envelope + manifest_io into manifest.py`

## Documentation

- One dated entry in `CHANGELOG.md` under `## Unreleased`.
- If `DESIGN.md` mentions either old module, update the reference.
