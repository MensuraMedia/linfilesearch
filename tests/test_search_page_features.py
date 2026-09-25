"""UI feature checks: stop button, reorderable columns, history page wiring.
Builds the real window offscreen; skips without DISPLAY."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get('DISPLAY'), reason='needs an X display')

gi = pytest.importorskip('gi')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk                                         # noqa: E402


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
    nav = NavigationManager()
    window = DashboardWindow(
        nav, MountManager(),
        HistoryManager(config_dir=str(tmp_path / 'cfg')))
    return window


def _find_widget(container, predicate, found):
    if hasattr(container, 'forall'):
        container.forall(lambda w: _find_widget(w, predicate, found))
    if predicate(container):
        found.append(container)
    return found


def test_stop_button_exists_and_stops(tmp_path):
    window = _build_window(tmp_path)
    page = window.content_area.nav_manager.pages.get('search') if hasattr(
        window.content_area.nav_manager, 'pages') else None
    page = page or _find_widget(window.content_area, lambda w: type(w).__name__ == 'SearchPage', [])[0]
    assert page.stop_button is not None
    assert isinstance(page.stop_button, Gtk.Button)
    assert page.stop_button.get_tooltip_text() == 'Stop search'
    # stopping with no engine is a safe no-op
    page.stop_search()
    assert page._search_state == 'idle'


def test_results_columns_reorderable(tmp_path):
    window = _build_window(tmp_path)
    page = _find_widget(window.content_area, lambda w: type(w).__name__ == 'SearchPage', [])[0]
    cols = page.view.get_columns()
    assert len(cols) == 6
    assert all(c.get_reorderable() for c in cols), 'columns must be drag-reorderable'
    assert all(c.get_resizable() for c in cols)


def test_history_page_lists_and_clears(tmp_path):
    window = _build_window(tmp_path)
    content = window.content_area
    history = content.history_manager
    history.add(query='*report*.odt', mode='wildcard', case_sensitive=False,
                scope_kind='all', scope_paths=[])
    history.add(query='budget', mode='substring', case_sensitive=True,
                scope_kind='paths', scope_paths=['/home'])
    page = _find_widget(content, lambda w: type(w).__name__ == 'HistoryPage', [])[0]
    page.refresh()
    model = page.view.get_model()
    assert len(model) == 2
    assert model[0][2] == 'budget'          # newest first
    assert model[1][2] == '*report*.odt'
    page.on_clear_all(None)
    assert len(history.records) == 0
    assert len(page.view.get_model()) == 0


def test_bookmark_moves_to_saved(tmp_path):
    window = _build_window(tmp_path)
    content = window.content_area
    history = content.history_manager
    rec = history.add(query='pics', mode='substring', case_sensitive=False,
                      scope_kind='all', scope_paths=[])
    saved_page = _find_widget(content, lambda w: type(w).__name__ == 'SavedPage', [])[0]
    assert len(saved_page.view.get_model()) == 0
    history.bookmark(rec)
    saved_page.refresh()
    assert len(saved_page.view.get_model()) == 1
    assert saved_page.view.get_model()[0][1] == 'pics'


def test_controller_repopulates_search_page(tmp_path):
    window = _build_window(tmp_path)
    content = window.content_area
    history = content.history_manager
    rec = history.add(query='*notes*.md', mode='wildcard', case_sensitive=True,
                      scope_kind='all', scope_paths=[])
    page = _find_widget(content, lambda w: type(w).__name__ == 'SearchPage', [])[0]
    content.controller.run_search(rec)
    assert page.query_entry.get_text() == '*notes*.md'
    assert page.mode == 'wildcard'
    assert page.case_sensitive is True
    # a real search engine was started for the recorded query
    assert page.engine is not None and page.engine.running
    assert page.mount_buttons['__all__'].get_active()
    page.stop_search()
