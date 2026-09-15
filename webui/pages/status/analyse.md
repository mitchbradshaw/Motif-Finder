# Status — Analyse › Chain unit

| page | status | what's left | last commit |
|---|---|---|---|
| analyse.chain | done | live path unchanged; demo mode covers frames 1, 1b, 1c, 1d, 1e, 1f, 1g, 1h, 1i, 2 | demo chain states + insert modal |
| analyse.block | done | demo block pages 01 Baseline (5), 02 Noise floor (6), 03 Encoding (3), 04 Detection (4), Matrix profile (7), Threshold (7b), Model stage (8), generic; live block page unchanged | demo block pages |
| analyse.glyphs | done | 21-glyph registry (frame 6b) with detail drawer; 12 glyphs added to analyse/glyphs.tsx | glyph registry |

Smoke: `smoke.py --pages-only --only analyse` → 43 states, 0 failures.
