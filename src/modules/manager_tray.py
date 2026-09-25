"""
Tray Manager
System tray / panel icon using Ayatana AppIndicator when available, with a
Gtk.StatusIcon fallback for legacy XEmbed trays. Menu: show/hide, new search,
about, quit. Closing the window hides it to the tray while the tray is alive.
"""

import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

APP_ICON_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'resources', 'images', 'app-icon')

INDICATOR_ID = 'linfilesearch'


def _icon_path(size=24):
    return os.path.join(APP_ICON_DIR, f'{size}.png')


class TrayManager:
    """Panel/system tray icon bound to the main window."""

    def __init__(self, window):
        self.window = window
        self.active = False
        self._indicator = None
        self._status_icon = None
        self._menu = self._build_menu()
        self._install()

    # ------------------------------------------------------------- setup

    def _build_menu(self):
        menu = Gtk.Menu()

        show = Gtk.MenuItem(label='Show / Hide')
        show.connect('activate', self.on_toggle_window)
        menu.append(show)

        search = Gtk.MenuItem(label='New Search')
        search.connect('activate', self.on_new_search)
        menu.append(search)

        menu.append(Gtk.SeparatorMenuItem())

        about = Gtk.MenuItem(label='About')
        about.connect('activate', self.on_about)
        menu.append(about)

        quit_item = Gtk.MenuItem(label='Quit')
        quit_item.connect('activate', self.on_quit)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _install(self):
        try:
            gi.require_version('AyatanaAppIndicator3', '0.1')
            from gi.repository import AyatanaAppIndicator3 as AI
            self._indicator = AI.Indicator.new(
                INDICATOR_ID, _icon_path(24),
                AI.IndicatorCategory.APPLICATION_STATUS)
            self._indicator.set_status(AI.IndicatorStatus.ACTIVE)
            self._indicator.set_menu(self._menu)
            self._indicator.set_title('linfilesearch')
            self.active = True
            return
        except (TypeError, ValueError, ImportError):
            pass
        try:
            self._status_icon = Gtk.StatusIcon.new_from_file(_icon_path(24))
            self._status_icon.set_tooltip_text('linfilesearch')
            self._status_icon.connect(
                'activate', lambda w: self.on_toggle_window())
            self._status_icon.connect('popup-menu',
                                      self._on_status_popup)
            self.active = True
        except Exception:
            self.active = False

    def _on_status_popup(self, icon, button, time):
        self._menu.popup(None, None, Gtk.StatusIcon.position_menu,
                         icon, button, time)

    # ---------------------------------------------------------- actions

    def on_toggle_window(self, *args):
        if self.window.get_visible():
            self.window.hide()
        else:
            self.window.present()

    def on_new_search(self, *args):
        self.window.present()
        try:
            self.window.content_area.controller.nav.navigate_to('search')
            self.window.sidebar.set_active_page('search')
            page = self.window.content_area.nav_manager.pages.get('search') \
                if hasattr(self.window.content_area.nav_manager, 'pages') else None
            if page is not None and hasattr(page, 'query_entry'):
                page.query_entry.grab_focus()
        except Exception:
            pass

    def on_about(self, *args):
        self.window.present()
        try:
            self.window.sidebar.set_active_page('about')
            self.window.content_area.show_page('about')
        except Exception:
            pass

    def on_quit(self, *args):
        Gtk.main_quit()
