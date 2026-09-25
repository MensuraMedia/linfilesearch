#!/usr/bin/env python3
"""
linfilesearch — GTK file search across all mountpoints
Main application entry point - applies default theme on startup
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import sys

from ui.dashboard_window import DashboardWindow
from modules.manager_navigation import NavigationManager
from modules.manager_theme_applicator import ThemeApplicator
from modules.manager_mounts import MountManager
from modules.manager_history import HistoryManager
from config.config_themes import get_theme
from utils.manager_theme import ThemeManager


def main():
    """Main application entry point"""

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
    window.connect("destroy", Gtk.main_quit)
    window.show_all()

    # Start GTK main loop
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
