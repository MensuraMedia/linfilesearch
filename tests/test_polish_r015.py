"""r015 polish: compact logo + wordmark, red stop while running."""

import os
import time

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get('DISPLAY'), reason='needs an X display')

gi = pytest.importorskip('gi')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk                              # noqa: E402
import ui.dashboard_window                                  # noqa: F401  (import order)


def _find(container, cls_name):
    found = []

    def walk(w):
        if hasattr(w, 'forall'):
            w.forall(walk)
        if type(w).__name__ == cls_name:
            found.append(w)
    walk(container)
    return found


def _build_window(tmp_path):
    from modules.manager_navigation import NavigationManager
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from modules.manager_theme_applicator import ThemeApplicator
    from utils.manager_theme import ThemeManager
    from config.config_themes import get_theme
    from ui.dashboard_window import DashboardWindow
    ThemeApplicator().apply_theme(get_theme('default'))
    assert ThemeManager().load_css('resources/css/style.css')
    return DashboardWindow(
        NavigationManager(), MountManager(),
        HistoryManager(config_dir=str(tmp_path / 'cfg')))


def _find_style(container, css_class):
    found = []

    def walk(w):
        if hasattr(w, 'forall'):
            w.forall(walk)
        if hasattr(w, 'get_style_context') and \
                w.get_style_context().has_class(css_class):
            found.append(w)
    walk(container)
    return found


def test_sidebar_compact_header_square_cell(tmp_path):
    window = _build_window(tmp_path)
    # r025: small square logo cell beside the wordmark; header is the first
    # sidebar child and the nav buttons sit directly under it
    first = window.sidebar.get_children()[0]
    assert first.get_style_context().has_class('sidebar-header'), \
        'sidebar must open with the compact header row'

    cells = _find_style(window.sidebar, 'logo-cell')
    assert len(cells) == 1, 'exactly one logo cell expected'
    w, h = cells[0].get_size_request()
    assert w == h and w > 0, 'logo cell must be a perfect square'

    images, labels = [], []

    def walk(w):
        if hasattr(w, 'forall'):
            w.forall(walk)
        if isinstance(w, Gtk.Image):
            images.append(w)
        if isinstance(w, Gtk.Label) and w.get_text() == 'LINFILESEARCH':
            labels.append(w)
    walk(window.sidebar)
    assert labels, 'wordmark label missing from sidebar'
    from config.config_layout import Layout
    marks = [i for i in images if i.get_pixbuf() is not None
             and i.get_pixbuf().get_height() == Layout.dimensions.LOGO_CELL_ICON]
    assert marks, 'sidebar mark must render at the compact cell size (r025)'


def test_results_column_order(tmp_path):
    window = _build_window(tmp_path)
    page = _find(window.content_area, 'SearchPage')[0]
    titles = [c.get_title() for c in page.view.get_columns()]
    assert titles == ['Modified', 'Name', 'Path', 'Size', 'Type', 'Mount']


def test_all_pages_share_margins(tmp_path):
    window = _build_window(tmp_path)
    for name in ('SearchPage', 'HistoryPage', 'SavedPage', 'AboutPage',
                 'SettingsPage'):
        pages = _find(window.content_area, name)
        assert pages, f'{name} not built'
        page = pages[0]
        assert page.get_margin_start() == 24, name
        assert page.get_margin_end() == 24, name
        assert page.get_margin_top() == 24, name
        assert page.get_margin_bottom() == 24, name


def test_results_context_menu(tmp_path):
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from modules.manager_theme_applicator import ThemeApplicator
    from utils.manager_theme import ThemeManager
    from config.config_themes import get_theme
    from pages.page_search import SearchPage
    from gi.repository import Gdk
    import time
    ThemeApplicator().apply_theme(get_theme('default'))
    ThemeManager().load_css('resources/css/style.css')
    page = SearchPage(MountManager(), HistoryManager(config_dir=str(tmp_path / 'c4')))
    off = Gtk.OffscreenWindow()
    off.set_default_size(1100, 600)
    off.add(page)
    off.show_all()
    end = time.time() + 0.8
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    png = os.path.abspath('docs/mockups/mockup-a.png')
    page.store.append([None, 'mockup-a.png', png, '160 KB', 'Image',
                       '2026-09-25', '/home', 1789000000.0])

    # the offscreen Paned rig never maps the bin window, so geometry-based
    # hit-testing can't resolve rows here; stub it to the first row and test
    # the handler logic itself (left-click fallthrough + menu construction)
    page.view.get_path_at_pos = (
        lambda x, y, _c=page.view.get_column(0):
        (Gtk.TreePath.new_first(), _c, 0, 0))

    # left click must fall through to normal selection behaviour
    eb = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS).button
    eb.button, eb.x, eb.y = 1, 80.0, 10.0
    assert page.on_results_button_press(page.view, eb) is False

    # right click on a row builds the Open/Folder/Copy/Delete menu
    menus = []

    def capture_popup(menu, *a, **k):
        menus.append(menu)
        return None
    orig = Gtk.Menu.popup_at_pointer
    Gtk.Menu.popup_at_pointer = capture_popup
    try:
        eb2 = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS).button
        eb2.button, eb2.x, eb2.y = 3, 80.0, 10.0
        handled = page.on_results_button_press(page.view, eb2)
    finally:
        Gtk.Menu.popup_at_pointer = orig
    assert handled is True and menus, 'right-click menu did not open'
    labels = [i.get_label() for i in menus[0].get_children()]
    assert labels == ['Open', 'Folder', 'Copy', 'Delete']


def test_stop_red_while_search_running(tmp_path):
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from modules.manager_theme_applicator import ThemeApplicator
    from utils.manager_theme import ThemeManager
    from config.config_themes import get_theme
    from pages.page_search import SearchPage
    ThemeApplicator().apply_theme(get_theme('default'))
    ThemeManager().load_css('resources/css/style.css')
    page = SearchPage(MountManager(), HistoryManager(config_dir=str(tmp_path / 'c3')))
    page.query_entry.set_text('*')
    page.start_search()
    assert page._search_state == 'running'
    assert page._stop_red is True
    page.stop_search()
    assert page._stop_red is False
    assert page._search_state == 'idle'
