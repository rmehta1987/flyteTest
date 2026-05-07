<!-- drift-auditor agent memory index. -->
<!-- Add one line per memory file as you accumulate them. -->
<!-- Memory file frontmatter: name, description, type (user|feedback|project|reference). -->

- [Tutorial line-ref drift](project_tutorial_line_ref_drift.md) — sweep `rg -n 'src/flytetest/[^ )"\`]+:\d+' docs/tutorials/` after every polish/docs PR; cross-tutorial citations of the same fact should agree
- [Authoritative anchors](reference_authoritative_anchors.md) — canonical file:line for MANIFEST_OUTPUT_KEYS, SHOWCASE_TARGETS, FLAT_TOOLS, registry types; CHANGELOG-discipline rules; compat-critical surfaces
