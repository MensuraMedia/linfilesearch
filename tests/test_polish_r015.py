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


def test_sidebar_logo_compact_with_wordmark(tmp_path):
    window = _build_window(tmp_path)
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
    marks = [i for i in images if i.get_pixbuf() is not None
             and i.get_pixbuf().get_height() == 56]
    assert marks, 'sidebar mark must render at 56px, not the old 145px fill'


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
