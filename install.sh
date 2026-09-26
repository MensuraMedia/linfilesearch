#!/usr/bin/env bash
# linfilesearch installer — user-level, no root required.
# Installs the application icon set, a launcher in ~/.local/bin, and a
# .desktop entry with StartupWMClass (taskbar / ALT+TAB grouping).
# Usage:   ./install.sh [--uninstall]
set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_SRC="$PROJ/resources/images/app-icon"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor"
BIN="$BIN_DIR/linfilesearch"
DESKTOP="$APP_DIR/linfilesearch.desktop"
APP_NAME='linfilesearch'

uninstall=0
[ "${1:-}" = "--uninstall" ] && uninstall=1

if [ "$uninstall" -eq 1 ]; then
  rm -f "$BIN" "$DESKTOP"
  find "$ICON_DIR" -name "$APP_NAME.png" -delete 2>/dev/null || true
  command -v update-desktop-database >/dev/null && update-desktop-database "$APP_DIR" || true
  echo "uninstalled: launcher, .desktop, icons"
  echo "kept: ~/.config/linfilesearch (search history and saved searches)"
  exit 0
fi

[ -d "$ICON_SRC" ] || { echo "no icons at $ICON_SRC" >&2; exit 1; }

# icons -> hicolor/<size>/apps/
for f in "$ICON_SRC"/*.png; do
  size="$(basename "$f" .png)"
  dest="$ICON_DIR/${size}x${size}/apps"
  mkdir -p "$dest"
  cp "$f" "$dest/$APP_NAME.png"
done
echo "icons: installed to $ICON_DIR (13 sizes)"

# launcher wrapper
mkdir -p "$BIN_DIR"
rev="$(git -C "$PROJ" rev-parse --short HEAD 2>/dev/null || echo unversioned)"
cat > "$BIN" <<EOF
#!/usr/bin/env bash
# linfilesearch launcher (project install.sh, rev $rev)
cd "$PROJ" || exit 1
exec python3 src/main.py "\$@"
EOF
chmod +x "$BIN"
echo "launcher: $BIN (rev $rev)"

# .desktop entry
mkdir -p "$APP_DIR"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=LinFileSearch
GenericName=File Search
Comment=Search files across all mountpoints, including external drives
Exec=$BIN
Icon=$APP_NAME
Terminal=false
Categories=Utility;System;FileTools;FileManager;
Keywords=search;files;find;mountpoints;drives;grep;
StartupNotify=true
StartupWMClass=linfilesearch
X-GNOME-UsesNotifications=false
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$APP_DIR" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t -f "$ICON_DIR" 2>/dev/null || true
echo "desktop: $DESKTOP"
echo "installed. Start from the application menu, or run: linfilesearch"
