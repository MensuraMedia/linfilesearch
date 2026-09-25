"""
Saved Searches Page
Bookmarked searches (added via the bookmark column on the History page).
Single-click a row to run it; the trash column removes it.
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango

from pages.page_base import BasePage
from utils.icon_loader import get_icon
from utils.treeview_utils import attach_spreadsheet_behavior, set_text_index
from config.config_layout import Layout
from config.config_search import ICONS

BUTTON_ICON_SIZE = Layout.dimensions.MAIN_BUTTON_ICON_SIZE


class SavedPage(BasePage):
    """Bookmarked searches, restorable in one click, removable via trash."""

    def __init__(self, history_manager):
        self.history = history_manager
        self.controller = None
        self._trash_icon = None
        super().__init__(spacing=12, margin=24)

    def bind(self, controller):
        """Receive the app controller (wired after all pages exist)."""
        self.controller = controller

    def build_content(self):
        self.get_style_context().add_class('search-page')

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title = Gtk.Label(label='Saved Searches')
        title.get_style_context().add_class('page-title')
        head.pack_start(title, False, False, 0)
        self.pack_start(head, False, False, 0)

        self.hint = Gtk.Label(label='Single-click a search to run it again. '
                                    'Click the trash to remove it. '
                                    'Bookmark searches from the History page.')
        self.hint.get_style_context().add_class('status-text')
        self.pack_start(self.hint, False, False, 0)

        self._trash_icon = get_icon(ICONS['trash'], BUTTON_ICON_SIZE)
        self.store = Gtk.ListStore(
            GdkPixbuf.Pixbuf, str, str, str, str, str, str)  # trash,query,mode,case,scope,saved_at,id
        self.view = Gtk.TreeView(model=self.store)
        self.view.get_style_context().add_class('sheet-tree')
        self.view.set_headers_clickable(True)
        self.view.connect('button-press-event', self.on_button_press)

        trash_renderer = Gtk.CellRendererPixbuf()
        self.trash_col = Gtk.TreeViewColumn('Remove', trash_renderer, pixbuf=0)
        self.trash_col.set_fixed_width(52)
        set_text_index(self.trash_col, None)
        self.view.append_column(self.trash_col)
        # fixed widths per operator reference screenshot (r016)
        for title, idx, width in (('Query', 1, 420), ('Mode', 2, 150),
                                  ('Case', 3, 60), ('Scope', 4, 280),
                                  ('Saved', 5, 130)):
            renderer = Gtk.CellRendererText()
            renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
            col = Gtk.TreeViewColumn(title, renderer, text=idx)
            col.set_fixed_width(width)
            col.set_resizable(True)
            col.set_reorderable(True)
            col.set_sort_column_id(idx)
            set_text_index(col, idx)
            self.view.append_column(col)
        attach_spreadsheet_behavior(self.view)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.add(self.view)
        self.pack_start(scrolled, True, True, 0)

        self.history.on_change(self.refresh)
        self.refresh()

    def refresh(self):
        self.store.clear()
        for rec in reversed(self.history.saved):        # newest first
            self.store.append([
                self._trash_icon, rec.get('query', ''), rec.get('mode', ''),
                'Aa' if rec.get('case') else '—',
                self.history.scope_display(rec),
                rec.get('saved_at', ''), rec.get('id', '')])

    def _record_at(self, model, path):
        rec_id = model[path][6]
        for rec in self.history.saved:
            if rec.get('id') == rec_id:
                return rec
        return None

    def on_button_press(self, view, event):
        """Single click: row re-runs the search; trash column removes it."""
        # GDK3 does not introspect GDK_BUTTON_PRIMARY; primary is button 1
        if event.button != 1:
            return False
        result = view.get_path_at_pos(int(event.x), int(event.y))
        if result is None:
            return False
        path, column, _, _ = result
        record = self._record_at(view.get_model(), path)
        if record is None:
            return False
        if column is self.trash_col:
            self.history.remove_saved(record.get('id'))
        elif self.controller is not None:
            self.controller.run_search(record)
        return True
