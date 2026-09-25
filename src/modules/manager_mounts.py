"""
Mount Manager
Enumerates mountpoints from /proc/self/mounts, enriches with lsblk metadata,
classifies searchable vs skipped, and watches for changes via Gio when available.
"""

import os
import json
import subprocess

from config.config_search import classify_fstype, should_skip_path

PROC_MOUNTS = '/proc/self/mounts'


def _unescape_mountpoint(raw):
    """Decode octal escapes (\\040 etc.) used in /proc/self/mounts."""
    out, i = [], 0
    while i < len(raw):
        if raw[i] == '\\' and i + 3 < len(raw) + 1 and raw[i + 1:i + 4].isdigit():
            try:
                out.append(chr(int(raw[i + 1:i + 4], 8)))
                i += 4
                continue
            except ValueError:
                pass
        out.append(raw[i])
        i += 1
    return ''.join(out)


def parse_proc_mounts(proc_mounts_text):
    """Parse /proc/self/mounts text into raw mount tuples.

    Returns list of (device, mountpoint, fstype) preserving order.
    """
    mounts = []
    for line in proc_mounts_text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mountpoint, fstype = parts[0], parts[1], parts[2]
        mounts.append((device, _unescape_mountpoint(mountpoint), fstype))
    return mounts


def _lsblk_devices():
    """Map device name (e.g. sda1, nvme0n1p2) -> {tran, size_bytes}."""
    devices = {}
    try:
        out = subprocess.run(
            ['lsblk', '-J', '-o', 'NAME,SIZE,TYPE,TRAN,MOUNTPOINTS'],
            capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return devices
        tree = json.loads(out.stdout or '{}')
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        return devices

    def walk(node, parent_tran=None):
        tran = node.get('tran') or parent_tran
        size = node.get('size', '')
        devices[node['name']] = {'tran': tran, 'size': size}
        for child in node.get('children', []):
            walk(child, tran)
    for disk in tree.get('blockdevices', []):
        walk(disk)
    return devices


def _transport_class(transport):
    if transport == 'usb':
        return 'usb'
    if transport == 'nvme':
        return 'nvme'
    if transport in ('sata', 'sas', 'scsi', 'ata'):
        return 'disk'
    return None


class MountInfo:
    """One enumerated mountpoint."""

    def __init__(self, mountpoint, device, fstype, transport=None, size_text=None):
        self.mountpoint = mountpoint
        self.device = device
        self.fstype = fstype
        self.transport = transport
        self.size_text = size_text
        self.searchable = (
            classify_fstype(fstype) == 'searchable'
            and not should_skip_path(mountpoint)
            and os.path.exists(mountpoint)
        )

    @property
    def device_class(self):
        """Icon key: all_mounts-like class for chips (usb/drive/network)."""
        cls = _transport_class(self.transport)
        if cls == 'usb':
            return 'usb'
        if self.fstype.startswith('fuse.') or ':' in self.device:
            return 'network'
        return 'drive'

    def capacity(self):
        """(free_bytes, total_bytes) via statvfs, or None."""
        try:
            st = os.statvfs(self.mountpoint)
            return (st.f_bavail * st.f_frsize, st.f_blocks * st.f_frsize)
        except OSError:
            return None

    def __repr__(self):
        return f"MountInfo({self.mountpoint!r}, dev={self.device!r}, fs={self.fstype!r}, searchable={self.searchable})"


class MountManager:
    """Enumerates and watches mountpoints."""

    def __init__(self):
        self._monitor = None
        self._callbacks = []
        self._install_monitor()

    def _install_monitor(self):
        """Optional live mount/umount notifications."""
        try:
            from gi.repository import Gio
            self._monitor = Gio.UnixMountMonitor.get()
            self._monitor.connect('mounts-changed', self._on_mounts_changed)
        except Exception:
            self._monitor = None

    def _on_mounts_changed(self, *args):
        for cb in self._callbacks:
            cb()

    def on_change(self, callback):
        """Register callback fired when the OS mount table changes."""
        self._callbacks.append(callback)

    def enumerate(self):
        """Return list[MountInfo] for all mountpoints, in /proc order."""
        try:
            with open(PROC_MOUNTS, 'r', encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        except OSError:
            return []
        blk = _lsblk_devices()
        mounts = []
        for device, mountpoint, fstype in parse_proc_mounts(text):
            dev_name = device.split('/')[-1] if device.startswith('/') else None
            meta = blk.get(dev_name, {}) if dev_name else {}
            mounts.append(MountInfo(
                mountpoint, device, fstype,
                transport=meta.get('tran'),
                size_text=meta.get('size'),
            ))
        return mounts

    def searchable_mounts(self):
        """Return list[MountInfo] filtered to searchable mounts."""
        return [m for m in self.enumerate() if m.searchable]

    def refresh(self):
        """Force monitor rescan (no-op enumeration aid for callers)."""
        if self._monitor is not None:
            try:
                self._monitor.rate_limit()
            except Exception:
                pass
