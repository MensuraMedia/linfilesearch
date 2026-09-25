# linfilesearch

A native Linux desktop file-search utility built with GTK3 and Python.
It searches **all mounted filesystems** — the system root, the home partition,
permanently mounted data disks, and externally attached USB drives — without an
index, streaming results live with pause/stop control.

Built on [gtk-python-dashboard-starter](https://github.com/mikesdatawork/gtk-python-dashboard-starter)
(mikesdatawork). UI icons: [Phosphor Icons](https://phosphoricons.com/) (MIT).

## Features

- Name search with three modes: substring, wildcard (`* ? [ ]`, `find -name`
  semantics), and regular expressions — plus a case-sensitivity toggle
- Scope selection per mountpoint (device class + capacity shown), with
  live mount/umount awareness
- Streaming results (name, path, size, type, modified, mountpoint) in a
  sortable table with drag-reorderable columns
- Collapsible preview pane: metadata, text snippet, open / show-in-folder /
  copy path / trash actions
- Search history: every run recorded; single-click a former search to
  re-run it with all criteria prepopulated; bookmark any entry to Saved
- Seven dark themes inherited from the starter framework

## Running

```bash
python3 src/main.py          # system python3 with PyGObject (GTK 3)
```

or `./run.sh` (creates a venv and installs `requirements.txt`).

## Tests

```bash
python3 -m pytest tests/ -q
```

## Project layout

- `src/` — application code (`modules/` engine + managers, `pages/` UI pages,
  `ui/` shell, `config/` constants, `utils/` icon loading)
- `resources/icons/` — local Phosphor subset (see `manifest.txt`)
- `docs/` — technical concept and UI mockups (`docs/mockups/`)
- `tests/` — unit and UI-enforcement tests

## License

Copyright (c) 2026 MensuraMedia. Released under the
**Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

Free to use, copy, modify, and distribute, including remixes and builds upon
this work, with attribution. **Commercial use is prohibited without prior
permission from the author.** For commercial licensing, contact MensuraMedia.

See [LICENSE](LICENSE) for the full license text and
[the summary](https://creativecommons.org/licenses/by-nc/4.0/) for a plain-language
overview.
