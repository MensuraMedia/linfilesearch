"""Enforce operator rule r006: main-page buttons never exceed sidebar
nav button dimensions (28px tall, 130px wide — see config_layout.py).

Builds the real window offscreen and measures preferred sizes of every
Gtk.Button inside the content area (sidebar excluded). Skips without DISPLAY.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get('DISPLAY'), reason='needs an X display')

gi = pytest.importorskip('gi')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk                                         # noqa: E402

from config.config_layout import Layout                              # noqa: E402

MAX_H = Layout.dimensions.MAIN_BUTTON_MAX_HEIGHT
MAX_W = Layout.dimensions.MAIN_BUTTON_MAX_WIDTH


def _collect_buttons(container, found):
    if hasattr(container, 'forall'):
        container.forall(lambda w: _collect_buttons(w, found))
    if isinstance(container, (Gtk.Button, Gtk.ToggleButton)):
        found.append(container)


def _build_window():
    from modules.manager_navigation import NavigationManager
    from modules.manager_mounts import MountManager
    from modules.manager_theme_applicator import ThemeApplicator
    from utils.manager_theme import ThemeManager
    from config.config_themes import get_theme
    from ui.dashboard_window import DashboardWindow
    ThemeApplicator().apply_theme(get_theme('default'))
    assert ThemeManager().load_css('resources/css/style.css')
    nav = NavigationManager()
    mounts = MountManager()
    return DashboardWindow(nav, mounts)


def test_main_page_buttons_within_sidebar_caps():
    window = _build_window()
    found = []
    _collect_buttons(window.content_area, found)
    assert found, 'no buttons found in content area — test wiring broken'

    violations = []
    for btn in found:
        _, natural_h = btn.get_preferred_height()
        _, natural_w = btn.get_preferred_width()
        ctx = btn.get_style_context().list_classes()
        if natural_h > MAX_H or natural_w > MAX_W:
            violations.append(
                f'{ctx} natural h={natural_h} w={natural_w} (caps {MAX_H}/{MAX_W})')
        req_h = btn.get_property('height-request')
        if req_h > MAX_H:
            violations.append(
                f'{ctx} height-request {req_h} > cap {MAX_H}')
        if req_h == Layout.dimensions.MAIN_BUTTON_TARGET_HEIGHT:
            continue   # pinned buttons are correct by construction
    assert not violations, 'buttons exceeding sidebar caps:\n' + '\n'.join(violations)
