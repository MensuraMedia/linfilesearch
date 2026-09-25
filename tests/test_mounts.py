"""Unit tests for mount parsing and classification (pure functions)."""

from modules.manager_mounts import parse_proc_mounts, _unescape_mountpoint
from config.config_search import classify_fstype, should_skip_path


PROC_SAMPLE = """\
/dev/nvme0n1p2 / ext4 rw,relatime 0 0
/dev/nvme0n1p3 /home ext4 rw,relatime 0 0
/dev/sda1 /mnt/data ext4 rw,relatime 0 0
/dev/nvme0n1p1 /boot/efi vfat rw,relatime 0 0
tmpfs /run tmpfs rw,nosuid 0 0
/dev/loop5 /snap/lxd/40585 squashfs ro 0 0
gvfsd-fuse /run/user/1000/gvfs fuse.gvfsd-fuse rw,nosuid 0 0
/dev/sdb1 /media/user/My\\040Drive ext4 rw 0 0
"""


def test_parse_proc_mounts_count():
    mounts = parse_proc_mounts(PROC_SAMPLE)
    assert len(mounts) == 8


def test_parse_octal_escape():
    mounts = parse_proc_mounts(PROC_SAMPLE)
    assert any(m[1] == '/media/user/My Drive' for m in mounts)


def test_unescape_plain():
    assert _unescape_mountpoint('/mnt/data') == '/mnt/data'


def test_classification_ext4_searchable():
    assert classify_fstype('ext4') == 'searchable'
    assert classify_fstype('ntfs') == 'searchable'
    assert classify_fstype('exfat') == 'searchable'


def test_classification_pseudo_skipped():
    for fs in ('proc', 'sysfs', 'tmpfs', 'squashfs', 'overlay', 'efivarfs'):
        assert classify_fstype(fs) == 'skip', fs


def test_classification_gvfs_searchable():
    assert classify_fstype('fuse.gvfsd-fuse') == 'searchable'


def test_path_prefix_rules():
    assert should_skip_path('/proc')
    assert should_skip_path('/proc/self')
    assert should_skip_path('/run/user/1000')
    assert not should_skip_path('/home')
    assert not should_skip_path('/mnt/data')
    assert not should_skip_path('/runtime')          # prefix must not over-match
