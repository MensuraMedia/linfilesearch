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

    # Main-page button cap (operator rules r006-r013): buttons in the content
    # area must never exceed the RENDERED sidebar nav button size (36-40px;
    # the nominal 28px in NAV_BUTTON_HEIGHT is not what renders).
    MAIN_BUTTON_MAX_HEIGHT = 40
    MAIN_BUTTON_MAX_WIDTH = SIDEBAR_WIDTH - 2 * NAV_BUTTON_PADDING_H   # 130
    MAIN_BUTTON_TARGET_HEIGHT = 24
    MAIN_BUTTON_ICON_SIZE = 12

    # Operator rule r011/r013 (Option A, docs/search-row-spec.md): every
    # control in the search row shares the field's height, flush.
    SEARCH_ROW_HEIGHT = 38
    SEARCH_ROW_ICON_SIZE = 16

    # Compact sidebar header (operator rule r025): small square logo cell
    # beside the wordmark; replaces the old 150x150 centered logo block
    LOGO_CELL_SIZE = 34
    LOGO_CELL_ICON = 20
    
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


# Results sheet minimum column widths on open (operator rule r025): total
# deliberately exceeds a narrow window — the sheet scrolls horizontally
# instead of crushing Name/Path into unreadable slivers.
RESULTS_MIN_WIDTHS = {
    'Modified': 95,
    'Name': 200,
    'Path': 300,
    'Size': 75,
    'Type': 95,
    'Mount': 90,
}
