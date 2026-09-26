"""
Search Page
Main file-search UI: query bar with mode toggles, mountpoint scope chips,
icon toolbar, streaming results table, status bar, and a collapsible
preview pane (fold-out, per mockup A2).
"""

import os
import queue
import time

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Pango

from pages.page_base import BasePage
from modules.manager_search import SearchEngine, make_matcher
from config.config_search import (
    ICONS, MODE_SUBSTRING, MODE_WILDCARD, MODE_REGEX, DEFAULTS,
    file_type_info, TEXT_EXTS)
from utils.icon_loader import get_icon, get_image, MOUNT_TINT, ACCENT_TINT
from utils.treeview_utils import attach_spreadsheet_behavior, set_text_index
from utils.preview import preview_for
from config.config_layout import Layout, RESULTS_MIN_WIDTHS

BUTTON_ICON_SIZE = Layout.dimensions.MAIN_BUTTON_ICON_SIZE
BUTTON_MAX_H = Layout.dimensions.MAIN_BUTTON_MAX_HEIGHT
BUTTON_MAX_W = Layout.dimensions.MAIN_BUTTON_MAX_WIDTH
BUTTON_TARGET_H = Layout.dimensions.MAIN_BUTTON_TARGET_HEIGHT
SEARCH_ROW_H = Layout.dimensions.SEARCH_ROW_HEIGHT
ROW_ICON_SIZE = Layout.dimensions.SEARCH_ROW_ICON_SIZE
STOP_RED_TINT = (0xd9, 0x53, 0x4f)      # running-state stop colour (r015)


def pin_button_height(btn, height=None):
    """Pin a main-page button to the target height (operator rules r006/r008)."""
    btn.set_property('height-request', height or BUTTON_TARGET_H)
    return btn


def human_size(n):
    if n is None:
        return '—'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return f"{n:.0f} B" if unit == 'B' else f"{n:.1f} {unit}"
        n /= 1024


def format_mtime(mtime):
    """Render an mtime; corrupt/extreme values degrade to '—' instead of
    raising inside the drain callback (which would kill it for the session)."""
    if mtime is None:
        return '—'
    try:
        return time.strftime('%Y-%m-%d', time.localtime(mtime))
    except (OSError, OverflowError, ValueError):
        return '—'


class SearchPage(BasePage):
    """File search page (A+ layout: dashboard + fold-out preview)."""

    def __init__(self, mount_manager, history_manager=None):
        self.mounts = mount_manager
        self.history = history_manager
        self.engine = None
        self._active_record = None
        self._search_state = 'idle'
        self.mode = DEFAULTS['mode']
        self.case_sensitive = DEFAULTS['case_sensitive']
        self.mount_buttons = {}
        self.preview_visible = True
        super().__init__(spacing=12, margin=24)
        self.set_homogeneous(False)

    # ------------------------------------------------------------- build

    def build_content(self):
        self.get_style_context().add_class('search-page')
        self.build_search_row()
        self.build_toolbar()
        # progress line sits ABOVE the results (operator rule r016), evenly
        # spaced between the mountpoint chips row and the spreadsheet
        self.build_statusbar()
        self.build_results_area()

        self.mounts.on_change(self._on_mounts_changed)
        self.populate_scope_chips()
        GLib.timeout_add(100, self._drain_results)

    def build_search_row(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.get_style_context().add_class('search-row')

        self.query_entry = Gtk.Entry()
        self.query_entry.set_placeholder_text(
            "Search file names — e.g. LinShot (substring) or LinShot* (wildcard)")
        self.query_entry.set_hexpand(True)
        self.query_entry.connect('activate', lambda w: self.start_search())
        # NB: widget margin (not CSS padding) is double-counted in natural
        # height — keep margin 0 and pad via .search-entry CSS (search-row-spec)
        entry_box = Gtk.Box(spacing=8)
        entry_box.get_style_context().add_class('search-entry')
        entry_box.set_property('height-request', SEARCH_ROW_H)
        entry_box.pack_start(get_image(ICONS['search'], ROW_ICON_SIZE), False, False, 0)
        entry_box.pack_start(self.query_entry, True, True, 0)
        row.pack_start(entry_box, True, True, 0)

        self.mode_buttons = {}
        mode_group = Gtk.Box(spacing=0)
        mode_group.get_style_context().add_class('mode-group')
        mode_group.set_property('height-request', SEARCH_ROW_H)
        for key, mode, label in (
                ('case', None, 'Aa'),
                ('wildcard', MODE_WILDCARD, '*'),
                ('regex', MODE_REGEX, '.*')):
            btn = Gtk.ToggleButton()
            btn.set_tooltip_text({
                'case': 'Match case', 'wildcard': 'Wildcard mode (* ? [ ])',
                'regex': 'Regular expression mode'}[key])
            box = Gtk.Box(spacing=6)
            box.pack_start(get_image(ICONS[key], ROW_ICON_SIZE), False, False, 0)
            box.pack_start(Gtk.Label(label=label), False, False, 0)
            btn.add(box)
            # strip carries a 1px border top/bottom: 36 + 2 = SEARCH_ROW_H
            btn.set_property('height-request', SEARCH_ROW_H - 2)
            btn.get_style_context().add_class('mode-toggle')
            btn.connect('toggled', self._on_mode_toggled, key)
            mode_group.pack_start(btn, False, False, 0)
            self.mode_buttons[key] = btn
        row.pack_start(mode_group, False, False, 0)

        self.pause_button = self._icon_button(
            ICONS['pause'], 'Pause search', self.on_pause_clicked,
            height=SEARCH_ROW_H - 2, icon_size=ROW_ICON_SIZE)
        self.stop_button = self._icon_button(
            ICONS['stop'], 'Stop search', lambda w: self.stop_search(),
            height=SEARCH_ROW_H - 2, icon_size=ROW_ICON_SIZE)
        # pause + stop form one connected control (r018)
        ps_group = Gtk.Box(spacing=0)
        ps_group.get_style_context().add_class('ps-group')
        ps_group.set_property('height-request', SEARCH_ROW_H)
        ps_group.pack_start(self.pause_button, False, False, 0)
        ps_group.pack_start(self.stop_button, False, False, 0)
        search_button = Gtk.Button()
        search_button.set_tooltip_text('Run search')
        b = Gtk.Box(spacing=8)
        b.pack_start(get_image(ICONS['search'], ROW_ICON_SIZE), False, False, 0)
        b.pack_start(Gtk.Label(label='Search'), False, False, 0)
        search_button.add(b)
        search_button.get_style_context().add_class('primary-button')
        search_button.set_property('height-request', SEARCH_ROW_H)
        search_button.connect('clicked', lambda w: self.start_search())

        row.pack_start(ps_group, False, False, 0)
        row.pack_start(search_button, False, False, 0)
        self.pack_start(row, False, False, 0)
        self._sync_mode_buttons()

    def build_toolbar(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.get_style_context().add_class('toolbar-row')

        self.scope_box = Gtk.Box(spacing=6)
        row.pack_start(self.scope_box, False, False, 0)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        row.pack_start(spacer, True, True, 0)

        tools = Gtk.Box(spacing=0)
        tools.get_style_context().add_class('tool-group')
        self.filters_button = self._tool(ICONS['filters'], 'Filters (next phase)', None, enabled=False)
        self.advanced_button = self._tool(ICONS['advanced'], 'Advanced options (next phase)', None, enabled=False)
        refresh = self._tool(ICONS['refresh'], 'Refresh mounts', lambda w: self.populate_scope_chips())
        for t in (self.filters_button, self.advanced_button, refresh):
            tools.pack_start(t, False, False, 0)
        row.pack_start(tools, False, False, 0)
        self.pack_start(row, False, False, 0)

    def build_results_area(self):
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_hexpand(True)
        paned.set_vexpand(True)

        # --- results (left) ---
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        # model: icon,name,path,size,type,modified-text,mount,mtime-epoch
        # (hidden epoch column keeps Modified sorting numeric — '—' rows
        # sink to the oldest end instead of floating up as text, r025)
        self.store = Gtk.ListStore(
            GdkPixbuf.Pixbuf, str, str, str, str, str, str, float)
        self.view = Gtk.TreeView(model=self.store)
        self.view.set_hexpand(True)
        self.view.set_vexpand(True)
        self.view.get_style_context().add_class('results-tree')
        self.view.set_headers_clickable(True)
        self.view.get_selection().connect('changed', self.on_selection_changed)

        icon_renderer = Gtk.CellRendererPixbuf()
        name_renderer = Gtk.CellRendererText()
        name_renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        name_col = Gtk.TreeViewColumn('Name')
        name_col.pack_start(icon_renderer, False)
        name_col.pack_start(name_renderer, True)
        name_col.add_attribute(icon_renderer, 'pixbuf', 0)
        name_col.add_attribute(name_renderer, 'text', 1)
        name_col.set_resizable(True)
        name_col.set_reorderable(True)
        name_col.set_sort_column_id(1)
        set_text_index(name_col, 1)
        text_cols = {}
        for title, model_idx in (('Path', 2), ('Size', 3), ('Type', 4),
                                 ('Modified', 5), ('Mount', 6)):
            renderer = Gtk.CellRendererText()
            renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
            col = Gtk.TreeViewColumn(title, renderer, text=model_idx)
            col.set_resizable(True)
            col.set_reorderable(True)
            col.set_sort_column_id(model_idx)
            set_text_index(col, model_idx)
            text_cols[title] = col
        # default order (operator rule r021): Modified, Name, Path, Size, Type, Mount
        self.view.append_column(text_cols['Modified'])
        self.view.append_column(name_col)
        self.view.append_column(text_cols['Path'])
        self.view.append_column(text_cols['Size'])
        self.view.append_column(text_cols['Type'])
        self.view.append_column(text_cols['Mount'])
        # Modified sorts on the hidden epoch column (numeric)
        text_cols['Modified'].set_sort_column_id(7)
        # readable minimum widths on open (operator rule r025): names and
        # paths must not be squeezed to slivers; sheet scrolls horizontally
        for col in self.view.get_columns():
            col.set_min_width(
                RESULTS_MIN_WIDTHS.get(col.get_title(), 60))
        attach_spreadsheet_behavior(self.view)
        self.view.connect('button-press-event', self.on_results_button_press)
        # double-click opens the file with the default app (operator rule r034)
        self.view.connect('row-activated', self.on_row_activated)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.view)
        left.pack_start(scrolled, True, True, 0)
        paned.pack1(left, True, False)

        # --- preview (right, fold-out; small square toggle beside the
        #     spreadsheet header row — replaces the r018 full-height rail) ---
        right_side = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # narrow transparent strip; only its top cell is a button, sized to
        # a header cell and aligned with the header band: caret-right when
        # open, caret-left closed (r028; +2px to header-cell size in r030)
        toggle_size = Layout.dimensions.PREVIEW_TOGGLE_SIZE
        strip = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        strip.get_style_context().add_class('preview-strip')
        strip.set_size_request(toggle_size, -1)
        self.preview_toggle = Gtk.Button()
        self.preview_toggle.get_style_context().add_class('preview-toggle')
        self.preview_toggle.set_relief(Gtk.ReliefStyle.NONE)
        self.preview_toggle.set_tooltip_text('Toggle preview pane')
        self.toggle_icon = Gtk.Image.new_from_pixbuf(
            get_icon('caret-right', ROW_ICON_SIZE))
        self.preview_toggle.add(self.toggle_icon)
        self.preview_toggle.set_size_request(toggle_size, toggle_size)
        self.preview_toggle.connect('clicked', self.on_toggle_preview)
        strip.pack_start(self.preview_toggle, False, False, 0)
        right_side.pack_start(strip, False, False, 0)

        self.preview_revealer = Gtk.Revealer()
        self.preview_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.preview_revealer.set_transition_duration(250)
        self.preview_revealer.set_reveal_child(True)
        self.preview_revealer.set_hexpand(False)
        pane = self.build_preview_pane()
        pane.set_size_request(290, -1)
        self.preview_revealer.add(pane)
        right_side.pack_start(self.preview_revealer, False, False, 0)

        paned.pack2(right_side, False, False)

        self.pack_start(paned, True, True, 0)

    def build_preview_pane(self):
        pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        pane.get_style_context().add_class('preview-pane')

        self.pv_icon = Gtk.Image.new_from_pixbuf(
            get_icon('file_text', 56))
        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=16)
        icon_box.set_margin_top(24)
        icon_box.pack_start(self.pv_icon, False, False, 0)
        self.pv_name = Gtk.Label(label='No file selected')
        self.pv_name.set_line_wrap(True)
        self.pv_name.get_style_context().add_class('preview-name')
        icon_box.pack_start(self.pv_name, False, False, 0)
        self.pv_type = Gtk.Label(label='')
        self.pv_type.get_style_context().add_class('preview-type')
        icon_box.pack_start(self.pv_type, False, False, 0)
        pane.pack_start(icon_box, False, False, 0)

        self.pv_props = Gtk.Grid(row_spacing=6, column_spacing=12, margin=16)
        self.pv_props.get_style_context().add_class('preview-props')
        pane.pack_start(self.pv_props, False, False, 0)

        self.pv_snippet = Gtk.TextView()
        self.pv_snippet.set_editable(False)
        self.pv_snippet.set_cursor_visible(False)
        self.pv_snippet.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.pv_snippet.get_style_context().add_class('preview-snippet')
        self.pv_snippet.set_size_request(-1, 120)
        snippet_scroll = Gtk.ScrolledWindow()
        snippet_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        snippet_scroll.add(self.pv_snippet)
        pane.pack_start(snippet_scroll, True, True, 12)

        actions = Gtk.Box(spacing=0)
        actions.get_style_context().add_class('preview-actions')
        for key, label, tooltip in (
                ('open', 'Open', 'Open with default app'),
                ('folder_open', 'Folder', 'Show in folder'),
                ('copy', 'Copy', 'Copy path'),
                ('trash', 'Delete', 'Move to trash')):
            btn = Gtk.Button()
            btn.set_tooltip_text(tooltip)
            btn.get_style_context().add_class('preview-action')
            box = Gtk.Box(spacing=6)
            box.pack_start(get_image(ICONS[key], BUTTON_ICON_SIZE), False, False, 0)
            lbl = Gtk.Label(label=label)
            lbl.get_style_context().add_class('preview-action-label')
            box.pack_start(lbl, False, False, 0)
            btn.add(box)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            pin_button_height(btn)
            btn.connect('clicked', self.on_preview_action, key)
            actions.pack_start(btn, True, True, 0)
        pane.pack_start(actions, False, False, 0)
        return pane

    def build_statusbar(self):
        bar = Gtk.Box(spacing=16)
        bar.get_style_context().add_class('status-bar')
        self.status_spinner = Gtk.Spinner()
        bar.pack_start(self.status_spinner, False, False, 0)
        self.status_scan = Gtk.Label(label='')   # idle shows nothing (r018)
        bar.pack_start(self.status_scan, False, False, 0)
        self.status_matches = Gtk.Label(label='')
        bar.pack_start(self.status_matches, False, False, 0)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.pack_start(spacer, True, True, 0)
        self.status_time = Gtk.Label(label='')
        bar.pack_start(self.status_time, False, False, 0)
        for label in (self.status_scan, self.status_matches, self.status_time):
            label.get_style_context().add_class('status-text')
        self.pack_start(bar, False, False, 0)

    # ------------------------------------------------------- scope chips

    def populate_scope_chips(self):
        # preserve the operator's scope across refresh / mount-table changes
        # (r025: a USB plug-in used to silently reset the scope to "All")
        previous = None
        for path, btn in getattr(self, 'mount_buttons', {}).items():
            if btn.get_active():
                previous = path
                break

        for child in self.scope_box.get_children():
            self.scope_box.remove(child)
        self.mount_buttons = {}

        all_btn = self._scope_chip(
            None, label='All mountpoints', icon_key=ICONS['all_mounts'], active=False)
        self.scope_box.pack_start(all_btn, False, False, 0)
        self.mount_buttons['__all__'] = all_btn

        for m in self.mounts.searchable_mounts():
            btn = self._scope_chip(m, icon_key=m.device_class)
            self.scope_box.pack_start(btn, False, False, 0)
            self.mount_buttons[m.mountpoint] = btn
        target = previous if previous in self.mount_buttons else '__all__'
        self.mount_buttons[target].set_active(True)
        self.scope_box.show_all()

    def _scope_chip(self, m=None, label='All mountpoints', icon_key='all_mounts', active=False):
        btn = Gtk.ToggleButton()
        btn.set_active(active)
        btn.get_style_context().add_class('scope-chip')
        if m is None:
            tooltip = 'Search every searchable mountpoint'
        else:
            tooltip = (f"{m.device} · {m.fstype}"
                       + (f" · {m.size_text}" if m.size_text else ''))
        btn.set_tooltip_text(tooltip)
        box = Gtk.Box(spacing=6)
        icon_name = ICONS.get(icon_key, icon_key)
        tint = MOUNT_TINT if icon_name in ('usb', 'hard-drive', 'network') else None
        box.pack_start(get_image(icon_name, 14, tint), False, False, 0)
        box.pack_start(Gtk.Label(label=m.mountpoint if m is not None else label),
                       False, False, 0)
        btn.add(box)
        pin_button_height(btn)
        btn.connect('toggled', self._on_scope_toggled)
        return btn

    def _on_scope_toggled(self, button):
        # exclusive selection: "All" or exactly one mount for now.
        # Guard against re-entrancy: without it, deactivating the other
        # chip fires *its* handler, which deactivates this one and finally
        # re-activates "All" — a clicked mount chip silently popped back.
        if getattr(self, '_scope_syncing', False):
            return
        self._scope_syncing = True
        try:
            for btn in self.mount_buttons.values():
                if btn is not button and btn.get_active():
                    btn.set_active(False)
            if not any(b.get_active() for b in self.mount_buttons.values()):
                self.mount_buttons['__all__'].set_active(True)
        finally:
            self._scope_syncing = False

    def selected_roots(self):
        for path, btn in self.mount_buttons.items():
            if path != '__all__' and btn.get_active():
                return [path]
        return [m.mountpoint for m in self.mounts.searchable_mounts()]

    def _on_mounts_changed(self):
        GLib.idle_add(self.populate_scope_chips)

    # --------------------------------------------------------- searching

    def start_search(self):
        query = self.query_entry.get_text().strip()
        if not query:
            return
        notice = ''
        if self.mode == MODE_SUBSTRING and any(c in query for c in '*?['):
            # glob metachars are literal in substring mode — the r025
            # "missing files" trap (LinShot* matched nothing). Switch to
            # wildcard and say so instead of scanning to a bogus zero.
            self.mode = MODE_WILDCARD
            self._sync_mode_buttons()
            notice = ' — wildcards detected, switched to Wildcard mode'
        try:
            matcher = make_matcher(query, self.mode, self.case_sensitive)
        except ValueError as e:
            self.status_scan.set_text(str(e))
            self.status_spinner.stop()
            return
        if matcher is None:
            return
        self.stop_search()
        self.store.clear()
        roots = self.selected_roots()
        if not roots:
            self.engine = None
            self.status_scan.set_text('No searchable mountpoints found.')
            self.status_matches.set_text('')
            self._search_state = 'idle'
            self.set_stop_running(False)
            return
        self.engine = SearchEngine()
        scope_kind = 'all'
        if not self.mount_buttons.get('__all__').get_active():
            scope_kind = 'paths'
        if self.history is not None:
            self._active_record = self.history.add(
                query=query, mode=self.mode,
                case_sensitive=self.case_sensitive,
                scope_kind=scope_kind, scope_paths=roots)
        self.engine.start(roots, matcher,
                          include_hidden=DEFAULTS['include_hidden'],
                          follow_symlinks=DEFAULTS['follow_symlinks'])
        self.status_spinner.start()
        self.status_scan.set_text(f"Scanning {', '.join(roots)} …{notice}")
        self._search_state = 'running'
        self.set_stop_running(True)

    def apply_criteria(self, record):
        """Prepopulate every search field from a history/saved record."""
        self.query_entry.set_text(record.get('query', ''))
        self.mode = record.get('mode', MODE_SUBSTRING)
        self.case_sensitive = bool(record.get('case', False))
        self._sync_mode_buttons()
        # scope: reselect chips, falling back to All when a mount is gone
        target = 'all' if record.get('scope_kind') != 'paths' else None
        if target is None:
            for path in record.get('scope_paths', []):
                if path in self.mount_buttons:
                    target = path
                    break
            if target is None:
                target = 'all'
        for path, btn in self.mount_buttons.items():
            btn.set_active(path == target if target != 'all' else path == '__all__')
        if not any(b.get_active() for b in self.mount_buttons.values()):
            self.mount_buttons['__all__'].set_active(True)

    def on_pause_clicked(self, widget):
        if not self.engine:
            return
        if self._search_state == 'running':
            self.engine.pause()
            self._search_state = 'paused'
            self.status_spinner.stop()
            self.status_scan.set_text('Paused.')
        elif self._search_state == 'paused':
            self.engine.resume()
            self._search_state = 'running'
            self.status_spinner.start()
            self.status_scan.set_text('Scanning …')

    def stop_search(self):
        active = self._search_state in ('running', 'paused')
        if self.engine:
            if active:
                stats = self.engine.stats.snapshot()
                self.engine.stop()
                self._finish_active_record(stats, stopped=True)
                self.status_scan.set_text(
                    f"Stopped — {stats['matched']:,} matches, "
                    f"{stats['skipped']} skipped.")
                self.status_spinner.stop()
            else:
                self.engine.stop()
        self._search_state = 'idle'
        self.set_stop_running(False)

    def set_stop_running(self, running):
        """Stop control shows red while a search is running (r015)."""
        tint = STOP_RED_TINT if running else None
        self.stop_button.set_image(get_image(ICONS['stop'], ROW_ICON_SIZE, tint))
        self._stop_red = running

    def _finish_active_record(self, stats, stopped=False):
        if self._active_record is not None and self.history is not None:
            self.history.finish(
                self._active_record['id'],
                stats.get('matched', 0), stats.get('elapsed'),
                stopped=stopped)
            self._active_record = None

    def _drain_results(self):
        engine = self.engine
        if engine is None:
            return True
        drained = 0
        while drained < 200:
            try:
                rec = engine.results.get_nowait()
            except queue.Empty:
                break
            icon_key, type_label = file_type_info(rec['name'], rec['is_dir'])
            mtime = format_mtime(rec.get('mtime'))
            # true mount: the root this record was found under (r025; the
            # old startswith guess could only ever say '/home' or '/')
            mount = rec.get('root') or os.path.dirname(rec['path'])
            epoch = rec.get('mtime') if rec.get('mtime') is not None else 0.0
            self.store.append([
                get_icon(icon_key, 15), rec['name'], rec['path'],
                human_size(rec['size']) if not rec['is_dir'] else '—',
                type_label, mtime, mount, epoch])
            drained += 1
        stats = engine.stats.snapshot()
        self.status_matches.set_text(f"{stats['matched']:,} matches · {stats['dirs_visited']:,} dirs")
        if engine.stats.finished_at:
            self.status_time.set_text(f"{stats['elapsed']:.1f}s")
        elif stats['elapsed'] >= 1:
            # live duration while scanning (r025): the operator can tell a
            # working search from a hung one without waiting for Done
            self.status_time.set_text(f"{stats['elapsed']:.0f}s …")
        else:
            self.status_time.set_text('')
        if engine.stats.finished_at and engine.results.empty():
            verb = 'Stopped' if engine.stats.stopped else 'Done'
            self.status_spinner.stop()
            self._search_state = 'idle'
            self.status_scan.set_text(
                f"{verb} — {stats['matched']:,} matches, {stats['skipped']} skipped.")
            self._finish_active_record(stats, stopped=engine.stats.stopped)
            self.set_stop_running(False)
            self.engine = None
        return True

    # ---------------------------------------------------------- preview

    def on_selection_changed(self, selection):
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return
        row = model[tree_iter]
        name, path, is_dir_text = row[1], row[2], row[4]
        self.pv_name.set_text(name)
        self.pv_type.set_text(is_dir_text)
        self._selected_path = path

        # real content preview: image/pdf thumbnail, office text, plain text
        kind, payload = preview_for(path) if is_dir_text != 'Folder' else ('icon', None)
        if kind == 'image' and payload is not None:
            self.pv_icon.set_from_pixbuf(payload)
        else:
            icon_key, _ = file_type_info(name, is_dir_text == 'Folder')
            self.pv_icon.set_from_pixbuf(get_icon(icon_key, 56))

        for child in self.pv_props.get_children():
            self.pv_props.remove(child)
        props = [('Size', row[3]), ('Type', row[4]), ('Modified', row[5]),
                 ('Location', os.path.dirname(path)), ('Mountpoint', row[6])]
        for i, (k, v) in enumerate(props):
            label = Gtk.Label(label=k)
            label.get_style_context().add_class('preview-prop-key')
            value = Gtk.Label(label=v or '—')
            value.set_halign(Gtk.Align.START)   # left-aligned like the sheets
            value.set_xalign(0.0)
            value.set_ellipsize(3)
            value.set_max_width_chars(24)
            value.set_tooltip_text(v or '')
            self.pv_props.attach(label, 0, i, 1, 1)
            self.pv_props.attach(value, 1, i, 1, 1)
        self.pv_props.show_all()

        buf = self.pv_snippet.get_buffer()
        buf.set_text('')
        if kind == 'text' and payload:
            buf.set_text(payload[:DEFAULTS['snippet_max_bytes']])
        elif os.path.splitext(name)[1].lower() in TEXT_EXTS:
            try:
                if os.path.getsize(path) <= DEFAULTS['snippet_file_limit']:
                    with open(path, 'r', errors='replace') as fh:
                        buf.set_text(fh.read(DEFAULTS['snippet_max_bytes']))
            except OSError:
                pass

    def on_results_button_press(self, view, event):
        """Right-click a results row: Open / Folder / Copy / Delete menu.

        Delete asks for confirmation before moving the file to the trash.
        """
        if event.button != 3:
            return False
        result = view.get_path_at_pos(int(event.x), int(event.y))
        if result is None:
            return False
        path, _, _, _ = result
        view.get_selection().select_path(path)
        file_path = getattr(self, '_selected_path', None)
        if not file_path or not os.path.exists(file_path):
            return False

        menu = Gtk.Menu()
        for label, action in (('Open', 'open'), ('Folder', 'folder_open'),
                              ('Copy', 'copy'), ('Delete', 'delete')):
            item = Gtk.MenuItem(label=label)
            item.connect('activate', self.on_context_action, action, file_path)
            menu.append(item)
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def on_row_activated(self, view, path, column):
        """Double-click (or Enter) opens the file with the default app."""
        row = view.get_model()[path]
        file_path = row[2]
        if file_path and os.path.exists(file_path):
            try:
                Gtk.show_uri_on_window(
                    self.get_toplevel(), 'file://' + file_path, 0)
            except GLib.Error:
                pass

    def on_context_action(self, item, action, file_path):
        if action != 'delete':
            self.on_preview_action(item, action)
            return
        name = os.path.basename(file_path)
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            text=f"Delete '{name}'?",
            secondary_text='The file will be moved to the trash.')
        dialog.add_button('_Cancel', Gtk.ResponseType.CANCEL)
        dialog.add_button('Confirm', Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            self.on_preview_action(item, 'trash')

    def on_preview_action(self, widget, key):
        path = getattr(self, '_selected_path', None)
        if not path or not os.path.exists(path):
            return
        if key == 'open':
            Gtk.show_uri_on_window(self.get_toplevel(), 'file://' + path, 0)
        elif key == 'folder_open':
            Gtk.show_uri_on_window(self.get_toplevel(),
                                   'file://' + os.path.dirname(path), 0)
        elif key == 'copy':
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(path, -1)
        elif key == 'trash':
            try:
                from gi.repository import Gio
                Gio.File.new_for_path(path).trash(None)
            except Exception:
                pass

    def on_toggle_preview(self, widget=None):
        self.preview_visible = not self.preview_visible
        self.preview_revealer.set_reveal_child(self.preview_visible)
        # caret points in the toggle direction: right = fold away,
        # left = bring back (operator rule r018)
        self.toggle_icon.set_from_pixbuf(get_icon(
            'caret-right' if self.preview_visible else 'caret-left',
            ROW_ICON_SIZE))

    # ------------------------------------------------------------ modes

    def _on_mode_toggled(self, button, key):
        if key == 'case':
            self.case_sensitive = button.get_active()
            return
        # radio-like behaviour among wildcard/regex; both off = substring
        if button.get_active():
            self.mode = key
            for other in ('wildcard', 'regex'):
                if other != key:
                    self.mode_buttons[other].set_active(False)
        elif self.mode == key:
            self.mode = MODE_SUBSTRING

    def _sync_mode_buttons(self):
        self.mode_buttons['case'].set_active(self.case_sensitive)
        self.mode_buttons['wildcard'].set_active(self.mode == MODE_WILDCARD)
        self.mode_buttons['regex'].set_active(self.mode == MODE_REGEX)

    # ------------------------------------------------------------ utils

    def _icon_button(self, icon_key, tooltip, handler, height=None, icon_size=None):
        btn = Gtk.Button()
        btn.set_image(get_image(icon_key, icon_size or BUTTON_ICON_SIZE))
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_tooltip_text(tooltip)
        if handler:
            btn.connect('clicked', handler)
        btn.get_style_context().add_class('flat-icon-button')
        return pin_button_height(btn, height)

    def _tool(self, icon_key, tooltip, handler, enabled=True):
        btn = Gtk.Button()
        btn.set_image(get_image(icon_key, BUTTON_ICON_SIZE))
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_tooltip_text(tooltip)
        btn.set_sensitive(enabled)
        if handler:
            btn.connect('clicked', handler)
        btn.get_style_context().add_class('tool-button')
        return pin_button_height(btn)
