#!/usr/bin/env python3
"""
linfilesearch — GTK file search across all mountpoints
Main application entry point - applies default theme on startup
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import sys

from ui.dashboard_window import DashboardWindow
from modules.manager_navigation import NavigationManager
from modules.manager_theme_applicator import ThemeApplicator
from modules.manager_mounts import MountManager
from modules.manager_history import HistoryManager
from modules.manager_tray import TrayManager
from config.config_themes import get_theme
from utils.manager_theme import ThemeManager


def main():
    """Main application entry point"""

    # WM_CLASS: groups the window with the .desktop entry (StartupWMClass)
    GLib.set_prgname('linfilesearch')

    # Initialize managers
    navigation_manager = NavigationManager()
    theme_applicator = ThemeApplicator()
    mount_manager = MountManager()
    history_manager = HistoryManager()

    # Apply default theme immediately for consistent startup
    default_theme = get_theme('default')
    theme_applicator.apply_theme(default_theme)

    # Load the application stylesheet (widget classes: search page, results,
    # preview pane, status bar). Without this only theme colors apply.
    ThemeManager().load_css('resources/css/style.css')

    # Create and show main window
    window = DashboardWindow(navigation_manager, mount_manager, history_manager)

    # system tray icon; while active, closing the window hides it to tray
    tray = TrayManager(window)
    window.tray = tray
    if tray.active:
        def on_delete(widget, event):
            widget.hide()
            return True           # swallow the destroy
        window.connect('delete-event', on_delete)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()

    # Start GTK main loop
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
