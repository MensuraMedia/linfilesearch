# Changelog — linfilesearch

Append-only. Newest entries at the bottom. One entry per completed change.

## 2026-09-25
- Project bootstrapped with development standards (s003_a).
- Vendored gtk-python-dashboard-starter into src/, resources/, run.sh (docs/starter-README.md kept; demo gif excluded); live-launched and operator-tested on X11.
- Phosphor icon library downloaded to ~/projects/assets/icons via s011_c (1512 icons × 6 weights, MIT).
- Icon subset installed to resources/icons/{regular,fill} via s012_a (53 icons × 2, manifest.txt).
- Technical concept written: docs/file-search-concept.md (features, mountpoint handling, engine, icon system, roadmap).
- UI mockups A/B/C + review index built in docs/mockups/ with real icons; screenshots archived (mockup-a/b/c.png); all three verified defect-free by image analysis; index.html presents them with the live-starter baseline.
- Operator selected direction: A + collapsible right preview pane (r004). Mockup A2 built as interactive fold-out (eye tool / rail / caret toggle; #collapsed URL preset); both states rendered and verified; column-clipping and edge-spacing defects found by image analysis and fixed; review index updated with A+ card. IAB screenshot capability broke mid-session; captures moved to headless Firefox.
