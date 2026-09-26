"""r034 fixes: selected-row highlight must survive hover, and double-click
opens a result.

The hover bug's root cause: GTK3 paints TreeView ROW backgrounds with the
VIEW's own style context carrying the per-row state flags — the old
`.results-tree row:hover/:selected` selectors never matched (verified by a
red-probe: our rules did not affect rendering at all). States now live on
the view node (`.results-tree:selected` etc.), and this test verifies the
REAL rendered pixels with a synthesized motion event, not just CSS files.
"""

import os
import time

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get('DISPLAY'), reason='needs an X display')

gi = pytest.importorskip('gi')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf          # noqa: E402
import ui.dashboard_window                              # noqa: F401,E402 (import order)

SELECTED = (0x00, 0x78, 0xd7)
HOVER = (0x37, 0x37, 0x37)


def _build_tree():
    from modules.manager_theme_applicator import ThemeApplicator
    from utils.manager_theme import ThemeManager
    from config.config_themes import get_theme
    ThemeApplicator().apply_theme(get_theme('default'))
    ThemeManager().load_css('resources/css/style.css')

    store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str, str, str, str, float)
    view = Gtk.TreeView(model=store)
    view.get_style_context().add_class('results-tree')
    view.set_size_request(600, 160)
    renderer = Gtk.CellRendererText()
    view.append_column(Gtk.TreeViewColumn('Name', renderer, text=1))
    for i in range(4):
        store.append([None, f'file-{i}.txt', f'/tmp/file-{i}.txt', '1 KB',
                      'Plain Text', '2026-09-26', '/tmp', 1789000000.0])
    win = Gtk.OffscreenWindow()
    win.set_default_size(600, 160)
    win.add(view)
    win.show_all()
    _pump(0.5)
    view.get_selection().select_path(Gtk.TreePath.new_first())
    _pump()
    return view, win


def _pump(t=0.3):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def _pixel(win, view, bin_x, bin_y):
    win.get_surface().write_to_png('/tmp/r034-test.png')
    from PIL import Image
    px = Image.open('/tmp/r034-test.png').convert('RGB').load()
    _, wy = view.convert_bin_window_to_widget_coords(bin_x, bin_y)
    return px[bin_x + 5, wy]


def _hover(view, bin_x, bin_y):
    ev = Gdk.Event.new(Gdk.EventType.MOTION_NOTIFY)
    ev.motion.window = view.get_bin_window()
    ev.motion.x, ev.motion.y = float(bin_x), float(bin_y)
    ev.motion.device = Gdk.Display.get_default().get_default_seat().get_pointer()
    ev.motion.state = Gdk.ModifierType(0)
    view.event(ev)
    _pump()


def test_selected_highlight_survives_hover():
    view, win = _build_tree()

    # selected, no hover: blue
    got = _pixel(win, view, 60, 10)
    assert all(abs(a - b) <= 2 for a, b in zip(got, SELECTED)), \
        f'selected row must be blue, got {tuple(got)}'

    # mouse back over the selected row: STILL blue (the reported bug)
    _hover(view, 60, 10)
    got = _pixel(win, view, 60, 10)
    assert all(abs(a - b) <= 2 for a, b in zip(got, SELECTED)), \
        f'hover must not steal the selection highlight, got {tuple(got)}'

    # hovering a plain row: hover gray there, selection stays blue
    _hover(view, 60, 52)
    got_plain = _pixel(win, view, 60, 52)
    got_sel = _pixel(win, view, 60, 10)
    assert all(abs(a - b) <= 3 for a, b in zip(got_plain, HOVER)), \
        f'plain-row hover must still work, got {tuple(got_plain)}'
    assert all(abs(a - b) <= 2 for a, b in zip(got_sel, SELECTED)), \
        f'selected row must stay blue while another row is hovered, got {tuple(got_sel)}'


def test_double_click_opens_file(tmp_path, monkeypatch):
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    page = SearchPage(MountManager(),
                      HistoryManager(config_dir=str(tmp_path / 'cfg')))
    target = tmp_path / 'LinShot_1.png'
    target.write_bytes(b'\x89PNG')
    page.store.append([None, 'LinShot_1.png', str(target), '9 B', 'Image',
                       '2026-09-26', str(tmp_path), 1789000000.0])

    opened = []
    monkeypatch.setattr(
        Gtk, 'show_uri_on_window',
        lambda win, uri, ts: opened.append(uri), raising=True)

    page.on_row_activated(page.view, Gtk.TreePath.new_first(),
                          page.view.get_column(0))
    assert opened == [f'file://{target}'], 'double-click must open the file'

    # a missing path is a no-op, not a crash
    page.store.append([None, 'ghost.txt', str(tmp_path / 'ghost.txt'),
                       '—', '—', '—', str(tmp_path), 0.0])
    page.on_row_activated(page.view, Gtk.TreePath.new_from_string('1'),
                          page.view.get_column(0))
    assert len(opened) == 1
