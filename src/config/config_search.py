"""
Search Configuration
Defaults, icon map, filesystem classification, file-type detection
"""

# Filesystem types that are never searched (pseudo/ephemeral filesystems)
SKIP_FSTYPES = {
    'proc', 'procfs', 'sysfs', 'devfs', 'devtmpfs', 'devpts', 'tmpfs',
    'squashfs', 'overlay', 'efivarfs', 'fusectl', 'rpc_pipefs', 'cgroup',
    'cgroup2', 'pstore', 'bpf', 'tracefs', 'debugfs', 'configfs',
    'autofs', 'mqueue', 'hugetlbfs', 'ramfs', 'securityfs', 'nsfs',
}

# Path prefixes that are never searched
SKIP_PREFIXES = (
    '/proc', '/sys', '/dev', '/run', '/var/lib/docker', '/boot/efi',
)

# Real filesystems we search by default
SEARCHABLE_FSTYPES = {
    'ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'zfs', 'f2fs', 'jfs',
    'ntfs', 'ntfs3', 'exfat', 'vfat', 'fat', 'fuseblk', 'udf',
    'apfs', 'hgfs', 'virtiofs',
}

# Directories skipped during traversal (per-path basename match)
SKIP_DIR_NAMES = {'.git', 'node_modules', '__pycache__', '.cache', '.venv', 'venv'}

# Query modes
MODE_SUBSTRING = 'substring'
MODE_WILDCARD = 'wildcard'
MODE_REGEX = 'regex'

# Icon name -> UI purpose (subset of resources/icons, see manifest.txt)
ICONS = {
    'search': 'magnifying-glass',
    'clear': 'x',
    'stop': 'stop-circle',
    'pause': 'pause-circle',
    'play': 'play',
    'refresh': 'arrow-clockwise',
    'spinner': 'spinner-gap',
    'filters': 'funnel',
    'advanced': 'sliders-horizontal',
    'case': 'text-aa',
    'wildcard': 'asterisk',
    'regex': 'brackets-curly',
    'date': 'calendar-blank',
    'all_mounts': 'hard-drives',
    'drive': 'hard-drive',
    'usb': 'usb',
    'network': 'network',
    'folder_scope': 'path',
    'folder_open': 'folder-open',
    'folder': 'folder',
    'file': 'file',
    'file_text': 'file-text',
    'file_pdf': 'file-pdf',
    'file_zip': 'file-zip',
    'file_code': 'file-code',
    'image': 'image',
    'audio': 'music-notes',
    'video': 'video-camera',
    'list_view': 'list-dashes',
    'grid_view': 'squares-four',
    'preview': 'eye',
    'copy': 'copy',
    'trash': 'trash',
    'info': 'info',
    'warning': 'warning',
    'done': 'check-circle',
    'lock': 'lock',
    'history': 'clock-counter-clockwise',
    'saved': 'bookmark-simple',
    'settings': 'gear-six',
    'open': 'arrow-square-out',
    'add': 'plus-circle',
    'clock': 'clock',
}

# Extension -> (icon key, type label)
TYPE_BY_EXT = {
    '.txt': ('file_text', 'Text'),
    '.md': ('file_text', 'Text'),
    '.odt': ('file_text', 'Document'),
    '.ods': ('file_text', 'Spreadsheet'),
    '.odp': ('file_text', 'Presentation'),
    '.doc': ('file_text', 'Document'),
    '.docx': ('file_text', 'Document'),
    '.xls': ('file_text', 'Spreadsheet'),
    '.xlsx': ('file_text', 'Spreadsheet'),
    '.ppt': ('file_text', 'Presentation'),
    '.pptx': ('file_text', 'Presentation'),
    '.pdf': ('file_pdf', 'PDF'),
    '.zip': ('file_zip', 'Archive'),
    '.tar': ('file_zip', 'Archive'),
    '.gz': ('file_zip', 'Archive'),
    '.bz2': ('file_zip', 'Archive'),
    '.xz': ('file_zip', 'Archive'),
    '.7z': ('file_zip', 'Archive'),
    '.py': ('file_code', 'Source'),
    '.sh': ('file_code', 'Source'),
    '.js': ('file_code', 'Source'),
    '.ts': ('file_code', 'Source'),
    '.c': ('file_code', 'Source'),
    '.h': ('file_code', 'Source'),
    '.cpp': ('file_code', 'Source'),
    '.json': ('file_code', 'Source'),
    '.yaml': ('file_code', 'Source'),
    '.yml': ('file_code', 'Source'),
    '.toml': ('file_code', 'Source'),
    '.png': ('image', 'Image'),
    '.jpg': ('image', 'Image'),
    '.jpeg': ('image', 'Image'),
    '.gif': ('image', 'Image'),
    '.svg': ('image', 'Image'),
    '.webp': ('image', 'Image'),
    '.bmp': ('image', 'Image'),
    '.mp3': ('audio', 'Audio'),
    '.wav': ('audio', 'Audio'),
    '.flac': ('audio', 'Audio'),
    '.ogg': ('audio', 'Audio'),
    '.m4a': ('audio', 'Audio'),
    '.mp4': ('video', 'Video'),
    '.mkv': ('video', 'Video'),
    '.avi': ('video', 'Video'),
    '.webm': ('video', 'Video'),
    '.mov': ('video', 'Video'),
}

# Text extensions eligible for snippet preview
TEXT_EXTS = {'.txt', '.md', '.py', '.sh', '.js', '.ts', '.c', '.h', '.cpp',
             '.json', '.yaml', '.yml', '.toml', '.log', '.cfg', '.ini', '.conf'}

DEFAULTS = {
    'case_sensitive': False,
    'mode': MODE_SUBSTRING,
    'include_hidden': False,
    'follow_symlinks': False,
    'snippet_max_bytes': 4096,
    'snippet_file_limit': 262144,   # 256 KB
}


def classify_fstype(fstype):
    """Return 'searchable' | 'skip' for a filesystem type."""
    if fstype in SKIP_FSTYPES:
        return 'skip'
    if fstype in SEARCHABLE_FSTYPES:
        return 'searchable'
    # gvfs user mounts (MTP phones, network places): searchable
    if fstype == 'fuse.gvfsd-fuse':
        return 'searchable'
    # other FUSE mounts (AppImages, portals): skip by default
    return 'skip'


def should_skip_path(path):
    """True when a mountpoint path is excluded by prefix rules."""
    return any(path == p or path.startswith(p + '/') for p in SKIP_PREFIXES)


def file_type_info(filename, is_dir=False):
    """Return (icon_key, type_label) for a filename."""
    import os
    if is_dir:
        return ('folder', 'Folder')
    ext = os.path.splitext(filename)[1].lower()
    return TYPE_BY_EXT.get(ext, ('file', 'File'))
