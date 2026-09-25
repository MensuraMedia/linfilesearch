"""
Treeview Spreadsheet Utilities
Traditional spreadsheet behaviour for Gtk.TreeView sheets:
- double-click on a column boundary auto-fits the column width to its contents
- vertical grid lines (cell borders) enabled

Columns register the model index they render as text via set_text_index()
so auto-fit can measure real content.
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

EDGE_GRAB_PX = 6          # click within this many px of a column edge
MAX_AUTOFIT_WIDTH = 400   # cap so a huge path cannot blow out the layout
MIN_AUTOFIT_WIDTH = 40


def attach_spreadsheet_behavior(view):
    """Enable grid lines + double-click column auto-fit on a TreeView."""
    view.set_grid_lines(Gtk.TreeViewGridLines.VERTICAL)
    view.connect('button-press-event', _on_button_press)


def set_text_index(column, model_idx):
    """Record which model column this TreeViewColumn renders as text."""
    column._linfilesearch_text_col = model_idx


def _on_button_press(view, event):
    """Double-click near a column edge auto-fits that column."""
    if event.type != Gdk.EventType._2BUTTON_PRESS or event.button != 1:
        return False
    edge = _column_edge_at(view, int(event.x), int(event.y))
    if edge is None:
        return False
    auto_fit_column(edge)
    return True


def _column_edge_at(view, x, y):
    """Column whose RIGHT edge is within EDGE_GRAB_PX of x, or None."""
    if view.get_path_at_pos(x, y) is None and \
            view.get_path_at_pos(max(0, x - EDGE_GRAB_PX), y) is None:
        return None
    x_off = 0
    for col in view.get_columns():
        width = col.get_width()
        if abs(x - (x_off + width)) <= EDGE_GRAB_PX:
            return col
        x_off += width
    return None


def auto_fit_column(column):
    """Size a column to its widest content (header + cells, capped)."""
    view = column.get_tree_view()
    if view is None:
        return
    model = view.get_model()
    if model is None:
        return

    text_idx = getattr(column, '_linfilesearch_text_col', None)
    max_w = _measure_text(view, column.get_title() or '') + 34
    for row in model:
        value = row[text_idx] if text_idx is not None else ''
        if not isinstance(value, str):
            value = str(value)
        max_w = max(max_w, _measure_text(view, value or ' ') + 30)
        if max_w >= MAX_AUTOFIT_WIDTH:
            break

    width = max(MIN_AUTOFIT_WIDTH, min(max_w, MAX_AUTOFIT_WIDTH))
    column.set_fixed_width(width)
    view.queue_resize()


def _measure_text(view, text):
    layout = view.create_pango_layout(text)
    _, logical = layout.get_pixel_extents()
    return logical.width
