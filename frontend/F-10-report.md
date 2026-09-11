# F-10: Deduplicate P07 CSS — Report

## What Changed
- `frontend/app/globals.css`: consolidated 3 duplicate `.mk-p07` base blocks (A at line 3213, B at 5480, C at 6094) into 1 canonical block (line 3213).

## Blocks Removed
- **Block A base** (lines 3213-3782, 571 lines): Original P07 design. Merged into canonical block.
- **Block B base + media** (lines 5477-6089, 613 lines): Byte-identical duplicate of Block A. Deleted entirely.
- **Block C base + media** (lines 6091-6696, 606 lines): Newer P07 design (last in cascade, wins conflicts). Merged into canonical block.
- **Block A max-767 media** (lines 3805-3822): Fully superseded by C's max-767 media (C later in cascade wins all live selectors).

## What Was Kept
- **Merged canonical base** (109 selectors, 16KB): All unique selectors from A and C. For shared selectors, C's values win (matches original cascade: A base → C base = C last-wins).
- **A's min-768 media** (lines 3784-3803): Only source of `flex-direction: row` for `.mk-p07-actions` at desktop width. C has no min-width media block.
- **C's max-1024 media** (lines 6650-6657): Tablet breakpoint.
- **C's max-767 media** (lines 6659-6696): Mobile breakpoint. Supersedes A's max-767 for all live selectors.

## Cascade Equivalence Verified
- Script simulated last-wins cascade across A→B→C (original) vs A→C (merged, since B==A).
- Result: **identical** — 109 selectors, same declarations per selector.
- A-only properties (e.g. `.mk-p07-brand{flex-shrink:0}`, `.mk-p07-nav{font-size:11px;flex-wrap:nowrap}`, `.mk-p07-footer{font-size:12px;color:var(--mk-text-secondary)}`) preserved because C does not define them.

## Verification
| Check | Result |
|-------|--------|
| tsc --noEmit | PASS |
| npm run build | PASS (4 routes: /, /_not-found, /doctor, /patient) |
| pytest | 151 passed |
| audit | 9/9 PASS |
| Duplicate selectors in merged block | 0 (109 unique) |
| Canonical `.mk-p07 {` count | Exactly 1 |

## File Impact
- Line reduction: 7087 → 6210 (−877 lines, −12.4%)
- No visual changes (cascade equivalence proven)
- No UI redesign, no backend changes, no LLM/OCR logic changes
