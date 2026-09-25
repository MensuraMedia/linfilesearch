# linfilesearch — Technical Concept

Status: draft for operator review (r003, 2026-09-25)
Base framework: mikesdatawork/gtk-python-dashboard-starter (GTK3 + Python, vendored into `src/`)
Icon set: Phosphor (MIT), master library `~/projects/assets/icons`, project subset `resources/icons/`

## 1. What this is

A native Linux desktop file-search utility. It finds files by name (and optionally by
content) across **all mounted filesystems** — the system root, the home partition,
permanently mounted data disks, and externally attached USB drives — without an index.
It is built on the vendored gtk-python-dashboard-starter template and keeps that
template's architecture, dark theming, and page-based routing.

Design goal: the familiar feature set of popular file-search tools (Everything,
locate/gnome-search-tool, fd/find, catfish) delivered as a responsive GTK3 app with
icon-based tool buttons.

## 2. Foundation: the starter framework

Inherited as-is from the vendored template:

| Starter element | Use here |
|---|---|
| `src/ui/dashboard_window.py`, `sidebar.py`, `content_area.py` | app shell: 150px sidebar, page routing |
| `src/pages/page_base.py` + page registry | new pages: Search, History, Saved, About, Settings |
| `src/config/config_themes.py` (7 dark themes) | unchanged; accent-aware icon tinting hooks in later |
| `src/modules/manager_navigation.py`, `manager_theme_applicator.py` | unchanged |
| `resources/css/style.css` | extended with search/table/statusbar classes |
| `resources/images/` | logo; icons live in the new `resources/icons/` |

New modules planned under the starter's conventions:

```
src/modules/manager_search.py      engine control (start/pause/stop, events)
src/modules/manager_mounts.py      mountpoint enumeration + change signals
src/pages/page_search.py           main search UI
src/pages/page_history.py          search history
src/pages/page_saved.py            saved searches
src/config/config_search.py        defaults, filter definitions, icon map
```

## 3. Feature set

**Query modes** — substring (default), case-sensitive toggle (`text-aa`), wildcard
(`asterisk`, fnmatch semantics), regular expression (`brackets-curly`). Mode is a
visible toggle group; the active mode is reflected in the accent color.

**Content search** (optional, off by default) — match text inside files: plain-text
first N KB, binary detection (NUL-byte probe), size cap, per-type skip list.

**Filters** — type (Documents/Images/Video/Audio/Archives/Source/Folders), size range,
modified-date range, hidden files, symlinks, excluded directory patterns
(`.git`, `node_modules`, caches).

**Scope** — the defining feature. Default: all mountpoints. The user can narrow to any
subset of mounts or add arbitrary folders (`plus-circle`). Scope chips show each mount
with a device-class icon and capacity.

**Results** — streaming list (matches appear while scanning): name, path, size, type,
modified, mountpoint; sortable columns; list or grid view; selection with keyboard
navigation; a locked row style marks unreadable paths.

**Result actions** — open (`arrow-square-out`), open containing folder (`folder-open`),
copy path (`copy`), move to trash (`trash`), properties (`info`), preview pane (`eye`).

**Search control** — start (`magnifying-glass`), pause/resume (`pause-circle`/`play`),
stop (`stop-circle`), live progress in the status bar: mounts being scanned, directories
visited, match count, elapsed time, skipped-count (`warning`).

**History & saved searches** — recent queries restorable in one click; named saved
searches (query + mode + filters + scope) persisted as JSON under `~/.config/linfilesearch/`.

## 4. Mountpoint handling (core requirement)

**Enumeration.** Primary source: `/proc/self/mounts` parsed for mount root, mountpoint,
filesystem type, and device. Device metadata (label, size) via `os.statvfs` and
`lsblk -J` fallback. User-facing names via GLib: `Gio.unix_mounts_get()` and
`Gio.UnixMountMonitor` for mount/umount change signals — a USB stick plugged in
mid-search appears in the Locations list without a restart. No hard dependency on
UDisks2/GVfs; they are optional enhancements later (eject button, MTP names).

**Classification.**

| Include by default | Exclude by default |
|---|---|
| ext2/3/4, btrfs, xfs, zfs, f2fs | procfs, sysfs, devpts, tmpfs, efivarfs, rpc_pipefs |
| ntfs/fuseblk, exfat, vfat (data partitions) | squashfs (snap loops), overlayfs |
| gvfs FUSE mounts (`/run/user/<uid>/gvfs/**`) | `/proc`, `/sys`, `/dev`, `/run` trees |

Exclusions are a settings-editable list of fs types and path prefixes. `/boot/efi`
(vfat) is excluded by default; a toggle exists.

**This machine (verified 2026-09-25):**

| Mountpoint | Device | Fs | Size | Default |
|---|---|---|---|---|
| `/` | nvme0n1p2 | ext4 | 98G | included |
| `/home` | nvme0n1p3 | ext4 | 1.7T | included |
| `/mnt/data` | sda1 (attached disk) | ext4 | 916G | included |
| `/boot/efi` | nvme0n1p1 | vfat | 511M | excluded |
| snap loops ×11, tmpfs ×5 | — | squashfs/tmpfs | — | excluded |

**Semantics.**
- One worker thread per selected mountpoint; each stays on its device
  (`os.stat().st_dev` check, `find -xdev` equivalent) so bind mounts and nested mounts
  cannot produce duplicate results.
- The same device reachable at two mountpoints is deduplicated by `(st_dev, inode)`.
- A mount that disappears mid-scan ends its worker gracefully (error recorded, not fatal).
- Unreadable directories are recorded as skipped (`warning` count, expandable list),
  never abort the search. A "no access" row style (`lock`) shows in results only when
  the operator enables it.
- Search-as-non-root: system paths outside the user's permissions are skipped silently
  unless "show locked paths" is on.

## 5. Search engine

Non-indexed streaming scan, chosen for v1 simplicity and correctness on rotating
external drives:

- `os.scandir` recursion per mount worker; entry metadata comes from the DirEntry
  where possible (one stat per file on most filesystems).
- Match pipeline: cheap name test first; content test only for survivors.
- Cancellation/pause via `threading.Event`; workers check it every directory.
- Results flow to the UI through a bounded queue; the GTK main thread drains it in
  `GLib.idle_add` batches (~200 rows / 100 ms) into a `Gtk.ListStore` + `Gtk.TreeView`
  (GTK3 virtualized — no row cap needed for realistic result sets).
- Progress counters are sampled, not per-file signals.
- Target throughput: ≥ 20k directory entries/sec/worker on warm ext4 (to be verified in
  a benchmark during implementation; not yet measured — assumed).

Indexing (mlocate-style or custom) is explicitly **out of scope for v1**; the
`database` icon marks its future home in the UI.

## 6. Icon system

- Source: Phosphor Icons, MIT license. Master library (1,512 icons × 6 weights) at
  `~/projects/assets/icons`, downloaded by `s011_download_phosphor_icons_c.sh`.
- Project subset: 53 icons × 2 weights (`regular`, `fill`) in `resources/icons/`,
  selected by `s012_icon_subset_select_a.sh`; `resources/icons/manifest.txt` maps every
  icon to its planned UI use.
- Weights: `regular` for tool buttons and rows; `fill` for active states and the logo.
- Loading: `GdkPixbuf.Pixbuf.new_from_file_at_size` at 16px (toolbar/rows) and 24px
  (nav), cached in a dict keyed by `(name, size, tint)`.
- Tinting: Phosphor SVGs are solid black. At load time the pixbuf is recolored to the
  theme's foreground/accent (Pillow `getchannel` mask + solid fill), so icons follow the
  7 starter themes without per-theme asset copies. (Implementation detail, to verify.)

Naming note: Phosphor has no `regex` icon — regex mode uses `brackets-curly`. There is
no `arrows-sort`; sort indicators use `sort-ascending` / `sort-descending`.

## 7. UI direction (see docs/mockups/)

Three mockups were built on the real starter palette (`#2d2d2d` window, `#353535`
sidebar, `#0078D7` accent, hairline `#1a1a1a`) with the real icon subset:

| Mockup | Layout | Best for |
|---|---|---|
| A — Dashboard Classic | starter sidebar + search page | maximal fidelity to the template |
| B — Compact Utility | single toolbar, dense two-line rows | speed of use, small window |
| C — Dual Pane + Preview | locations rail + results + preview pane | mount visibility & file inspection |

Common to all: query bar with mode toggles (Aa / * / .*), scope chips or rail with
device-class icons, icon tool buttons throughout, streaming status bar, blue-accent
selection states. `docs/mockups/index.html` presents all three side by side with the
live starter screenshot as baseline.

Open aesthetic decisions for the operator:
1. Which layout (A/B/C) is the primary direction?
2. Icons at 16px monochrome-white (mockups) vs accent-tinted when active?
3. Keep the 150px sidebar (A/C) or go chrome-less (B)?

## 8. Data flow

```
Gio.UnixMountMonitor ──change──► manager_mounts ──refresh──► Locations UI
                                          │
manager_search ──start(query, filters, scope)──► worker per mountpoint
      ▲                                            │ os.scandir recursion
      │pause/stop (Event)                          ▼
      │                              match pipeline: name → filters → content
      │                                            │
      └────GLib.idle_add batches◄──result queue────┘
                     │
              Gtk.ListStore / TreeView / status bar
```

## 9. Configuration & persistence

`~/.config/linfilesearch/` — `settings.json` (defaults, exclusions, window geometry),
`history.json` (recent queries, capped), `saved-searches/` (named searches).
Nothing else writes outside the XDG dirs. No secrets, no telemetry.

## 10. Non-goals (v1)

- Indexing / incremental index maintenance (marker icons only)
- Remote search over SSH/Samba (network mounts already scan if mounted)
- Content search inside binaries, archives, or office-file XML payloads
- GTK4/libadwaita port (starter is GTK3; revisit after v1)

## 11. Risks

| Risk | Mitigation |
|---|---|
| Slow scans on huge cold external drives | streaming results, pause/resume, per-mount progress, cancellable workers |
| GVfs/MTP mounts behave badly under scandir | fs-type exclusion list, per-mount error budget, worker isolation |
| GTK3 TreeView flooding on 500k+ matches | batched idle_add inserts, match cap setting with "load more" |
| Root-owned trees yielding permission noise | silent-skip default, explicit "show locked paths" toggle |

## 12. Roadmap

1. Operator picks mockup direction → freeze UI spec (this document §7).
2. `manager_mounts` + scope UI with real enumeration on this machine (3 mounts).
3. `manager_search` name-only streaming search end to end.
4. Filters, sort, result actions, status bar.
5. History + saved searches + settings page.
6. Content search (opt-in), preview pane.
7. Icon tinting across the 7 themes; benchmark pass; v1 tag.
