# Inventory — Analyse › Chain

Frames: `prototyping/imgs/analyse-chain/*.pdf`. Two modes share one route: **live** (no `template`/`state` query —
the bridge's real adapters: detrend → matrix_profile → threshold, SSE runs) and **demo** (`?template=<name>` or
`?state=…` — the B24 detection chain and the other frame chains as `demo.*` blocks, validated locally, run on
`useSim`, fixture payloads drawn through `analyse/Renderer.tsx`). Block indices in `#/analyse/block/<i>` are the
**0-based step index** in both modes (live smoke flows depend on it): `block/0` = 01.

## Pages

| page id | route | frames covered | spec § | states (deep link) |
|---|---|---|---|---|
| analyse.chain | `#/analyse/chain` | chain-1, 1b, 1c, 1d, 1e, 1f, 1g, 1h, 1i, 2 | §6.1–6.4, §6.8 States, P1, P2, P4, P24 | live · `template=drop_motifs9` (1) · `&popover=history` (1b) · `state=empty&modal=import` (1c) · `&state=running` (1d) · `&state=invalid` (1e) · `&state=failed` (1f) · `template=mp_full_channel_CH4` (1g) · `template=mp_span_CH4` (1h) · `template=sax_vs_mp` (1i) · `&modal=insert&at=3` (2) |
| analyse.block | `#/analyse/block/<i>` | chain-3, 4, 5, 6, 7, 7b, 8 | §6.5, §6.8, P5 | live `block/1`, `block/2` · demo `block/0..3?template=drop_motifs9` (5, 6, 3, 4) · `block/0?template=mp_span_CH4` (7) · `block/1?template=mp_span_CH4` (7b, after inserting threshold or `&with=threshold`) · `block/1?template=spiketrain_cnn_CH4` (8) · `&state=running` · `&state=stale` |
| analyse.glyphs | `#/analyse/glyphs` | chain-6b | §6.8 glyph row | default · `?focus=<glyph>` detail |

## analyse.chain

**Regions** — toolbar (name chip with rename + run state, source chip ▾ popover, surrogate toggle / null chip,
estimate text, History, Import, Save template, primary Run / Re-run from 0N / Retry from 0N / Cancel / Export HPC job /
Continue from 03); rows (Source + one row per block: grip, number, name, badge, signature, one-line caption,
settings · bypass · duplicate · delete; plot on the shared time axis); `+ insert` between every pair and at the end;
end-of-chain suggestion card (1h); shared time axis; footer (terminal chip, headline + sub, Export run, Analyse events,
Pass N to Review); bottom cards for 1g (Generated job + After it finishes) and 1i (Paused run log + When you continue).

**Controls & interactions** — Run starts a simulated run (queued → running per stage with `64 % · 0.2 s left`,
downstream `waits for 0N · last result hidden`, Cancel between stages) ending in fixture results; the default
drop_motifs9 fails at 04 (merge window 2.0 s < trough window 2.4 s) → error card with View log · Open settings ·
Retry 04; delete a stage → invalid junction pill (Insert X here · Show blocks that fit), Run disabled with reason,
toast Undo / Ctrl Z; bypass/duplicate edit the chain and re-validate; editing marks downstream stale; History popover
(filters, search, fits-current-source checkbox, Open, Apply to source with disabled reasons, diff callout, pager,
Save current chain first); Import modal (search, kind tabs, list with fit reasons, detail + On apply, Import .json
file → not wired, Apply to this source); Insert-stage modal (breadcrumb ribbon, three contract pills, search,
category tabs, sort, show incompatible, fits / doesn't-fit cards with reasons, detail panel with defaults,
cost/null/side-inputs tiles, `04 goes stale · 00–03 stay cached`, Insert / Insert and open settings); HPC card
(Create SLURM script writes a job to the in-memory Jobs store, Upload computed profile moves to "result in place",
Copy script / Download job); Paused card (Open in Jobs ↗, Continue from 03).

**Fixtures** — `fixtures/analyse.ts`: `DEMO_BLOCKS` (22 demo adapters with glyph, signature, category, cost,
null, params, description), `DEMO_TEMPLATES` (drop_motifs9 v3 · a7f39c, sharkfin_v2, banded_sax_lp,
slope_interrogation, cnn_windows_v2, mp_span_CH4, mp_full_channel_CH4, sax_vs_mp, spiketrain_cnn_CH4),
`RUN_HISTORY` (34 runs; #128, #131, #129, #97, #140, #133 first), synthetic mV payloads per block.

**Copy** — header subtitle "build here · open a block to tune it"; badges cached / stale / new / running / failed /
invalid / on cluster / paused; "last run shown · stale"; "terminal SpanSet → detection template"; "Chain is invalid ·
fix the red junction · validation runs on every edit"; "No result · run #134 failed at 04 · nothing was written to
detections"; "Not computed here · ≈ 6.4 h on this machine"; "Result found in ./PROFILES · 1.9 GB · 14:31".

## analyse.block

**Regions (shared shell)** — toolbar (`‹ full chain`, name chip, source chip, surrogate / null chip, estimate,
Save template, primary Re-run); chain ribbon (every block clickable, badge + signature, `+ stage`); process card;
parameters card; null / downstream / next cards; footer (unapplied changes, Revert to recommended, primary action).

**Per template** — 01 Baseline (stacked / overlay / difference, edge zones, variance tiles, Try other windows,
What this change does downstream); 02 Noise floor (slope histogram linear / log with cut lines, estimate card,
estimator / cut k / scope / exclude / floor source, σ stability, recording-floor comparison, output strip);
03 Encoding (signal + PAA, slope + draggable cutlines, quantised k5 + dSAX k3 strips, alphabet / split / segment /
same_fraction / noise floor / edges, tiles, plain-English readout, null sweep bars with click-to-set); 04 Detection
(detections in context with dropped boxes and colour-by, raw → kept breakdown, parameters with recommended markers,
kept/surrogate/vs chance tiles, kept detection cards ≤ 10 with sort, Save as a detection template form, hand-offs);
Matrix profile (signal with m to scale, distance profile, profile with p5/p95, value histogram vs surrogate, m vs
null bars, parameters, top locations, cost + HPC); Threshold to spans (live: draggable threshold; demo: scores with
cut, scores over null, spans vs cut, spans table, output, next); Model stage (windows scored per class, model card,
scores vs null, top windows, parameters, output, next).

**Fixtures** — block fixtures in `fixtures/analyse.ts` (`BLOCK_FIXTURES`), all mV traces synthetic and shared-y.

## analyse.glyphs

**Regions** — title + caption, colour key legend, four groups (preprocess · encode · scores & detect · interrogate ·
windows · cluster · model) of cards: 272 × 96 glyph, 44 × 26 glyph, name, signature. Clicking a card opens a detail
drawer (sizes side by side, registry name, where it is used). Copy per frame 6b.

## Kit needs

- None blocking. Requests (if any) in `webui/pages/requests/analyse.md`.
