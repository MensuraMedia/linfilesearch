# Header Style Spec — V2 Soft Hairline (applied)

Status: **chosen by operator and applied to the app** (r017, 2026-09-25)
Reference study: `docs/mockups/mockup-headers.html` (variant V2)

## The rule

Every spreadsheet header band (results, History, Saved) uses a soft hairline
full border around each header cell — clearly visible cell edges without the
glare that #ccc had on the dark fill.

## Specification

| Property | Value |
|---|---|
| Border | 1px solid `#767676`, all four sides of every header cell |
| Header fill | `#313131` |
| Header text | `#aaaaaa`, 9pt |
| Padding | 4px vertical / 6px horizontal (≥4px on all sides) |

## Why V2

- Keeps the spreadsheet grid legible (the reason borders were introduced)
  at a contrast level that sits with the dark theme instead of shouting over
  it — #ccc read as glare, #4a4a4a was too quiet.
- Full cell borders preserve the column-edge affordance that pairs with the
  double-click auto-fit behavior.
- Same border on all three sheets keeps the sheets visually identical.

## Implementation map

- `resources/css/style.css` — `.results-tree header button,
  .sheet-tree header button { border: 1px solid #767676; padding: 4px 6px; }`
- Applied to results (`page_search`), History, and Saved sheets via their
  shared `sheet-tree` / `results-tree` classes.

## Acceptance

Header cells show a uniform soft-grey hairline on all sides at ≥4px padding,
identical across all three sheets; verified against a live screenshot.
