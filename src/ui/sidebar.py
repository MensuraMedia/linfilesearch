"""
Sidebar Component
Fixed sidebar with logo and navigation
Updated: Home button has top border, Settings has top border
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf, GObject
import os

from config.config_layout import Layout


class Sidebar(Gtk.Box):
    """Fixed sidebar with logo and navigation buttons"""
    
    __gsignals__ = {
        'page-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,))
    }
    
    def __init__(self, navigation_manager):
        """Initialize sidebar"""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.nav_manager = navigation_manager
        
        self.set_size_request(Layout.dimensions.SIDEBAR_WIDTH, -1)
        self.get_style_context().add_class('sidebar')
        
        self.active_button = None
        
        self.build_logo_area()
        self.build_navigation()
        
        if "search" in self.nav_buttons:
            self.set_active_button(self.nav_buttons["search"])
            self.nav_manager.navigate_to("search")
    
    def build_logo_area(self):
        """Build logo area: compact icon with wordmark below (r015, mockup ref)"""

        logo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        logo_box.set_size_request(
            Layout.dimensions.LOGO_AREA_WIDTH,
            Layout.dimensions.LOGO_AREA_HEIGHT
        )
        logo_box.get_style_context().add_class('logo-area')

        logo_path = self.get_logo_path()
        if os.path.exists(logo_path):
            try:
                # transparent-background mark at 56px, not the old 145px fill
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    logo_path, 56, 56, True)
                logo_image = Gtk.Image.new_from_pixbuf(pixbuf)
                logo_box.pack_start(logo_image, True, True, 0)
            except Exception as e:
                print(f"Could not load logo: {e}")   # wordmark still shows below

        # wordmark below the icon, as in the original mockup
        wordmark = Gtk.Label(label="LINFILESEARCH")
        wordmark.get_style_context().add_class('logo-cap')
        wordmark.set_xalign(0.5)
        logo_box.pack_start(wordmark, False, False, 6)

        self.pack_start(logo_box, False, False, 0)
    
    def get_logo_path(self):
        """Get path to logo image"""
        return os.path.join(
            os.path.dirname(__file__), '..', '..',
            'resources', 'images', 'logo.png'
        )
    
    def add_fallback_logo(self, container):
        """Add fallback logo text"""
        logo_label = Gtk.Label(label="LINFILESEARCH")
        logo_label.get_style_context().add_class('logo-text')
        logo_label.set_xalign(0.5)
        container.pack_start(logo_label, True, True, 0)

    def build_navigation(self):
        """Build navigation with linfilesearch pages (Search top-bordered, Settings bottom)"""

        # Top navigation container
        nav_box_top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Main navigation items (icon key, label, page_id, is_top)
        nav_items = [
            ('search', "Search", "search", True),
            ('history', "History", "history", False),
            ('saved', "Saved", "saved", False),
            ('info', "About", "about", False),
        ]

        self.nav_buttons = {}
        for icon_key, label, page_id, is_top in nav_items:
            button = self.create_nav_button(label, page_id, icon_key=icon_key, is_top=is_top)
            nav_box_top.pack_start(button, False, False, 0)
            self.nav_buttons[page_id] = button
        
        # Add top navigation
        self.pack_start(nav_box_top, False, False, 0)
        
        # Add expanding spacer to push Settings to bottom
        spacer = Gtk.Box()
        self.pack_start(spacer, True, True, 0)
        
        # Bottom navigation container for Settings
        nav_box_bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Settings button with bottom styling (top border)
        settings_button = self.create_nav_button("Settings", "settings", is_bottom=True)
        nav_box_bottom.pack_start(settings_button, False, False, 0)
        self.nav_buttons["settings"] = settings_button
        
        # Add bottom navigation
        self.pack_start(nav_box_bottom, False, False, 0)
    
    def create_nav_button(self, label, page_id, icon_key=None, is_top=False, is_bottom=False):
        """Create a navigation button with an optional leading icon"""
        button = Gtk.Button()
        button.get_style_context().add_class('nav-button')

        # Add special class for top button (Search)
        if is_top:
            button.get_style_context().add_class('nav-button-top')

        # Add special class for bottom button (Settings)
        if is_bottom:
            button.get_style_context().add_class('nav-button-bottom')

        button.set_relief(Gtk.ReliefStyle.NONE)
        button.connect("clicked", self.on_nav_clicked, page_id)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if icon_key:
            from utils.icon_loader import get_image
            from config.config_search import ICONS
            box.pack_start(get_image(ICONS.get(icon_key, icon_key), 16), False, False, 0)
        text = Gtk.Label(label=label)
        text.set_xalign(0)
        text.get_style_context().add_class('nav-label')
        box.pack_start(text, False, False, 0)
        button.add(box)

        return button
    
    def set_active_button(self, button):
        """Set button as active"""
        if self.active_button:
            self.active_button.get_style_context().remove_class('active')
        
        button.get_style_context().add_class('active')
        self.active_button = button

    def set_active_page(self, page_id):
        """Highlight the nav button for a page (programmatic navigation)."""
        button = self.nav_buttons.get(page_id)
        if button is not None:
            self.set_active_button(button)
    
    def on_nav_clicked(self, button, page_id):
        """Handle navigation click"""
        self.set_active_button(button)
        self.nav_manager.navigate_to(page_id)
        self.emit('page-changed', page_id)
