"""
Saved Searches Page (stub — populated in roadmap step 5)
"""

from pages.page_base import BasePage


class SavedPage(BasePage):
    """Named saved searches; persistence lands with history storage."""

    def build_content(self):
        self.add_title('Saved Searches')
        self.add_paragraph('Save a query with its mode, filters and scope (roadmap step 5).')
