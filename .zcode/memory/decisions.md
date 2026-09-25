# Decisions

Record architectural decisions with rationale. Newest at the bottom.

- 2026-09-25 (r003): Base framework vendored (copied, not referenced) from mikesdatawork/gtk-python-dashboard-starter — doctrine rule 1. GTK3/PyGObject, run via system python3.
- 2026-09-25 (r003): Phosphor icons (MIT) as the icon system. Master library machine-wide at ~/projects/assets/icons; project subset resources/icons/{regular,fill} with suffix-stripped names so one key works across weights. No `regex` icon exists in Phosphor → `brackets-curly`; no `arrows-sort` → `sort-ascending`/`sort-descending`.
- 2026-09-25 (r003): v1 search engine is non-indexed streaming scan (os.scandir, one worker per mountpoint, st_dev containment, Event-based pause/stop). Indexing deferred (non-goal v1).
- 2026-09-25 (r004): Operator picked UI direction: Mockup A — Dashboard Classic, plus a collapsible right preview pane (folds to a 36px icon rail). Reference: docs/mockups/mockup-a2-preview.html; verified in both states.
- 2026-09-25 (r005): Remote = private MensuraMedia/linfilesearch; design phase (b6bb7df) pushed.
- 2026-09-25 (r005): Wildcard mode uses fnmatch full-match semantics (same as find -name): `report*.odt` does NOT match `q3-financial-report.odt`; users write `*report*.odt` for match-anywhere. Invalid regex compiles to a never-matching predicate instead of raising.
- 2026-09-25 (r005): Mount classification: gvfs FUSE searchable; other FUSE (AppImage/portal mounts) skipped; /boot/efi excluded by prefix rule. Verified live: searchable = /, /home, /mnt/data.

