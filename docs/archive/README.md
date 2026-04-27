# `docs/archive/` — retention policy

This directory holds the last **60 days** of completed milestone plans,
submission prompts, and superseded design docs. Anything older is
recoverable from the git tag or commit at the time of archival, so the
working tree does not need to carry it forward.

The 60-day window keeps the archive useful for context-bridging across
recent work without bloating clones or muddying repository search. When
you want to know what happened more than 60 days ago, use `git log` and
`git show <ref>:docs/archive/<file>` rather than asking the working tree
to remember.

## Pruning workflow

When an entry crosses the 60-day boundary:

1. Confirm a summary (or strikethrough note) for the milestone exists in
   `CHANGELOG.md` *or* that the work was tagged at the time of merge.
2. If neither is true, leave the entry and add a one-line note on the
   checklist explaining why; do not silently delete.
3. Otherwise `git rm` the entry and let it live in git history.

## Archiving a new milestone

When archiving:

- preserve the original filename
- if the entry is a milestone folder, move the entire folder with one
  `git mv` so the prompts and checklist stay together
- if the entry was superseded for a specific reason, add a short note
  at the top of the file
- make sure the active checklist reflects the current status — the
  archive should not become the source of truth

## Current state

As of 2026-04-26, the oldest entry is from 2026-04-06 (20 days old), so
no entries qualify for pruning yet. The first deletions will land when
the 2026-04-06 entries cross the boundary on 2026-06-05.
