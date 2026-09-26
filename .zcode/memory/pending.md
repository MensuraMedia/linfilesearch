# Pending

- Roadmap next: filters popover (type/size/date), preview snippet match highlighting, throughput benchmark, .deb packaging.
- Icon tint decision still open: monochrome-white (current) vs accent-tinted active states.
- Skip lists (venv/node_modules/dotfiles) are configured skips with no UI escape hatch — revisit if operator reports 'missing' files inside them.
- Hover-over-selected CSS hardened spec-side (background-image:none + ordering) and offscreen-verified, but no real-mouse verification possible on this machine (no xdotool/pyautogui) — operator should wave the cursor over a selected row.
- Operator's monitor may run fractional scaling (captures arrive at 2×) — if pixel-level complaints persist, verify alignment on their display before changing code (r031 lesson).
