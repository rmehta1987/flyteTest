# Step 04 — Prune docs and test boilerplate

Three independent sub-steps. Each commits separately.

## 04a — Strip boilerplate test docstrings [ENG-05]

The exact sentence "This test keeps the current contract explicit and
guards the documented behavior against regression." appears as a docstring
in hundreds of tests. Delete every occurrence. Do not replace with a
different generic sentence.

```bash
rg -l 'This test keeps the current contract explicit' tests/
```

For each file, delete the boilerplate line *and* the surrounding triple-
quoted docstring if the docstring contains only that sentence. Keep
docstrings that have additional, test-specific content (rare).

Acceptance:
- `rg -c 'This test keeps the current contract explicit' tests/` returns
  zero hits.
- All 887 tests still pass.

Commit: `critique-followup: strip boilerplate test docstrings`

## 04b — Retention-prune `docs/archive/` [ENG-04]

1. Add `docs/archive/README.md` (or update if it exists) with a one-paragraph
   retention policy: "Anything older than 60 days is recoverable from git
   tags / commits at the time of archival; this directory holds only the
   last 60 days." Cite the rationale (search noise, clone bloat).
2. Identify entries older than the cutoff:
   ```bash
   find docs/archive -maxdepth 1 -type f -name '2026-0[1-2]-*'  # adjust
   ```
3. Verify each one is referenced from a tag or has its summary in
   `CHANGELOG.md` before deletion. If a milestone's outcome isn't captured
   anywhere else, leave the file and flag it.
4. `git rm` the rest.

Acceptance:
- `find docs/archive -maxdepth 1 -type f -name '*.md' | wc -l` is
  meaningfully smaller (target: <80).
- `docs/archive/README.md` documents the policy.

Commit: `critique-followup: retention-prune docs/archive (60-day window)`

## 04c — Split `CHANGELOG.md` [ENG-09]

Move entries older than 90 days into `CHANGELOG.archive.md`. Keep
`CHANGELOG.md` under ~500 lines.

1. Find the cutoff line in `CHANGELOG.md`.
2. `git mv` content via a manual split: copy the older block into
   `CHANGELOG.archive.md`, delete from `CHANGELOG.md`.
3. Add a 1-line "Older entries: see `CHANGELOG.archive.md`." pointer at
   the bottom of `CHANGELOG.md`.

Acceptance:
- `wc -l CHANGELOG.md` < 600.
- `CHANGELOG.archive.md` exists and contains the moved entries.

Commit: `critique-followup: split CHANGELOG.md, archive older entries`
