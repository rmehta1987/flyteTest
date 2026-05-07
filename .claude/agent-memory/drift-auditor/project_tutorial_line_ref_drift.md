---
name: tutorial_line_ref_drift
description: Recurring drift class — line refs in docs/tutorials/user_authored_tasks/ lag behind code edits in src/flytetest/. Even after polish passes, individual citations get missed.
type: project
---

Tutorial chapters cite source code as `src/flytetest/<path>:<line>`. As code is added/removed, those citations need updating, but polish passes don't always catch every one.

**Why:** Observed in PR #12 (commit cb0927f, "docs(tutorial): polish pass — fix cross-links, line refs, add prev/next footers") which still missed at least two citations in `02_first_task.md` (both off by exactly 3 lines, suggesting one upstream edit was the cause). Other chapters (e.g., `04_manifests.md`) had been correctly updated for the same fact.

**How to apply:** When a docs polish pass is announced, sweep all `src/flytetest/<path>:<line>` citations across `docs/tutorials/` and verify each line refs the claimed content. Quick sweep:
```
rg -n 'src/flytetest/[^ )"`]+:\d+' docs/tutorials/
```
For each hit, fetch the named line and compare with the tutorial's claim. Flag any mismatch as HIGH severity (the polish pass *promised* line-ref fixes).

**Cross-tutorial consistency:** When the same fact (e.g., MANIFEST_OUTPUT_KEYS location, my_custom_filter location) is cited in multiple chapters, they should agree. Disagreement is itself drift.
