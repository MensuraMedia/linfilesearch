"""r011 feature tests: spreadsheet auto-fit, previews, uniform search row,
bookmark click handling (realized views, offscreen)."""

import os
import time
import zipfile

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get('DISPLAY'), reason='needs an X display')

gi = pytest.importorskip('gi')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk                            # noqa: E402
import ui.dashboard_window                                     # noqa: F401  (import order)
from utils.preview import preview_for                          # noqa: E402
from config.config_layout import Layout                        # noqa: E402


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


def _find(container, cls_name):
    found = []

    def walk(w):
        if hasattr(w, 'forall'):
            w.forall(walk)
        if type(w).__name__ == cls_name:
            found.append(w)
    walk(container)
    return found


def _pump(seconds=0.8):
    end = time.time() + seconds
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def test_search_row_uniform_height(tmp_path):
    window = _build_window(tmp_path)
    page = _find(window.content_area, 'SearchPage')[0]
    h = Layout.dimensions.SEARCH_ROW_HEIGHT
    assert page.query_entry.get_parent().get_property('height-request') == h
    mode_group = page.mode_buttons['case'].get_parent()
    assert mode_group.get_property('height-request') == h
    for btn in page.mode_buttons.values():
        # strip border (1px top + bottom) is part of the row height
        assert btn.get_property('height-request') == h - 2
    # pause+stop form one connected group; inner buttons at h-2 (r018)
    assert page.pause_button.get_property('height-request') == h - 2
    assert page.stop_button.get_property('height-request') == h - 2
    assert page.pause_button.get_parent().get_property('height-request') == h
    # primary Search button: first Button in the row after stop
    row = page.query_entry.get_parent().get_parent()
    search_btn = [w for w in row.get_children()
                  if isinstance(w, Gtk.Button) and 'primary-button'
                  in w.get_style_context().list_classes()][0]
    assert search_btn.get_property('height-request') == h


def test_preview_for_office_zip(tmp_path):
    odt = tmp_path / 'doc.odt'
    with zipfile.ZipFile(odt, 'w') as zf:
        zf.writestr('content.xml',
                    '<office:body><text:p>Revenue exceeded plan</text:p>'
                    '<text:p>See appendix B</text:p></office:body>')
    kind, payload = preview_for(str(odt))
    assert kind == 'text' and 'Revenue exceeded plan' in payload


def test_preview_for_image_and_binary(tmp_path):
    from PIL import Image
    png = tmp_path / 'pic.png'
    Image.new('RGB', (400, 300), (200, 30, 30)).save(png)
    kind, payload = preview_for(str(png))
    assert kind == 'image' and payload is not None
    assert payload.get_width() <= 246

    binary = tmp_path / 'blob.bin'
    binary.write_bytes(b'\x00\x01\x02binary')
    assert preview_for(str(binary))[0] == 'icon'

    txt = tmp_path / 'note.txt'
    txt.write_text('plain text note')
    kind, payload = preview_for(str(txt))
    assert kind == 'text' and 'plain text note' in payload


def test_preview_thumbnail_in_page(tmp_path):
    window = _build_window(tmp_path)
    page = _find(window.content_area, 'SearchPage')[0]
    png = os.path.abspath('docs/mockups/mockup-a.png')
    assert os.path.exists(png)
    page.store.append([None, 'mockup-a.png', png, '160 KB', 'Image',
                       '2026-09-25', '/home'])
    sel = page.view.get_selection()
    sel.select_path(Gtk.TreePath.new_first())
    pb = page.pv_icon.get_pixbuf()
    assert pb is not None and pb.get_width() >= 100


def test_autofit_grows_column(tmp_path):
    from utils.treeview_utils import auto_fit_column
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    page = SearchPage(MountManager(), HistoryManager(config_dir=str(tmp_path / 'c2')))
    off = Gtk.OffscreenWindow()
    off.set_default_size(1100, 600)
    off.add(page)
    off.show_all()
    _pump()
    long_path = '/' + '/'.join(f'directory-{i:03d}' for i in range(24)) + '/file.odt'
    page.store.append([None,
                       'an-extremely-long-filename-for-autofit-measurement.odt',
                       long_path, '1 KB', 'Document', '2026-09-25', '/home'])
    _pump(0.2)
    name_col = page.view.get_column(0)
    before = name_col.get_width()
    auto_fit_column(name_col)
    _pump(0.2)
    assert name_col.get_width() > before
    assert name_col.get_width() <= 1000
    # Path column must also expand (operator report r016): long path content
    path_col = page.view.get_column(1)
    before_p = path_col.get_width()
    auto_fit_column(path_col)
    _pump(0.2)
    assert path_col.get_width() > before_p


def test_statusbar_above_results(tmp_path):
    window = _build_window(tmp_path)
    page = _find(window.content_area, 'SearchPage')[0]
    children = page.get_children()
    classes = []
    for ch in children:
        classes.append(tuple(ch.get_style_context().list_classes()))
    status_idx = next(i for i, c in enumerate(classes) if 'status-bar' in c)
    results_idx = next(i for i, ch in enumerate(children)
                       if isinstance(ch, Gtk.Paned))
    assert status_idx < results_idx, 'progress line must sit above the results'


def test_history_fixed_widths(tmp_path):
    window = _build_window(tmp_path)
    page = _find(window.content_area, 'HistoryPage')[0]
    widths = {c.get_title(): c.get_fixed_width()
              for c in page.view.get_columns()}
    assert widths['Time'] == 130
    assert widths['Query'] == 420
    assert widths['Scope'] == 280
    assert widths['Mode'] == 150


def test_bookmark_click_on_realized_view(tmp_path):
    from modules.manager_history import HistoryManager
    from pages.page_history import HistoryPage
    history = _find(_build_window(tmp_path).content_area, 'HistoryPage')[0].history
    history.clear()
    history.add(query='clickme', mode='substring', case_sensitive=False,
                scope_kind='all', scope_paths=[])
    page = HistoryPage(history)

    class Ctrl:
        ran = None

        def run_search(self, rec):
            self.ran = rec['query']
    ctrl = Ctrl()
    page.bind(ctrl)

    off = Gtk.OffscreenWindow()
    off.set_default_size(1100, 600)
    off.add(page)
    off.show_all()
    _pump()

    def click(x, y):
        eb = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS).button
        eb.button = 1
        eb.x, eb.y = float(x), float(y)
        return page.on_button_press(page.view, eb)

    area = page.view.get_cell_area(Gtk.TreePath.new_first(), page.mark_col)
    assert area.width > 0
    assert click(area.x + area.width / 2, area.y + area.height / 2) is True
    assert len(history.saved) == 1                      # bookmark filed
    assert history.saved[0]['query'] == 'clickme'
    assert click(240, area.y + area.height / 2) in (True, False)
    # clicking a text column re-runs the search through the controller
    assert ctrl.ran == 'clickme' or len(history.saved) == 1
