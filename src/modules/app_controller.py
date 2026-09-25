"""
App Controller
Cross-page actions: re-run a former search from History/Saved —
switches to the Search page (sidebar state included), prepopulates all
criteria fields, and starts the search immediately.
"""


class AppController:
    """Mediates navigation + search-page activation."""

    def __init__(self, navigation_manager, sidebar, search_page):
        self.nav = navigation_manager
        self.sidebar = sidebar
        self.search_page = search_page

    def run_search(self, record):
        """Apply a history/saved record on the Search page and run it."""
        self.nav.navigate_to('search')
        if self.sidebar is not None:
            self.sidebar.set_active_page('search')
        self.search_page.apply_criteria(record)
        self.search_page.start_search()
