"""
History Page
Spreadsheet of former searches. Single-click a row to re-run it (switches to
the Search page, prepopulates every field, and starts the search). The
bookmark column saves a row to the Saved page. Clear All empties the history.
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango

from pages.page_base import BasePage
from utils.icon_loader import get_icon, get_image
from config.config_layout import Layout
from config.config_search import ICONS

BUTTON_ICON_SIZE = Layout.dimensions.MAIN_BUTTON_ICON_SIZE


class HistoryPage(BasePage):
    """Former searches, restorable in one click, bookmarkable, clearable."""

    def __init__(self, history_manager):
        self.history = history_manager
        self.controller = None
        self._bookmark_on = None
        self._bookmark_off = None
        super().__init__(spacing=12, margin=24)

    def bind(self, controller):
        """Receive the app controller (wired after all pages exist)."""
        self.controller = controller

    def build_content(self):
        self.get_style_context().add_class('search-page')

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title = Gtk.Label(label='Search History')
        title.get_style_context().add_class('page-title')
        head.pack_start(title, False, False, 0)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        head.pack_start(spacer, True, True, 0)
        clear_btn = Gtk.Button()
        clear_btn.set_tooltip_text('Clear all history')
        clear_btn.get_style_context().add_class('flat-icon-button')
        cb = Gtk.Box(spacing=6)
        cb.pack_start(get_image(ICONS['trash'], BUTTON_ICON_SIZE), False, False, 0)
        cb.pack_start(Gtk.Label(label='Clear'), False, False, 0)
        clear_btn.add(cb)
        clear_btn.set_property(
            'height-request', Layout.dimensions.MAIN_BUTTON_TARGET_HEIGHT)
        clear_btn.connect('clicked', self.on_clear_all)
        head.pack_start(clear_btn, False, False, 0)
        self.pack_start(head, False, False, 0)

        self.hint = Gtk.Label(label='Single-click a search to run it again. '
                                    'Click the bookmark to save it.')
        self.hint.get_style_context().add_class('status-text')
        self.pack_start(self.hint, False, False, 0)

        # spreadsheet: time, query, mode, case, scope, matches, [bookmark]
        self.store = Gtk.ListStore(
            GdkPixbuf.Pixbuf, str, str, str, str, str, str, str)  # mark,time,query,mode,case,scope,matches,id
        self.view = Gtk.TreeView(model=self.store)
        self.view.get_style_context().add_class('sheet-tree')
        self.view.set_headers_clickable(True)
        self.view.connect('button-press-event', self.on_button_press)

        self._bookmark_off = get_icon(ICONS['saved'], BUTTON_ICON_SIZE)
        self._bookmark_on = get_icon(ICONS['saved'], BUTTON_ICON_SIZE,
                                     tint=(0x00, 0x78, 0xd7))

        mark_renderer = Gtk.CellRendererPixbuf()
        self.mark_col = Gtk.TreeViewColumn('Saved', mark_renderer, pixbuf=0)
        self.mark_col.set_fixed_width(44)
        self.view.append_column(self.mark_col)
        for title, idx in (('Time', 1), ('Query', 2), ('Mode', 3),
                           ('Case', 4), ('Scope', 5), ('Matches', 6)):
            renderer = Gtk.CellRendererText()
            renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
            col = Gtk.TreeViewColumn(title, renderer, text=idx)
            col.set_resizable(True)
            col.set_reorderable(True)
            col.set_sort_column_id(idx)
            self.view.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.add(self.view)
        self.pack_start(scrolled, True, True, 0)

        self.history.on_change(self.refresh)
        self.refresh()

    # ------------------------------------------------------------- data

    def refresh(self):
        self.store.clear()
        for rec in reversed(self.history.records):       # newest first
            icon = self._bookmark_on if self.history.is_saved(rec) else self._bookmark_off
            matches = rec.get('matches')
            matches_text = f"{matches:,}" if matches is not None else '…'
            self.store.append([
                icon, rec.get('time', ''), rec.get('query', ''),
                rec.get('mode', ''), 'Aa' if rec.get('case') else '—',
                self.history.scope_display(rec), matches_text, rec.get('id', '')])

    def _record_at(self, model, path):
        rec_id = model[path][7]
        for rec in self.history.records:
            if rec.get('id') == rec_id:
                return rec
        return None

    # ---------------------------------------------------------- actions

    def on_button_press(self, view, event):
        """Single click: row re-runs the search; bookmark column saves it."""
        if event.button != Gdk.BUTTON_PRIMARY_BUTTON:
            return False
        result = view.get_path_at_pos(int(event.x), int(event.y))
        if result is None:
            return False
        path, column, _, _ = result
        record = self._record_at(view.get_model(), path)
        if record is None:
            return False
        if column is self.mark_col:
            self.history.bookmark(record)
        elif self.controller is not None:
            self.controller.run_search(record)
        return True

    def on_clear_all(self, widget):
        self.history.clear()
