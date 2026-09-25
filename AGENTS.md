# linfilesearch — project instructions

Workspace scope. Global standards load first from ~/.zcode/AGENTS.md; this file
only adds what is specific to this project. Additive changes only — never modify
universal standards here.

- Description: native Linux GTK3 file-search utility built on mikesdatawork/gtk-python-dashboard-starter; searches all mountpoints incl. external drives; Phosphor icon tool buttons
- Bootstrapped: 2026-09-25 by s003_workspace_bootstrap_a.sh
- Ledger: ~/projects/Zai-ZCode/s-register.md

## Stack
- Python 3.12 (system python3, PyGObject via system packages; run with `python3 src/main.py`)
- GTK 3 (PyGObject, gi), pycairo, Pillow (per starter requirements.txt)
- Run: `./run.sh` or `python3 src/main.py` — app is live-tested on X11 (:0)
- Icons: Phosphor (MIT) — master library ~/projects/assets/icons (1512×6 weights), project subset resources/icons/{regular,fill} (53 icons each, manifest.txt maps use)
- Docs: docs/file-search-concept.md (technical concept), docs/mockups/ (3 UI mockups + index + baseline screenshot), docs/starter-README.md
- No test framework yet (tests/ empty)

## Project rules
(add project-specific rules as new entries; do not restate global rules)

## Change tracking
- changelog.md at repo root — append-only; every completed change gets an entry

## Memory
- .zcode/memory/decisions.md — architectural decisions with rationale
- .zcode/memory/pending.md — unfinished work carried between sessions
