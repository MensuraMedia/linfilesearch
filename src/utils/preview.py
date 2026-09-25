"""
Preview Provider
Real content previews for the fold-out pane:
- images: scaled thumbnail (GdkPixbuf)
- PDF: first page via pdftoppm when available
- odt/docx (zip-based office files): readable text extracted from the XML
- plain text files: first bytes of content
Everything else falls back to the file-type icon.
"""

import os
import re
import subprocess
import zipfile

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GdkPixbuf

MAX_TEXT_BYTES = 4096
IMAGE_MAX_W, IMAGE_MAX_H = 246, 180
PDF_SCALE = 300

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
ZIP_TEXT_PARTS = {
    '.odt': ('content.xml', None),
    '.ods': ('content.xml', None),
    '.odp': ('content.xml', None),
    '.docx': ('word/document.xml', 'w:br'),
    '.xlsx': ('xl/sharedStrings.xml', None),
    '.pptx': ('ppt/slides/slide1.xml', None),
}


def preview_for(path):
    """Return ('image', GdkPixbuf) | ('text', str) | ('icon', None) for a path."""
    if not path or not os.path.isfile(path):
        return ('icon', None)
    ext = os.path.splitext(path)[1].lower()

    if ext in IMAGE_EXTS:
        pb = _image_thumb(path)
        return ('image', pb) if pb is not None else ('icon', None)

    if ext == '.pdf':
        pb = _pdf_thumb(path)
        if pb is not None:
            return ('image', pb)

    if ext in ZIP_TEXT_PARTS:
        text = _zip_text(path, *ZIP_TEXT_PARTS[ext])
        if text:
            return ('text', text)

    try:
        with open(path, 'rb') as fh:
            head = fh.read(2048)
        if b'\x00' in head:
            return ('icon', None)          # binary
        with open(path, 'r', errors='replace') as fh:
            return ('text', fh.read(MAX_TEXT_BYTES))
    except OSError:
        return ('icon', None)


def _image_thumb(path):
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(
            path, IMAGE_MAX_W, IMAGE_MAX_H, True)
    except Exception:
        return None


def _pdf_thumb(path):
    if _which('pdftoppm') is None:
        return None
    try:
        out = subprocess.run(
            ['pdftoppm', '-png', '-singlefile', '-scale-to', str(PDF_SCALE),
             path, '/tmp/linfilesearch-preview'],
            capture_output=True, timeout=10)
        png = '/tmp/linfilesearch-preview.png'
        if out.returncode != 0 or not os.path.exists(png):
            return None
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            png, IMAGE_MAX_W, IMAGE_MAX_H, True)
        os.unlink(png)
        return pb
    except Exception:
        return None


def _zip_text(path, part_name, _break_tag=None):
    """Extract readable text from a zip-based office document."""
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read(part_name).decode('utf-8', errors='replace')
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    text = re.sub(r'<[^>]+>', ' ', xml)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return None
    return text[:MAX_TEXT_BYTES]


def _which(name):
    for d in os.environ.get('PATH', '').split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None
