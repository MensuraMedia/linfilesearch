# Search Row Spec — Option A (applied)

Status: **chosen by operator and applied to the app** (r013, 2026-09-25)
Reference mockup: `docs/mockups/mockup-searchrow.html` (Option A panel)
Lineage: proportions taken from the original A2 mockup
(`docs/mockups/mockup-a2-preview.html`).

## The rule

The search field defines the row height. Every control in the row stretches
flush to that height — no control may render taller or shorter than the field,
and no control may exceed the rendered sidebar nav button height.

## Dimensions (Option A)

| Element | Spec |
|---|---|
| Search field | 38 px tall, 11 pt text, inset dark fill (#262626) |
| Mode strip (Aa / * / .*) | one joined segmented control, 38 px, 16 px icons, 9 pt labels |
| Pause | borderless flat button, 38 px, **columns** icon (two vertical bars) |
| Stop | borderless flat button, 38 px, **stop** icon (plain square) |
| Search button | accent blue (#0078D7), 38 px, 16 px icon + bold 9 pt label |
| Sidebar nav (reference) | renders 36–40 px — row at 38 px stays at-or-below |

## Icon selection (operator, r012)

- Pause is represented by the Phosphor **columns** icon (two bars ·|·), not
  `pause-circle`.
- Stop is the plain Phosphor **stop** square, not `stop-circle`.
- Both live in `resources/icons/{regular,fill}` (subset revision s012_b).

## Why Option A was recommended

1. It reproduces the proportions of the approved A2 mockup exactly (field
   ~38 px, 16 px icons) instead of inventing new numbers.
2. Flush-to-field heights eliminate the mismatch class of bug outright: GTK
   pinning uses one shared `SEARCH_ROW_HEIGHT` for the field and every
   control, so uneven heights cannot recur.
3. Borderless pause/stop and the joined mode strip keep the visual weight low
   even at 38 px — the original "too big" complaint came from boxed buttons
   sitting next to a differently-sized field.

## Implementation map

- `src/config/config_layout.py` — `SEARCH_ROW_HEIGHT = 38`;
  `MAIN_BUTTON_MAX_HEIGHT = 40` (the rendered sidebar ceiling).
- `src/config/config_search.py` — `ICONS['pause'] = 'columns'`,
  `ICONS['stop'] = 'stop'`.
- `src/pages/page_search.py` — search-row controls use 16 px icons
  (`ROW_ICON_SIZE`) and share `SEARCH_ROW_HEIGHT`.
- `resources/css/style.css` — `.mode-group` joined strip, `.flat-icon-button`
  borderless, `.primary-button` label styling.
- Enforcement: `tests/test_button_caps.py` (all content-area buttons ≤ sidebar
  render size) and `tests/test_spreadsheet_and_preview.py`
  (`test_search_row_uniform_height` — every row control shares the constant).

## Verification

Rendered screenshots are pixel-checked after every change to this row; the
acceptance bar is: single uniform strip, tops and bottoms aligned, all
controls at-or-below the sidebar nav buttons, pause/stop icons clearly
distinct at 16 px.
