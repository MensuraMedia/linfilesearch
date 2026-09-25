"""
Icon Loader
Loads Phosphor SVGs from resources/icons, tints them to a solid color
(they are solid black by default), and caches pixbufs by (name, size, color).
"""

import io
import os
import threading

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GdkPixbuf
from PIL import Image

ICONS_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'resources', 'icons')

_cache = {}
_lock = threading.Lock()

DEFAULT_TINT = (0xee, 0xee, 0xee)     # near-white foreground
ACCENT_TINT = (0x00, 0x78, 0xd7)      # starter accent blue
MOUNT_TINT = (0x9c, 0xd0, 0xff)      # light blue used for mount chips


def _svg_path(name, weight='regular'):
    return os.path.join(ICONS_DIR, weight, f'{name}.svg')


def _tint(pixbuf, rgb):
    """Recolor a pixbuf: keep its alpha, replace RGB with rgb."""
    try:
        ok, buf = pixbuf.save_to_bufferv('png', [], [])
    except Exception:
        return pixbuf
    if not ok:
        return pixbuf
    src = Image.open(io.BytesIO(buf))
    out = Image.new('RGBA', src.size, rgb + (255,))
    out.putalpha(src.getchannel('A'))
    target = io.BytesIO()
    out.save(target, format='png')
    loader = GdkPixbuf.PixbufLoader()
    loader.write(target.getvalue())
    loader.close()
    return loader.get_pixbuf()


def get_icon(name, size=16, tint=None, weight='regular'):
    """Return a cached GdkPixbuf for an icon name at a size and tint.

    Falls back to 'file' when the named icon is missing; returns None
    only when even the fallback is absent.
    """
    rgb = tint if tint is not None else DEFAULT_TINT
    key = (name, size, rgb, weight)
    with _lock:
        if key in _cache:
            return _cache[key]

    path = _svg_path(name, weight)
    if not os.path.exists(path):
        if name == 'file':
            return None
        return get_icon('file', size, tint, weight)

    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
    pixbuf = _tint(pixbuf, rgb)
    with _lock:
        _cache[key] = pixbuf
    return pixbuf


def get_image(name, size=16, tint=None, weight='regular'):
    """Return a Gtk.Image widget for an icon name."""
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    pixbuf = get_icon(name, size, tint, weight)
    if pixbuf is None:
        return Gtk.Image()
    return Gtk.Image.new_from_pixbuf(pixbuf)
