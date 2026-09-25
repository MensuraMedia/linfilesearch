"""
About Page
linfilesearch application information: what it does, how it searches,
credits and licensing. Margins match the other pages (r016).
"""

from pages.page_base import BasePage


class AboutPage(BasePage):
    """About page for linfilesearch"""

    def __init__(self):
        super().__init__(spacing=12, margin=24)

    def build_content(self):
        """Build about page content"""

        self.add_title("About linfilesearch")

        self.add_paragraph(
            "linfilesearch is a native Linux desktop file-search utility built with "
            "GTK 3 and Python. It searches every mounted filesystem — the system root, "
            "the home partition, permanently mounted data disks, and externally "
            "attached USB drives — without an index, streaming results live with "
            "pause and stop control."
        )

        self.add_subtitle("How it searches")

        self.add_paragraph(
            "Name matching supports three modes: plain substring, wildcards "
            "(* ? [ ], find -name semantics), and regular expressions, each with an "
            "optional case-sensitivity toggle. One worker thread scans each selected "
            "mountpoint and stays on its own device, so nested mounts never produce "
            "duplicate results. Pseudo-filesystems (/proc, /sys, snap images) are "
            "excluded automatically; plug or unplug a drive and the scope list "
            "updates on its own."
        )

        self.add_subtitle("Credits")

        self.add_paragraph(
            "Built on the gtk-python-dashboard-starter template by mikesdatawork. "
            "Interface icons: Phosphor Icons (MIT License)."
        )

        self.add_subtitle("License")

        self.add_paragraph(
            "Copyright (c) 2026 MensuraMedia. Licensed under the Creative Commons "
            "Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0): free "
            "to use, copy, modify, and distribute with attribution; commercial use "
            "is prohibited without prior permission from the author."
        )
