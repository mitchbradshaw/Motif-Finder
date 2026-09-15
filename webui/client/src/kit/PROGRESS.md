# kit — progress notes

Shared UI kit for the concept pages. Written as the kit is built so a killed run leaves usable work.

## Done
- icons.tsx (Icon + ICONS), hooks.ts (useQueryState/useQueryFlag, usePagedList, copyToClipboard, fmtInt/fmtMv/fmtPct,
  layer stack + useSurfaceDismiss, useAnchoredPosition, useControllable, sampleIndices), portal.tsx (Portal, cx, tid),
  kit.css (all component styles, `k-` prefix), display.tsx (Tooltip, DisabledReason, Button, IconButton, Chip, Badge,
  StatTile/StatRow, KeyValue, EmptyState, ProgressBar, CodeBlock, Callout, Stepper, Checklist, ColourDot, Kbd).

- (after the 05:00 crash) surfaces.tsx (Popover, PopoverButton, InfoTip, Modal, Drawer, Menu, Dropdown), nav.tsx (Tabs, Seg,
  Breadcrumb, Pager), layout.tsx (Page, PageTitle, Toolbar, Spacer, DividerV, Card, SectionCard, SplitPane, Rail, SideNav),
  Table.tsx, forms.tsx (Field, TextField, NumberField, SelectField, Toggle, Checkbox, Slider, RangeSlider, RadioCards),
  glyphs.tsx (re-export of analyse/glyphs + BlockGlyph/SourceGlyph/GLYPH_ALIASES), ChainRibbon.tsx, plots.tsx (Trace,
  MiniTrace, LineChart, Histogram, Bars, Scatter, Heatmap, BandStrip, NullBand, SmallMultiples, Legend), index.ts.
  `npx tsc --noEmit -p tsconfig.app.json` exit 0.

- Gallery.tsx (`KitGallery`, route wired by the orchestrator in App.tsx), README.md (builders' API reference).
- Fixed in sim.ts (orchestrator file): `getSim` returned a fresh IDLE object per call → useSyncExternalStore infinite loop
  ("Maximum update depth exceeded") for any idle sim. Now caches the idle state.
- Verified: `npx tsc --noEmit -p tsconfig.app.json` exit 0; Playwright (conda python, 1440×900) against
  http://127.0.0.1:5173/#/kit — 0 console/page errors; modal open/Escape/backdrop/✕ + focus return, popover
  Escape/outside/trigger toggle, drawer Escape/✕, dropdown keyboard select, InfoTip, Tabs → ?tab=, invalid NumberField
  reason, 27 plot SVGs painted, SmallMultiples resample; #/explore/corpus and #/analyse/chain render with no errors.
  Screenshots: webui/screenshots/kit/.

## Left / not built
- Glyph registry was not moved out of analyse/glyphs.tsx (kit re-exports it + alias wrapper); chain-6b glyphs the registry
  lacks (noise floor, symbol smoothing, run-length collapse, alphabet remap, word filter, seeded search, drop detection,
  model stage, resolve-slope, aggregate, sliding windows) fall back to type-signature glyphs.
- No Tab trap inside overlay Drawer (it is non-modal by design); nested modal-in-modal not tested.
