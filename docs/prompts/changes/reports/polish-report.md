WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\polish
BRANCH: changes/polish

# polish-pass — report

## In plain words (for the researcher)

Think of each page as a shop window. Before, every item had a small grey label explaining how it was made, so the
eye could not find the price tags. This pass keeps the price tags (the numbers, the plots, the buttons) and puts the
"how it was made" labels one click away, behind an ⓘ or a closed "about …" strip. It also colours every button by what
it does (green for the one next step, blue for anything else you can do, red for removing) and takes the yellow ⚠
off notes that ask nothing of you. Nothing was deleted and no number, route or behaviour changed.

## Assumed (the researcher was away; each a defensible choice)

- **Order.** Discovery › Runs last (the manager's override); the rest in the prompt's order. Every page in the order
  is done, one commit each, plus the merge of `changes/coverage` before Runs.
- **What counts as "grey".** `.muted`, the Library's `.lib-cap` / `.lib-muted-label`, settings `.s-row-caption`.
  Data shown under a title (where, when, how many, a distance) is not a caption: it moved to the new `.k-meta`
  (kit) / `.lib-meta` (library) class — text-2, still small and mono — rather than behind an ⓘ.
- **About keeps its body in the DOM** (`hidden` when closed), so a `data-testid` moved into it still satisfies a
  smoke `expect`; nothing a smoke state `wait_for`s (which needs visibility) was moved into one — those stayed visible
  (e.g. `judged-rule` now wraps the ⓘ that holds its text; `xc-flag-line`, `view-by-store`, `preview-tree-note`).
- **Settings captions.** A literal `caption="…"` on a `<Row>` is an explanation fixed in the source → `tip` (behind
  the label's ⓘ). A computed `caption={…}` (a size, a date, an error, a count) is live state → stays on the face. 65
  rows moved mechanically by that rule.
- **Buttons.** Every kit `Button` with no variant became `primary`, or `danger` when it removes/discards/cancels a
  run; Cancel / Close / Dismiss in a modal stay the kit default (dismissal, not an action). The page's one typical next
  step became `next` (green) where it was obvious (send unjudged to Review on a family, Insert and open settings,
  Open <channel> on the home page, Add and run, Keep blind).
- **⚠.** Kept only where the researcher must act or a number is unreliable (failures, held-out switches, undeclared
  units, a sharkfin exemplar's read-out, the cluster route). Notes about a default, an exclusion or a consequence
  became an ⓘ (shared-ground pair, "applying regroups the whole catalogue", the illustrative training chain).
- **Demo chip (rule 5).** Jobs has none. Models › Registry and the Training pages genuinely read fixtures
  (`getRegistry = demo(...)`), and there is no `corpus.dataset_name` in the client; removing the chip there would make
  a fixture page look live, so it stays (see "left").
- **The add-block pop-up's one-line purpose** is the description's first sentence (`splitPurpose`, ≥ 20 characters,
  up to the first ". " or "; "); the rest goes into "About this block".

## Kit primitives added (append-only)

- `kit/About.tsx` — `<About label="about …" testid>…</About>`: an "ⓘ label ⌄" toggle (muted blue) over a tinted
  text-2 strip, closed by default; body stays in the DOM while closed. `export { About, type AboutProps }` appended
  to `kit/index.ts`; `.k-about*` appended to `kit.css`.
- `.k-meta` (kit.css): text-2 for data under a title. Library adds `.lib-meta` / `.lib-key` (library.css).
- `settings/chrome.tsx` `Row` gains `tip` (merged into the label's ⓘ with `info`).

## Smoke states

Count checks use Playwright's `:nth-match(<selector>, N+1)` inside `expect_absent` — "a (N+1)th grey node must not
exist" — so `webui/smoke.py` is **unchanged**. Discovery states sort before `zzzzzzzzzzz_a2_p4_seed.json`
(`tests/test_webui_seed_on_demand_client.py` passes, 16/16).

`webui/smoke_pages/zzzzzzzzzzz_polish.json` (13):

| State | Page | Must show |
|---|---|---|
| polish-family-grey-at-most-20 | library/family/F-03 (g-05) | ≤ 20 grey nodes in `family-view`; no `lib-amber-btn`; `judged-rule`, `member-scale-note` present |
| polish-block-params-one-grey-line | analyse/block/1 | ≤ 1 `.muted` in `params-panel`, none in `null-card`; null card has a chip; Save template `.primary`, Delete block `.danger` |
| polish-add-block-detail-is-name-purpose-io-params | analyse/chain?insert=1 | `modal-purpose`, `modal-signature`, About toggle closed, About body not visible; ≤ 1 `.muted` in the detail; Insert `.primary`, Insert-and-open `.next` |
| polish-inspector-grey-at-most-24 | review/queue/2/100 | ≤ 24 `.muted` in `inspector`; Other channels `.primary` |
| polish-cross-channel-grey-at-most-4 | explore/cross-channel/4 | ≤ 4 `.muted` in the stack header + Take-it-further; `cross-strip-caption` holds an ⓘ |
| polish-signal-no-grey-buttons | explore/signal/4 | Send motif `.primary` (no count: the drawer's table makes one unreliable) |
| polish-atlas-rail-grey-at-most-4 | library/atlas (g-05) | ≤ 4 grey nodes in `atlas-rail`; Interrogate `.primary` |
| polish-grouping-apply-note-is-info | library/grouping?from=atlas | ≤ 6 grey nodes in `ge-params`; Compute preview `.primary`; no ⚠ icon in `apply-clears-scope` |
| polish-settings-row-captions-only-live | settings/analysis-defaults | ≤ 3 `.s-row-caption`; a row ⓘ present |
| polish-settings-display-no-row-captions | settings/display | no `.s-row-caption` |
| polish-jobs-inbox-button-blue-no-demo-chip | jobs | `open-inbox` `.primary`; no `demo-chip` |
| polish-corpus-open-channel-green | explore/corpus | Open `.next`, Cross-channel `.primary`; ≤ 3 `.muted` in the page |
| polish-reports-no-grey-sentence-on-the-toolbar | reports | no `.muted` beside Reload |

`webui/smoke_pages/zzzzzzzzzzz_a1_polish_discovery.json` (2):

| State | Page | Must show |
|---|---|---|
| polish-seed-steps-grey-at-most-12 | discovery/seed?step=1 | ≤ 12 `.muted` in the step column; `seed-card` |
| polish-runs-actions-coloured | discovery/runs | every run row's meta is `.k-meta`, none `.muted` |

The bounds are estimates from the source (no DATA in a worktree, no browser walk): if one fails on the real
database, the number on the page is the evidence — raise the bound only after looking at what the extra grey is.

## What each page should look like (no browser smoke was run)

- **Family:** summary card = plot, legend, numbers (judged has an ⓘ holding the resolver rule), a closed "how
  coherence is measured"; green *Send N to Review as a queue*; blue/red actions; member cards with dark meta.
- **Add-block pop-up:** right panel = name, one sentence, signature (+ side inputs), parameters, a closed "About this
  block"; footer *+ Insert* blue, *→ Insert and open settings* green.
- **Settings:** rows are label ⓘ · control, with a caption only where something live is printed.
- **Everywhere:** no grey (white, bordered) button for an available action, except Cancel/Close.

## Per page (worst first, as committed)

### Library › Family (`library/FamilyPage.tsx`, `FamilyOverlay.tsx`, `CrossChannel.tsx`, `Edges.tsx`)

**Summary:** the family reads as plot, numbers, members and actions; how each number is made is one click away
(an ⓘ or a closed "about" strip). Grey nodes in the main view: roughly 40 → at most 20 (smoke bound).

| Found | What it was | Done |
|---|---|---|
| unjudged banner caption "a family of unjudged members is a proposal, not a finding" | grey (amber-tinted) line | moved behind ⓘ "Why judge them" |
| *Send N to Review as a queue* / *Open in Review* | amber `lib-amber-btn` (a yellow button) | recoloured `next` (green): the page's one next step |
| summary `summary-trace-note` "measured · centred · nothing normalised · peak" | 10 px grey line | behind ⓘ on the plot's axis row; the *unit undeclared* variant stays on the face, amber (the plot is not in mV) |
| `family-unit-note` | 10 px amber | kept on the face (a reason the plot is not in mV); inline 10 px removed |
| exemplar / medoid legend row | grey 10.5 px | restyled `lib-meta` (data, text-2) |
| `family-null-context` (s of quiet background · borrowed · % overlap) | grey | restyled `lib-meta` (numbers) |
| coherence labels "coherence σ²", "eq. 17 (the verdict)" | grey 10.5 px inline | restyled `lib-key` (a label for a number) |
| `coherence-context`, `coherence-extra`, "the rule" `<details>` | three 10 px grey lines | into one closed **About "how coherence is measured"** (`coherence-about`) |
| `coherence-caveat` | 10 px grey / amber | on the face only when the family is judged noise-like (amber: the number is unreliable); otherwise in the About |
| `judged-rule` "judged N of M by the divergence resolver — … not exact span equality" | grey line | moved into the ⓘ beside *judged* in the key-value list; `judged-rule` now wraps that ⓘ (still visible, so the `zzzz_ae` wait_for holds) |
| "edges N" beside *Seed search* | grey | moved into the key-value list as `edges` (`family-edges`) |
| *Seed search in Discovery*, *Export entry*, *Edit grouping…*, *‹ back to atlas*, *Make exemplar*, *Redraw in Explore*, batch *Send to Review* / *Add tag* / *Export* | grey (default) buttons | `primary` (muted blue) |
| batch *Remove from family*, pick-card *Remove from family* | grey | `danger` (red outline) |
| pick card *Send to Review* / *Open in Explore* | grey | `primary` |
| `overlay-pick-hint` "click a trace to pick it" | 10 px grey | deleted from the face: it repeated the overlay ⓘ's first sentence, which keeps it |
| *hand edits only* toggle | grey when off | `link` (blue) when off, purple when on |
| member card "channel · onset h" | grey | `lib-meta` (data) |
| removed-strip rows, "+ N more" | grey, 11 px inline | `lib-meta`; inline sizes removed |
| batch hint "tick members … · send to Review, tag, assign class, remove, export" | grey line | "tick members to act on several" + ⓘ with the list |
| rail axis + `rail-member-note` | 10 px grey | note behind ⓘ on the axis row; "no waveform" reason stays on the face |
| rail `revisions-none` | `muted` | text-2 (it is the value of the row) |
| rail "edges · distance, value, cut, scale, run and recipe" | grey 11 px | "edges" + ⓘ |
| rail "class · waits for the Review-behaviour prompt…" (`rail-class-waits`) | grey sentence | a `waits` chip, the sentence on hover (rule 2: a "not settled yet" note is a chip) |
| Cross-channel `cross-channel-chance-rule`, `cross-channel-null` | two grey lines | into a closed **About "how this is classified"** (testids kept, in the DOM) |
| Cross-channel *Classify across channels*, *Send N suspected artifacts*, *Open in Review* | grey | `primary` |
| `xc-flag-line` | grey | `lib-meta` (counts; still visible — `zzzz_ad` waits for it) |
| Scale read-out `scale-readout-caveat` with ⚠ | always a ⚠ | ⚠ (amber) only for a sharkfin exemplar; otherwise inside a closed About "exemplar morphology" |
| Scale read-out run picker | grey buttons | `link` / `subtle` (picked) |
| Scale read-out run note | grey line under the table | ⓘ beside the run's label |
| *Seed search* (read-out) | grey | `primary` |
| Matched-member card lines | grey | `lib-meta` |
| inline `fontSize: 10` (×8), `fontSize: 10.5`/`11` duplicates of the class | inline | removed |

Kept, with reason: the overlay caption "medoid … · the N members on this page" (the card's one caption);
`member-scale-note` (the grid's one caption, asserted by `library.json`); the *sort* / *member pairs* / *recurrence*
labels (labels of controls/counts); the coherence "not scored: <reason>" line (says why there is no number).
Not touched: `SequenceFamilyPage.tsx` (the sequence variant of this route) — listed under "left".

### Analyse › block pages and the add-block pop-up (`analyse/InsertStageModal.tsx`, `BlockPage.tsx`, `ParamsPanel.tsx`, `views/registry.tsx`, `views/GroupingView.tsx`, `analyse.css`)

**Summary:** the add-block pop-up's right side is now name · one-line purpose · inputs → outputs · parameters, with
"About this block" (closed) holding the rest; the block page's toolbar and parameter card lost their grey and grey buttons.

| Found | What it was | Done |
|---|---|---|
| pop-up detail: the whole `description` paragraph | a wall of text on the right | first sentence on the face (`modal-purpose`); the rest in **About this block** (`modal-about`, closed) — `splitPurpose()` in the modal file |
| pop-up detail: glyph, est. cost / null / side-inputs tiles | always shown | inside About this block; side inputs also printed on the inputs → outputs line (`modal-signature`) |
| pop-up detail "defaults" heading | label | renamed **parameters** (rule 6 names it so; the values are the defaults) |
| pop-up detail "⏱ NN goes stale · 00–NN stay cached" | amber line | into About (a cache note, not an action; the ribbon above already says "inserting makes NN stale") |
| pop-up detail "⚠ span exceeds the local ceiling → HPC" | amber ⚠ | kept: the run will route to the cluster (the researcher must know) |
| card chip "null · not declared" | the same grey chip on every card | removed from the cards; its sentence is in About this block |
| card chip font 10 px | CSS | 10.5 px |
| card "⚠ known broken" | ⚠ | kept: the block does not work |
| footer "N blocks in the registry · a new technique is one adapter file" | grey | count kept; the second half behind ⓘ |
| *+ Insert* | grey `btn` | `primary`; disabled says why on hover |
| *→ Insert and open settings* | primary | `next` (green): the one typical next step |
| *sort fits first* toggle | grey `btn` | `btn ghost` (blue text) |
| block toolbar *Save template* | grey | `primary` |
| block toolbar *Delete block* | grey | `danger` |
| block footer *Revert to defaults* | grey | `primary` |
| empty state *Pick the example span…*, `OpenChain` (registry) | grey | `primary` |
| run veil note "the result refreshes here … before the next step" | 10 px grey line | behind ⓘ on the progress text; CSS 10 → 10.5 px |
| null card's dashed box "drawn per chain run — use the toolbar's surrogate toggle" | big grey box | a grey chip on the heading row |
| parameter rows "= default · recommended: not computed" | the same tail on every row | tail removed (the head's ⓘ "Recommended values" says it once) |
| parameter rows "default X" (changed value) | muted-2 | text-2 (it is the value to go back to) |
| band presets "Settings › Analysis defaults" | grey line | removed: the presets' own ⓘ says where the list comes from |
| band presets error | grey | red (a failure) |
| Grouping view `family-note` lines | grey list under the table | into About "notes on this table (N)"; the amber `family-warning` lines stay on the face |

Kept, with reason: the block card's "01" index (`mono muted`, an identifier); "N declared" beside *Parameters* (the
card's one caption); the footer's status sentence (the footer's one caption); the readout's `⚠` rows (the server marks
them `warn`); per-view empty/state lines in `views/*` ("no result for this stage yet", "nothing to draw" …) — they are
the empty states. Not swept: the remaining `views/*` captions (ShapeViews, EncodingView, IntervalTimeline, TreePage)
— listed under "left".

### Discovery › Seed (`discovery/SeedPage.tsx`, `discovery/seed/KeepCard.tsx`)

**Summary:** the four-step page already had one card open at a time (seed-search); this pass took the repeated
captions off it and coloured its remaining grey buttons. The step column shows at most 12 grey nodes (smoke bound).

| Found | What it was | Done |
|---|---|---|
| draft run row: amber `draft` badge + amber line "draft · not kept yet" | the same word twice, in warning colour | line moved onto the badge's hover; seed/role meta → `k-meta` |
| seed card head "type Signal span" | grey caption beside the ⓘ | moved into the ⓘ's first sentence ("Type: a Signal span.") |
| seed thumbnail "N samples · s" | grey | `k-meta` (data) |
| picker rows "recording · channel · h · samples · family" | grey per row | `k-meta` (data) |
| empty picker *Select a span in Explore* | grey button | `primary` |
| cut card *choose a cut anyway · d ≤ x* | grey button | `primary` |
| cut card `cut-rule` "the rule the recommended cut is read off" | grey line under the histogram | closed About "how the cut is read" (the histogram's legend still prints the rule) |
| search progress *Cancel preview* | grey | `danger` |
| match cards "d x" and "channel · h · scale" | grey | `k-meta` |
| selected match line | grey | `k-meta` |
| keep card *Import HPC result* | grey | `primary` |
| keep card run *Cancel* | grey | `danger` |
| keep card `run-estimate` | grey | `k-meta` (the estimate is a number) |
| keep card `save-as-template-line` "saves the recipe … never the matches" | grey sentence | behind ⓘ beside *Save as template* (`save-as-template-line` wraps the ⓘ) |
| held-out `Callout` (amber) | warning | kept: the bridge switched the seed (the researcher must know) |
| `seed-over-limit`, `apply-no-cut` (amber) | warning lines | kept: the run will go to the cluster / keeps every match |

Kept, with reason: the keep card's lede (its one caption); the advanced section's caption (its one caption); the step
strip's "pick an exemplar first" (a disabled step's reason); progress messages and ETA (live state); the
"no cut: none of the N matches…" note (says what the cards below are). Shared Discovery chrome (scope card, toolbar,
Runs card) is polished with Discovery › Runs.

### Review › Inspector (`review/parts.tsx`, `Shell.tsx`, `review.css`, `BlindTest.tsx`, `SuspectedArtifact.tsx`)

**Summary:** Review was the cleanest page already (AP swept it); this pass coloured its grey buttons, made family data
read as data and lifted every sub-10.5 px size. At most 24 grey nodes in the inspector (smoke bound) — they are the
labels of its controls (padding, class, tags, note, you, model) and one caption per evidence section.

| Found | What it was | Done |
|---|---|---|
| *Other channels* (closed) | grey | `primary` (open: `subtle`) |
| *Edit span in Explore*, tag *Add*, *Undo promotion*, *Shortcuts* | grey | `primary` |
| unblind modal *Show machine opinion* / *Keep blind* | grey / blue | `primary` / `next` (keeping the queue blind is the recommended path) |
| family rows: family name, "N members", "d x · N members" | grey | `k-meta` (data) |
| `review.css` font-size 10 px (×8: progress pace, left count, thumb more, queue row, blind badge, ticks, status chip, stage) | under 10.5 px | 10.5 px |
| `SuspectedArtifact` axis text 9 px, `BlindTest` axis text 10 px (inline) | under 10.5 px | 10.5 px |
| "auto-advance paused until you confirm" amber `Callout` | amber | kept: the researcher must act (Enter confirms) — its icon is ⏸, not ⚠ |
| Evidence section asides "nearest by shape, not a verdict", "not blinded" | grey | kept: each is its section's one caption |

Kept, with reason: control labels (padding, class, tags, note, family, you, model); "not computed" /
"no verdict yet in this queue" (empty states); the artifact factor labels (labels of numbers).

### Explore › Signal and Cross-channel (`explore/CrossChannelPage.tsx`, `SignalDrawer.tsx`, `MotifView.tsx`, `SpanActions.tsx`, `explore.css`)

**Summary:** Signal had no grey caption left (AP); its grey buttons are coloured. Cross-channel lost its two long grey
sentences (into ⓘ) and its non-actionable ⚠; at most 4 grey nodes in its header + action card (smoke bound).

| Found | What it was | Done |
|---|---|---|
| Signal: drawer *Export CSV* / *Export JSON*, *Add tag*, *Stage in Analyse*, *Send to Analyse*, *Clear filters* (×2) | grey | `primary` |
| Signal: *Send motif to Analyse* | grey | `primary` |
| Signal: *Save span*, strip *Zoom* | grey | `primary` |
| Signal: `unit-undeclared` amber ⚠ Callout | ⚠ | kept: the numbers are not in mV (unreliable as drawn) |
| Cross-channel overlay head: "Each channel drawn about its own mean … drag across the plot for a box to act on." | long grey sentence | moved into the Overlay ⓘ (its first sentence) |
| Cross-channel `cross-strip-caption` "This window on the N channels shown: send … or mark …" | grey sentence | **This window** + ⓘ holding the sentence (`cross-strip-caption` wraps them) |
| Cross-channel `shared-ground-warning` ⚠ "… known shared-ground pair — excluded from recurrence counts" | amber ⚠ | ⓘ icon (muted): a note about what is left out of a count, not a call to act |
| Cross-channel *edge window ✕*, *Open X in Signal*, empty-state *pick channels* | grey | `primary` |
| channel picker "N of M · cap" | grey | `k-meta` (data) |
| `scale-note`, `detrend-note` | grey header notes | kept: a scale and a measurement basis printed beside the plot they describe (smoke asserts both) |
| `nothing-to-align` | grey | kept (says why *align by lag* moved nothing) |
| ActionRow `-why` lines | grey | kept: a disabled card says why on the page (rule 3) |
| `window-sel-error`, `ov-det-error` ⚠ | ⚠ | kept: failures |

Kept, with reason: "Open design questions" count (the disclosure's caption).

### Library › Atlas and Grouping (`library/AtlasPage.tsx`, `chrome.tsx`, `GroupingPage.tsx`)

**Summary:** every grey button in the Library chrome, the atlas rails and the grouping editor is coloured; card counts
and legends read as data; the method description and two "how" sentences fold away; the "applying regroups" note is
an ⓘ, not a ⚠. Atlas rail: at most 4 grey nodes; grouping parameters: at most 6 (smoke bounds).

| Found | What it was | Done |
|---|---|---|
| Library toolbar *Find by shape*, *Import*, *Export*, *Edit grouping* | grey | `primary` |
| grouping-bar *Open the current grouping instead* (×2), *Retry*, view-bar *Apply*, *Send omitted to Review* | grey | `primary` |
| atlas rail *Seed search*, *Interrogate in Analyse*, *Send N unjudged to Review* (motif and sequence rails) | grey | `primary` (*Open all members* stays green) |
| grouping editor *Back to settings*, *Compute preview*, *Save*, cheaper-setting buttons, *Build the tree* | grey | `primary` |
| grouping editor *Cancel* (a running regroup) | grey | `danger` |
| atlas `scope-caption` "N families · N members in every recording" | grey 11 px | `lib-meta` (counts) |
| atlas rail "N members · in scope · hand edits", axis 0…s, exemplar/medoid legend, `rail-members-not-drawn` (both rails) | grey, inline 10.5/11 px | `lib-meta`; inline sizes removed |
| atlas "composition" label | grey 10.5 px inline | `lib-key` |
| omitted strip labels (text-2 on `lib-cap`) | grey class, inline colour | `lib-meta` |
| omitted card recording line, "d x" | grey | `k-meta` |
| view bar `view-by-store` | grey 11 px | `lib-meta` (counts; still visible — `zzzz_ae` waits for it) |
| view bar `view-rule-line` | grey 11 px inline | kept as the bar's one caption; inline size removed |
| grouping `apply-clears-scope` "applying regroups the whole catalogue and clears the current scope" | amber ⚠ | ⓘ, text-2: a consequence to know, not a call to act |
| grouping tree "Drag the amber line to cut the tree … read from the kept tree." | grey sentence | "drag the amber line to cut" + ⓘ with the sentence |
| grouping `method-description` | grey paragraph | closed About "about this method" (testid kept, in the DOM) |
| grouping "edges at the quantiles; every member falls in a bin" | grey | "quantile edges" + ⓘ |
| grouping "measured range …" | grey | `lib-meta` (a number) |
| grouping "feature" / "clustering" labels | grey 11 px inline | `lib-key` |
| custom basis: clustering scope `Callout` amber with ⓘ icon | amber | grey Callout (a note about the clustering's scope) |
| `no-clusterings` amber Callout | amber | kept: the basis cannot be used until one is registered (act) |
| over-limit ⏳ amber line | amber | kept: the regroup goes to the cluster |

Kept, with reason: histogram axis labels; the grouping's "no tree / no distribution" grey cards (they are the empty
states of those plots); job progress text.

### Settings pages (`settings/chrome.tsx` `Row`, every `settings/*Page.tsx`, `settings.css`)

**Summary:** the biggest grey-text source on the site was the right-hand consequence caption on every settings row
(about 90). `Row` gained a `tip` prop that sits behind the label's ⓘ (merged with `info`); every LITERAL caption
(`caption="…"`, an explanation fixed in the source) became `tip="…"` — 65 rows across 12 pages, mechanically, by
`<Row>` tag. Computed captions (`caption={…}`: a cache size, a stored date, a calibration, an error, a count) stay on
the face. Every grey button is coloured.

| Found | What it was | Done |
|---|---|---|
| literal row captions: Analysis defaults 18, Display 10, Models registration 10, Library groupings 6, Storage 6, Compute/HPC 5, Review queues 4, Nulls 3, Export 2 (+4 via `ChipRow`), About 1 | grey 10.5 px line per row | behind the label's ⓘ (`Row tip`) |
| computed row captions (cache GB + Clear, rose reference stored/date, fallback-with-count, calibration date, cores, workdir error, …) | grey | kept on the face: live state |
| `.s-sub` 10 px | under 10.5 px | 10.5 px |
| *Copy diagnostics*, *Export CSV*, *Show all*, *Add event*, *Run benchmark*, *Add cluster*, *Add profile*, *Import a recording…*, *Declare*, *Check*, *Open Vocabulary*, *Back up now*, *Restore…*, *Rescan*, *Add class*, *Add tag*, *Retry*, *Open Datasets*, *Recompute* (rose), *Stay* | grey | `primary` |
| *Keep the old binding* (keyboard conflict) | grey | `primary` (the safe choice) |
| *Clear cache* | grey | `danger` (it deletes the step cache) |
| *Discard* (unsaved changes) | grey | `danger` |
| Datasets `recording-warnings` ⚠ Callout, Storage `low-disk` ⚠ Callout | ⚠ | kept: the data is unreliable / the disk is nearly full (act) |
| Datasets SubHead captions (Identity, Read from the data, Recording conditions) | grey | kept: each is its section's one caption |
| page ledes (`page-lede`) | grey | kept: the page's one caption |
| table secondary columns (file names, paths, producer, evaluated on, added) | grey cells | kept: a table's secondary column (rule 4 "one mono style for identifiers") |

Cancel / Close in modals stay the kit default (dismissal, not an action).

### Models, Training, Jobs (`models/*.tsx`, `training/*.tsx`, `jobs/*.tsx`)

**Summary:** every grey button on the three workspaces is coloured (about 45); B.2's fixed training settings and
"how results return" sit behind ⓘ; the "illustrative" chip lost its ⚠. Jobs carries no demo chip (smoke-pinned).

| Found | What it was | Done |
|---|---|---|
| grey buttons — Models: B.2 *against a blind human*, score reference, prev/next, *Open Analyse › Chain*, *Create SLURM script*, Compare prev/next, *Settings › Datasets*, *Propose cuts*, Registry *Restore*, *Why*, *Open sample*, *Save draft*, *Retry*, *Open Launch*; Jobs: *Manifest inbox · import result*, *Models › Launch*, *Retry*; Training: *Send to Review* (×4), *Export run*, *Open 05 and rebind*, *Trial job*, unlock/lock criterion, *Resample*, *Save grouping*, *Lock*, drop label-derived, *Open in 04*, *Create SLURM*, *Upload matrix*, *Merge in 03*, *Copy script*, *Download trial job*, *Back*, *Save window set*, toolbar *History* / *Import* / *Save template* / *Retry* | grey (kit default) | `primary` |
| Registry *Retire* | grey | `danger` |
| `HpcScript` *copy the script*, Training cluster *Open Analyse › Chain* | grey `btn sm` | `btn sm primary` |
| B.2 model chooser (Random forest / CNN) unselected | grey `btn sm` | `btn sm ghost` (blue text; the selected one stays primary) |
| B.2 forest "class weight · seed" | grey line | ⓘ "Fixed settings" beside *trees* |
| B.2 CNN "batch · Adam lr · cosine · … · refit on every training window" | grey line | ⓘ "Fixed settings" beside *epochs* |
| B.2 `b2-cnn-returns` | grey paragraph under the buttons | "how results return" + ⓘ (testid kept on the row) |
| Training Chain `illustrative-chip` with ⚠ | amber ⚠ chip | amber chip with ⓘ icon (it says the page is illustrative; nothing to act on) |
| Training red Callouts (run stopped, junction does not type-check, leaks P12), amber label-derived / encoder new-version / manual-labels notes, "too small to train" flags | ⚠ | kept: each is a failure or a number the researcher must not trust |
| **demo chip** — Jobs | none on a live page | kept none; smoke state pins it |
| **demo chip** — Models › Registry, Training (analyse/training/*) | "demo data" | **kept**: both read fixtures (`getRegistry = demo(REGISTRY_MODELS)`, `getTrainingChain` …); there is no `corpus.dataset_name` in the client to label them from, and removing the chip from a fixture page would make it lie (CLAUDE.md: "a surface that … lies"). Wiring them live is its own prompt — see "left" |

Cancel / Close / Dismiss stay the kit default (dismissal).

### Corpus (home) (`explore/CorpusPage.tsx`)

**Summary:** the home page was already lean (AP); its one next step is now green and its other actions blue.

| Found | What it was | Done |
|---|---|---|
| *Open <channel>* (`open-channel`) | primary (blue) | `next` (green): the page's one typical next step on Explore → Analyse → Review |
| *Cross-channel* (`cross-channel-from`) | grey | `primary` |
| empty map *Show both* | grey | `primary` |
| "channel" axis label | inline 10 px | 10.5 px |
| "loading…", `divergence-nc` "not comparable" | grey | kept: a loading state and a cell that is not a number |
| matrix label / divergence scope (`.meta`) | text-2 | kept: data |

### Reports (`reports/index.tsx`)

**Summary:** Reports (new this wave) was already all blue buttons; its two grey sentences moved into the ⓘ beside them.

| Found | What it was | Done |
|---|---|---|
| report toolbar "The figures and tables behind this run, drawn by the server from the live database each time you open it." | grey sentence | first paragraph of the existing ⓘ "What this report is" |
| saved list "A snapshot is a report frozen on disk: … ready to paste into a chapter." | grey sentence | a **Snapshots** label + first paragraph of the existing ⓘ "Where reports come from" |
| row notes (`r.note`) | grey under the title | kept: the snapshot's own note (data) |
| buttons | all `primary` already | kept |
| `reports-load-failed` red ⚠ Callout, unknown-route ⚠ empty state | ⚠ | kept: failures |

### Discovery › Runs (`discovery/RunsPage.tsx`, `chrome.tsx`, `AddTemplateModal.tsx`, `AddMatches.tsx`) — polished on the merged coverage shape (merge `49e5410`)

**Summary:** polished last, after merging `changes/coverage` (7e982b9; one conflict in `kit/index.ts`, two
append-only exports — both kept). Every grey action is coloured, the run row's detail reads as data, the extend error
is red, and one legend sentence moved behind ⓘ. The coverage strip, "Run on the missing N", the "not run here" row
and the verdict gauge are untouched in behaviour.

| Found | What it was | Done |
|---|---|---|
| toolbar *Run*, *Apply template*, *Seed search*, run filter *Clear*, *Import spans to Analyse*, *Send to Review* (browse) | grey | `primary` |
| *Discard run* | grey | `danger` |
| chrome *Retry*, *History*, adopt-recording, add-channel *all* / *none*, *Preview on a 4 h sample*, *Back to the session's recording*, *Compare* (×2), *Run on the missing N* (coverage), *Import HPC result*, scope apply | grey | `primary` |
| Add-template modal *Add runs*, *Run preview* | grey | `primary` |
| Add-template modal *Add and run* | grey | `next` (green): the modal's one next step |
| Add-matches *Add N matches to …* | grey | `primary` |
| run row detail (`dsc-run-meta`) | grey | `k-meta` (data) |
| run row `extend-error-*` (coverage) | amber line | red: it is a failure, with the server's sentence |
| fires legend "one mark per span · at this scale several may share a pixel" | grey | "one mark per span" + ⓘ |
| `run-missing-callout` (amber ⚠), failed-run red ⚠ Callout, SLURM refused/wall-unverified/warnings Callouts | ⚠ | kept: a link to a run that is not there, failures, and a cluster wall the researcher must check |
| `spans-note` "spans are thinner than a pixel … zoom below 24 h" | note | kept: says what to do to read the plot |
| scores table grey cells (no null run, notes, recall n/a) | grey | kept: a table cell that is not a number |

Cancel / Dismiss stay the kit default.


## What is left

- **`views/*` captions on Analyse block pages** — ShapeViews, EncodingView, IntervalTimeline, TreePage, SignalView
  still carry their AP-era grey lines (mostly empty/state lines and per-view notes). Only `GroupingView`'s notes and
  `registry.tsx`'s `OpenChain` were touched.
- **`SequenceFamilyPage.tsx`** (the sequence variant of the Family route) and the Library's Recurrence, Window sets,
  Templates and Import pages were not in the order and are not swept.
- **Demo chip on Models › Registry and Training (analyse/training/*)** stays: both read fixtures. Meeting rule 5
  means wiring those reads live (or deciding to remove those pages) — a prompt of its own, not a restyle.
- **Settings table cells** keep grey for secondary columns (paths, producer, evaluated on).
- **Add-template modal** (Discovery) follows the old long-detail layout; rule 6 named only the add-block pop-up — the
  same `About` split would apply to its right pane.
- Wording noted, not changed (per the prompt): the B.2 "Fixed settings" tips reuse the old line verbatim; the
  Family "waits" chip is a new one-word label for the existing class-vocabulary sentence (its hover keeps the
  sentence).

## Gates run

- `tsc -b` before every commit (clean); `vite build` after Seed, after Corpus/Reports and before reporting (built).
- conda: `tests/test_webui_seed_on_demand_client.py` 16 passed.
- webui/.venv, every test that reads client source (16 files: `test_analyse_null_toggle`, `test_block_standard`,
  `test_webui_block_views`, `_cross_page`, `_decompose_payload`, `_header_counts`, `_library`, `_library_tree`,
  `_plot_domain`, `_review`, `_review_axis`, `_seed_on_demand_client`, `_slope_anatomy`, `_template_kind_terminal`,
  `_w2f_ui`, `_w3f_ui`): 448 passed, 3 xpassed (before the coverage merge); after it,
  `test_webui_discovery_coverage.py` + the seed client test: 23 passed.
- No browser smoke (no DATA in a worktree).

## Commits

- f0bf485 polish: Library > Family
- 7bf051a polish: Analyse › block pages (and the add-block pop-up)
- b7848b8 polish: Discovery › Seed
- de3ba76 polish: Review › Inspector
- 9784452 polish: Explore › Signal and Cross-channel
- dc4a45d polish: Library › Atlas and Grouping
- 4ef0352 polish: Settings pages
- cbd7ca6 polish: Models, Training, Jobs
- 2495de4 polish: Corpus (home)
- 597025b polish: Reports
- 49e5410 Merge coverage (7e982b9) — conflict in `kit/index.ts` only (two appended exports; both kept)
- 7a4cb51 polish: Discovery › Runs
- (this report)

## Critic round

**In plain words first.** This pass was meant to tidy the screens without changing what any of them does. The critic
read every changed line against that promise. It does keep it: nothing that counts, saves or navigates was rewired,
and nothing the researcher needs was deleted. Each grey sentence moved behind an ⓘ or into a closed "about …"
strip. One real trap turned up. A closed "about" strip still holds its text in the page, only hidden. So four of the
existing automated checks that look for that text kept passing even though nobody could see it. Those checks now
open the strip first and require the text to be on screen. **Verdict: ready to merge after the manager's gate**
(the browser walk could not run here).

### Findings

| # | Severity | Where | Evidence | Status |
|---|---|---|---|---|
| 1 | should-fix | `webui/smoke_pages/zzzz_ad_suspected_artifact.json:2`, `zzz_w_cross_channel.json:2`, `library_edges.json:2`, `library.json:59` | `About` keeps its body in the DOM under `hidden`, and smoke `expect` is `locator.count()`. So `cross-channel-chance-rule`, `cross-channel-null`, `scale-readout-caveat` (F-173, a trough exemplar, so it falls in the About) and `method-description` passed while invisible. Those states' `_why` lines claim the text is shown. | FIXED (61115b8): each state opens the About with `click_if` on `<id>-toggle[aria-expanded="false"]` (so a state that inherits an open About does not close it) and expects the node `:visible`. `Edges.tsx` and `GroupingPage.tsx` give their Abouts test ids (`scale-readout-about`, `method-about`) so the toggle can be found. |
| 2 | minor | `library/FamilyPage.tsx` (the overlay pick hint) | `data-testid="overlay-pick-hint"` was deleted: its text repeated the ⓘ's first sentence. `zzzzzzzzzzz_family_actions.json:6` asserts it ABSENT after a pick, and that assertion is now vacuous because the hint is always absent. No state needs it present. | NOT FIXED (a defensible deletion under rule 1; the pick itself is still asserted by that state's other expects) |
| 3 | minor | `analyse/InsertStageModal.tsx` (detail panel) | The amber "⏱ NN goes stale · 00–NN stay cached" note moved into the closed "About this block" and lost its amber colour. It tells you a cost, but it is not an unreliable number and needs no action. Rule 2 allows this. The over-the-local-ceiling ⚠ (→ HPC) and the cards' "known broken" ⚠ stay on the face. | NOT FIXED (defensible; flag for the researcher's eye) |
| 4 | nit | `analyse/InsertStageModal.tsx` sort button | The sort toggle used to show its state through its style (ghost when off). Now it is always ghost, and only the label ("fits first" / "by registry") shows the state. | NOT FIXED |
| 5 | note | test ids that now wrap an `InfoTip` | `save-as-template-line`, `judged-rule`, `summary-trace-note` (unit declared), `rail-member-note` (with a waveform), `b2-cnn-returns`, `cross-strip-caption`. An `InfoTip`'s text is NOT in the DOM until it is opened (it renders through `Popover`). The wrapper ids still exist, and existing states only check presence (`zzzzzzzzzzz_a1_seed_search.json:47`, and `zzzz_ae_library_view.json:24-25`, which `wait_for`s `judged-rule`; the wrapper span holds a visible ⓘ button, so it passes). No state reads their text. | no change needed |

**Warnings that were demoted (rule 2), each checked.** These were checked for whether any of them is an
unreliable-number warning:
- Explore cross-channel shared-ground ⚠→ⓘ: the pair is excluded from the counts, so the numbers are already
  corrected.
- Grouping "applying regroups the whole catalogue" ⚠→ⓘ: a consequence of pressing Apply.
- Custom-clustering scope Callout amber→grey.
- Training "illustrative · out of scope" chip ⚠→ⓘ.
- Family "a proposal, not a finding" moved into an ⓘ. The bold amber "N of M members have never been judged" line
  and the green send stay.

None of these is an unreliable-number warning. The genuine ones stay on the face:
- the coherence caveat, when the family is judged no more coherent than noise;
- "unit undeclared · not drawn in mV" and the family unit note;
- the sharkfin scale-readout caveat (a non-sharkfin caveat goes into an About);
- the label-leak callouts in Training;
- the "arms train on different windows" callout;
- every held-out / lock note (untouched).

**Behaviour (rule "moves and restyles").** The client diff (df58f85..HEAD minus the coverage merge) holds the
following, and nothing else:
- variant/class changes;
- captions moved into `InfoTip` / `About` / `tip`, with `Row.tip` merged into the label ⓘ alongside `info`;
- text recoloured `.muted`→`.k-meta`/`.lib-meta`;
- one chip;
- sizes raised to 10.5 px;
- `edges N` moved into the summary key-value list;
- the band-preset "Settings › Analysis defaults" pointer deleted. The presets' own `i` title already says it, so
  nothing is lost.

No handler, condition, route, label or number changed. Error paths only got louder: band presets and extend errors
are now red. Disabled buttons keep their reasons, and the pop-up's raw Insert buttons gained a `title`.

**Merge-readiness.** The polish commits touch only `webui/client/src/**`, `webui/smoke_pages/**` and this report. The
coverage merge brings its own server change. `kit/index.ts` and `kit/kit.css` only gain lines. `docs/manual` and
`version.tex` are untouched, and no block description changed (the pop-up splits `description` at display time).
The discovery unit `zzzzzzzzzzz_a1_polish_discovery.json` sorts before `zzzzzzzzzzz_a2_p4_seed.json`.
`zzzzzzzzzzz_polish.json` opens no Discovery page.

**The count bounds, checked by hand for one page.** The block page's `params-panel` has one `.muted` node, the
"N declared" count. `ParamsPanel` adds a `.muted` only for a block with no parameters, so the walk's block 1 stays
at 1. The bound (`:nth-match(..., 2)` absent) is plausible.

### Gates (critic, after 61115b8)

- `tsc -b` clean; `vite build` built (to a scratch outDir, so no served `dist` was rebuilt under a running walk).
- conda: `test_webui_seed_on_demand_client` 16, `test_import_boundaries` 4, `test_analyse_null_toggle` 6,
  `test_block_standard` 222 — all passed.
- venv: `block_views` 11, `cross_page` 21, `decompose_payload` 4, `header_counts` 3, `library` 59 + 3 xpassed,
  `library_tree` 12, `plot_domain` 19, `review` 32, `review_axis` 7, `slope_anatomy` 7, `template_kind_terminal` 3,
  `w2f_ui` 10, `w3f_ui` 16 — all passed (`block_views` / `slope_anatomy` print a logging "I/O operation on closed
  file" at interpreter exit; the summary lines are clean).
- Six smoke manifests parse as JSON. No browser smoke here.
