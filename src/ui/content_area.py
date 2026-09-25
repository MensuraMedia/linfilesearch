"""
Content Area Component
Stack container for pages with individual scroll states
Updated for linfilesearch: search / history / saved / about / settings
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pages.page_search import SearchPage
from pages.page_history import HistoryPage
from pages.page_saved import SavedPage
from pages.page_about import AboutPage
from pages.page_settings import SettingsPage
from modules.app_controller import AppController


class ContentArea(Gtk.Box):
    """Content area with page navigation and individual scroll states"""

    def __init__(self, navigation_manager, mount_manager=None,
                 history_manager=None, sidebar=None):
        """Initialize content area"""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.nav_manager = navigation_manager
        self.mount_manager = mount_manager
        self.history_manager = history_manager
        self.sidebar = sidebar

        # Style class for content area
        self.get_style_context().add_class('content-area')

        # Create stack for pages - NO transitions
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.pack_start(self.stack, True, True, 0)

        # Register stack with navigation manager
        self.nav_manager.set_page_stack(self.stack)

        # Register pages
        self.register_pages()

    def wrap_page_in_scrolled_window(self, page):
        """Wrap a page in its own ScrolledWindow (individual scroll state)"""
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(page)
        return scrolled_window

    def register_pages(self):
        """Register all application pages and wire cross-page actions"""
        history = self.history_manager
        search_page = (SearchPage(self.mount_manager, history)
                       if self.mount_manager else None)
        history_page = HistoryPage(history) if history else None
        saved_page = SavedPage(history) if history else None
        pages = [
            ('search', search_page),
            ('history', history_page),
            ('saved', saved_page),
            ('about', AboutPage()),
            ('settings', SettingsPage()),
        ]
        for page_id, page in pages:
            if page is None:
                continue
            scrolled = self.wrap_page_in_scrolled_window(page)
            self.stack.add_named(scrolled, page_id)
            self.nav_manager.register_page(page_id, page)

        # controller: History/Saved rows re-run on the Search page
        self.controller = None
        if search_page is not None:
            self.controller = AppController(
                self.nav_manager, self.sidebar, search_page)
            if history_page is not None:
                history_page.bind(self.controller)
            if saved_page is not None:
                saved_page.bind(self.controller)

    def show_page(self, page_id):
        """Show a specific page"""
        self.nav_manager.navigate_to(page_id)
