"""
History Page (stub — populated in roadmap step 5)
"""

from pages.page_base import BasePage


class HistoryPage(BasePage):
    """Recent searches; persistence lands with saved-search storage."""

    def build_content(self):
        self.add_title('Search History')
        self.add_paragraph('Recent searches will be listed here (roadmap step 5).')
