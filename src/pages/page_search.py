"""
Search Page
Main file-search UI: query bar with mode toggles, mountpoint scope chips,
icon toolbar, streaming results table, status bar, and a collapsible
preview pane (fold-out, per mockup A2).
"""

import os
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
from config.config_layout import Layout

BUTTON_ICON_SIZE = Layout.dimensions.MAIN_BUTTON_ICON_SIZE
BUTTON_MAX_H = Layout.dimensions.MAIN_BUTTON_MAX_HEIGHT
BUTTON_MAX_W = Layout.dimensions.MAIN_BUTTON_MAX_WIDTH
BUTTON_TARGET_H = Layout.dimensions.MAIN_BUTTON_TARGET_HEIGHT
SEARCH_ROW_H = Layout.dimensions.SEARCH_ROW_HEIGHT


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


class SearchPage(BasePage):
    """File search page (A+ layout: dashboard + fold-out preview)."""

    def __init__(self, mount_manager, history_manager=None):
        self.mounts = mount_manager
        self.history = history_manager
        self.engine = None
        self._active_record = None
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
        self.build_results_area()
        self.build_statusbar()

        self.mounts.on_change(self._on_mounts_changed)
        self.populate_scope_chips()
        GLib.timeout_add(100, self._drain_results)

    def build_search_row(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.get_style_context().add_class('search-row')

        self.query_entry = Gtk.Entry()
        self.query_entry.set_placeholder_text(
            "Search file names — try  *report*.odt  or  meeting notes")
        self.query_entry.set_hexpand(True)
        self.query_entry.connect('activate', lambda w: self.start_search())
        entry_box = Gtk.Box(spacing=8, margin=6)
        entry_box.get_style_context().add_class('search-entry')
        entry_box.set_property('height-request', SEARCH_ROW_H)
        entry_box.pack_start(get_image(ICONS['search'], BUTTON_ICON_SIZE), False, False, 0)
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
            box.pack_start(get_image(ICONS[key], BUTTON_ICON_SIZE), False, False, 0)
            box.pack_start(Gtk.Label(label=label), False, False, 0)
            btn.add(box)
            btn.set_property('height-request', SEARCH_ROW_H)
            btn.get_style_context().add_class('mode-toggle')
            btn.connect('toggled', self._on_mode_toggled, key)
            mode_group.pack_start(btn, False, False, 0)
            self.mode_buttons[key] = btn
        row.pack_start(mode_group, False, False, 0)

        self.pause_button = self._icon_button(
            ICONS['pause'], 'Pause search', self.on_pause_clicked, height=SEARCH_ROW_H)
        self.stop_button = self._icon_button(
            ICONS['stop'], 'Stop search', lambda w: self.stop_search(), height=SEARCH_ROW_H)
        search_button = Gtk.Button()
        search_button.set_tooltip_text('Run search')
        b = Gtk.Box(spacing=8)
        b.pack_start(get_image(ICONS['search'], BUTTON_ICON_SIZE), False, False, 0)
        b.pack_start(Gtk.Label(label='Search'), False, False, 0)
        search_button.add(b)
        search_button.get_style_context().add_class('primary-button')
        search_button.set_property('height-request', SEARCH_ROW_H)
        search_button.connect('clicked', lambda w: self.start_search())

        row.pack_start(self.pause_button, False, False, 0)
        row.pack_start(self.stop_button, False, False, 0)
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
        self.preview_button = self._tool(
            ICONS['preview'], 'Preview pane', self.on_toggle_preview)
        self.preview_button.get_style_context().add_class('active')
        refresh = self._tool(ICONS['refresh'], 'Refresh mounts', lambda w: self.populate_scope_chips())
        for t in (self.filters_button, self.advanced_button, self.preview_button, refresh):
            tools.pack_start(t, False, False, 0)
        row.pack_start(tools, False, False, 0)
        self.pack_start(row, False, False, 0)

    def build_results_area(self):
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_hexpand(True)
        paned.set_vexpand(True)

        # --- results (left) ---
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.store = Gtk.ListStore(
            GdkPixbuf.Pixbuf, str, str, str, str, str, str)
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
        self.view.append_column(name_col)
        for title, model_idx in (('Path', 2), ('Size', 3), ('Type', 4),
                                 ('Modified', 5), ('Mount', 6)):
            renderer = Gtk.CellRendererText()
            renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
            col = Gtk.TreeViewColumn(title, renderer, text=model_idx)
            col.set_resizable(True)
            col.set_reorderable(True)
            col.set_sort_column_id(model_idx)
            set_text_index(col, model_idx)
            self.view.append_column(col)
        attach_spreadsheet_behavior(self.view)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.view)
        left.pack_start(scrolled, True, True, 0)
        paned.pack1(left, True, False)

        # --- preview (right, fold-out) ---
        self.preview_revealer = Gtk.Revealer()
        self.preview_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.preview_revealer.set_transition_duration(250)
        self.preview_revealer.set_reveal_child(True)
        self.preview_revealer.set_hexpand(False)
        pane = self.build_preview_pane()
        pane.set_size_request(290, -1)
        self.preview_revealer.add(pane)
        paned.pack2(self.preview_revealer, False, False)

        self.pack_start(paned, True, True, 0)

    def build_preview_pane(self):
        pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        pane.get_style_context().add_class('preview-pane')

        head = Gtk.Box(spacing=8, margin=8)
        head.get_style_context().add_class('preview-head')
        head.pack_start(get_image(ICONS['preview'], 14), False, False, 0)
        head.pack_start(Gtk.Label(label='Preview'), False, False, 0)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        head.pack_start(spacer, True, True, 0)
        close_btn = Gtk.Button()
        close_btn.set_image(get_image(ICONS['clear'], 12))
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.set_tooltip_text('Collapse preview')
        close_btn.connect('clicked', self.on_toggle_preview)
        head.pack_start(close_btn, False, False, 0)
        pane.pack_start(head, False, False, 0)

        self.pv_icon = Gtk.Image.new_from_pixbuf(
            get_icon('file_text', 56))
        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=16)
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
        bar = Gtk.Box(spacing=16, margin=8)
        bar.get_style_context().add_class('status-bar')
        self.status_spinner = Gtk.Spinner()
        bar.pack_start(self.status_spinner, False, False, 0)
        self.status_scan = Gtk.Label(label='Ready.')
        self.status_scan.get_style_context().add_class('status-text')
        bar.pack_start(self.status_scan, False, False, 0)
        self.status_matches = Gtk.Label(label='')
        bar.pack_start(self.status_matches, False, False, 0)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.pack_start(spacer, True, True, 0)
        self.status_time = Gtk.Label(label='')
        bar.pack_start(self.status_time, False, False, 0)
        bar.pack_start(get_image(ICONS['clock'], 12), False, False, 0)
        self.pack_start(bar, False, False, 0)

    # ------------------------------------------------------- scope chips

    def populate_scope_chips(self):
        for child in self.scope_box.get_children():
            self.scope_box.remove(child)
        self.mount_buttons = {}

        all_btn = self._scope_chip(
            None, label='All mountpoints', icon_key=ICONS['all_mounts'], active=True)
        self.scope_box.pack_start(all_btn, False, False, 0)
        self.mount_buttons['__all__'] = all_btn

        for m in self.mounts.searchable_mounts():
            btn = self._scope_chip(m, icon_key=m.device_class)
            self.scope_box.pack_start(btn, False, False, 0)
            self.mount_buttons[m.mountpoint] = btn
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
        # exclusive selection: "All" or exactly one mount for now
        for btn in self.mount_buttons.values():
            if btn is not button and btn.get_active():
                btn.set_active(False)
        if not any(b.get_active() for b in self.mount_buttons.values()):
            self.mount_buttons['__all__'].set_active(True)

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
        matcher = make_matcher(query, self.mode, self.case_sensitive)
        if matcher is None:
            return
        self.stop_search()
        self.store.clear()
        self.engine = SearchEngine()
        roots = self.selected_roots()
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
        self.status_scan.set_text(f"Scanning {', '.join(roots)} …")
        self._search_state = 'running'

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
        if self.engine:
            stats = self.engine.stats.snapshot()
            self.engine.stop()
            self._finish_active_record(stats)
        self._search_state = 'idle'
        self.status_spinner.stop()

    def _finish_active_record(self, stats):
        if self._active_record is not None and self.history is not None:
            self.history.finish(
                self._active_record['id'],
                stats.get('matched', 0), stats.get('elapsed'))
            self._active_record = None

    def _drain_results(self):
        if not self.engine:
            return True
        engine = self.engine
        drained = 0
        while drained < 200:
            try:
                rec = engine.results.get_nowait()
            except Exception:
                break
            icon_key, type_label = file_type_info(rec['name'], rec['is_dir'])
            mtime = time.strftime('%Y-%m-%d', time.localtime(rec['mtime'])) if rec['mtime'] else '—'
            mount = next((p for p in ('/home', '/') if rec['path'].startswith(p)), '/')
            self.store.append([
                get_icon(icon_key, 15), rec['name'], rec['path'],
                human_size(rec['size']) if not rec['is_dir'] else '—',
                type_label, mtime, mount])
            drained += 1
        stats = engine.stats.snapshot()
        self.status_matches.set_text(f"{stats['matched']:,} matches · {stats['dirs_visited']:,} dirs")
        if stats['elapsed'] and engine.stats.finished_at:
            self.status_time.set_text(f"{stats['elapsed']:.0f}s")
        if engine.stats.finished_at and engine.results.empty():
            self.status_spinner.stop()
            self._search_state = 'idle'
            self.status_scan.set_text(
                f"Done — {stats['matched']:,} matches, {stats['skipped']} skipped.")
            self._finish_active_record(stats)
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
            value.set_halign(Gtk.Align.END)
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
        ctx = self.preview_button.get_style_context()
        if self.preview_visible:
            ctx.add_class('active')
        else:
            ctx.remove_class('active')

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

    def _icon_button(self, icon_key, tooltip, handler, height=None):
        btn = Gtk.Button()
        btn.set_image(get_image(icon_key, BUTTON_ICON_SIZE))
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
