"""
Layout Configuration
Centralized layout dimensions and spacing constants
"""

class Dimensions:
    """Layout dimension constants"""
    
    # Sidebar
    SIDEBAR_WIDTH = 150
    
    # Logo area
    LOGO_AREA_WIDTH = 150
    LOGO_AREA_HEIGHT = 150
    LOGO_IMAGE_SIZE = 145
    
    # Navigation buttons
    NAV_BUTTON_HEIGHT = 28
    NAV_BUTTON_PADDING_V = 6
    NAV_BUTTON_PADDING_H = 10

    # Main-page button cap (operator rules r006/r008/r011): buttons in the
    # content area must never exceed the RENDERED sidebar nav button size
    # (~36-40px; the nominal 28px in NAV_BUTTON_HEIGHT is not what renders).
    # The search row is uniformly SEARCH_ROW_HEIGHT (30px) per r011.
    MAIN_BUTTON_MAX_HEIGHT = 36
    MAIN_BUTTON_MAX_WIDTH = SIDEBAR_WIDTH - 2 * NAV_BUTTON_PADDING_H   # 130
    MAIN_BUTTON_TARGET_HEIGHT = 24
    MAIN_BUTTON_ICON_SIZE = 12

    # Operator rule r011: every control in the search row (entry, mode
    # toggles, pause/stop, Search button) shares one uniform height.
    SEARCH_ROW_HEIGHT = 30
    
    # Content area
    CONTENT_MARGIN = 40
    CONTENT_SPACING = 15
    
    # Window
    WINDOW_DEFAULT_WIDTH = 1200
    WINDOW_DEFAULT_HEIGHT = 800


class Spacing:
    """Spacing constants"""
    
    NONE = 0
    SMALL = 5
    MEDIUM = 10
    LARGE = 15
    XLARGE = 20


class Layout:
    """Main layout configuration"""
    
    dimensions = Dimensions
    spacing = Spacing
