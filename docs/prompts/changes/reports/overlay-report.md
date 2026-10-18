# cross-channel-overlay — report

WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\overlay
BRANCH: changes/overlay (base aa62b52)

## 1. Assumed

- **No bridge change, so no red commit.** `GET /api/cross/{id}` already takes `px` (default 900, clamped 16–4000). The page already reads it at `px=600`: a min/max envelope of about 1,200 points per channel, which is enough for an overlay about 1,000 px wide. The overlay reuses those envelopes and fetches no new ones. Nothing in Python changed, so `explore_routes.py` is untouched and there is no failing-test commit.
- **The overlay draws every channel of the recording, not only the stack's selection.** The stack is capped at 10 channels with the reference pinned, but the researcher asked for CH1 to CH16 on one axis. The stack's selection only decides which channels start **bold** (`?bold=` absent means bold = the stack's channels).
- **The bold set has its own address key, `?bold=`.** It holds channel ids, or `none`. It is separate from `?channels=`, because `?channels=` cannot be empty and always contains the reference.
- **Clicking a name or trace:**
  - a plain click makes that channel the only bold one; clicking it again when it is the only one clears the bold set;
  - shift-click adds or removes one channel.
- **↑/↓ moves the bold channel:**
  - ↑ starts from the topmost bold channel and ↓ from the bottommost; the result is one bold channel;
  - with nothing bold, ↑ starts at the bottom and ↓ at the top;
  - the keys work once the plot has focus (click it first).
- **Align by lag is the page's own `?align=lag`, not a second switch.** In overlay mode the overlay header holds the toggle, and the controls row hides the stacked view's align Seg. One switch serves both views. It is off by default.
- **The shift uses the stack's rule** (`crossModel.lagShift`): the reference never moves, and a lag beyond max lag is not applied. That channel's name then says "past max" in amber.
- **The box is on the reference's clock.**
  - *Send unjudged* and *Mark artifact* use the box as drawn, on the bold channels.
  - *Open in Signal* and *Open in Analyse* add that channel's shift, so the channel opens at the moment that was lined up.
  - The InfoTip says this, and the box caption says "on X's clock" when align is on.
- **Open in Analyse** sends the topmost bold channel over the box. The existing *Take it further* strip still sends the reference over the whole window.
- **Open in Signal:**
  - one bold channel gives a button, "Open CHn in Signal";
  - several give a dropdown, "Open in Signal…", listing the bold channels with their shifts;
  - it sets the app's Explore view to the box (`setExplore`) and then navigates, which is how Signal already picks up its last view.
- **"Box the span" button.** It draws the box over the window's own span. smoke.py has no drag action, and I did not want to edit `smoke.py`. It is also a useful shortcut. Dragging is the main gesture.
- **The window's own span band is drawn once, across the full height of the block**, so it covers every channel.
- **Detections on every channel come from one `/api/channels/{id}/spans` read per channel**, only in overlay mode. They are spans, not envelopes. A failed read shows a warning line (`ov-det-error`), never a silent blank.
- **The detections chip still filters only the stack's reference row.** The overlay draws every detection the bridge returns for each channel.
- **Colour comes from the channel's rank in the recording**, using a fixed 16-colour palette, so a channel keeps its colour when the reference changes. The stacked rows show the same colour as a 3 px bar left of the name. That is the only change to the stacked view's drawing.
- **The box clears when the window changes.**

## 2. In plain words

Cross-channel now has an **overlay** view beside the stacked rows. Every channel of the recording is drawn on one tall plot, one colour each, with CH1 at the top. You click channel names (or the traces) to make some bold; the rest fade into the background. A switch slides each channel left or right by its measured delay, so a wave that travels across the electrodes lines up. Then you drag a box across the plot to send that stretch to Review, mark it as an artifact, zoom into it, or open it in Signal or Analyse.

## 3. Files

- `webui/client/src/explore/Overlay.tsx` (new): the component, its geometry (`overlayGeometry`), `overlayShift`, `channelColour`/`CHANNEL_PALETTE`, `fmtShift`, `OVERLAY_NAME_W`.
- `webui/client/src/explore/CrossChannelPage.tsx`:
  - adds the `view-seg` (stacked · overlay) and the `?view=` and `?bold=` keys;
  - in overlay mode, hides the y dropdown, the stacked align Seg, the scale note and the lag/r/bin column heads;
  - adds the overlay block with its header, axis, box caption and action strip;
  - adds the per-channel detections read and the colour bar on the stacked row names.
  - The detrend Seg and the existing *Take it further* strip are unchanged.
- `webui/client/src/explore/explore.css`: an appended `.ex-ov*` block.
- `webui/smoke_pages/zzzzzzzzzzz_overlay.json` (new): 5 states.
- Not touched: `api/explore.ts` (nothing to add), `webui/server/explore_routes.py`, `tests/`, `smoke.py`, `SpanActions.tsx`.

## 4. What was built

1. **Geometry, in numbers.**
   - **Lanes:** n channels get equal lanes. Block height H = max(420, 28·n + 20) px, so 16 channels give 468 px and a lane of (468 − 20)/16 = 28 px. Six channels give 420 px and lanes of 66.7 px.
   - **Lane position:** lane i is centred at 10 + lane·(i + ½), with i the channel's position in the recording (CH1 first).
   - **Centring:** each trace is drawn about the mean of its own envelope values over the window. The ~3.9 V DC offsets between electrodes therefore vanish, and values are not otherwise changed.
   - **Gain:** one shared gain for all channels. The median channel's own range (max − min over the window) spans 1.6 lanes; at 28 px lanes that is about 45 px. A channel twice as lively is drawn twice as tall.
   - **Clipping:** a trace that runs past the block is clipped by the block, never rescaled.
   - **Plot area:** a 118 px name gutter on the left; the plot takes the rest of the card width. The x axis is the window's absolute seconds, with the same ticks as the stack, labelled in seconds from the onset.
   - **Bold and faded:** bold traces are 1.8 px at full opacity and painted last. Faded traces are 1 px at 0.18 opacity. With nothing bold, every trace is 0.75 opacity.
   - **Detections:** each is a 2.5 px cap at the top of its channel's lane, in the channel's colour.
   - **Hover:** a dashed crosshair plus a readout showing t into the window and each bold channel's value (up to 8), taken at that channel's own clock.
2. **Props interface** (`Overlay.tsx`, props only, no fetch and no page state):
   ```ts
   interface OverlayChannel { id: number; name: string; colour: string; t: number[]; v: (number|null)[]; lag_s: number|null;
     detections?: { id: number; t0: number; t1: number }[]; error?: string }
   interface OverlayProps {
     channels: OverlayChannel[]; window: [number, number]; selected: number[]; onSelect(ids: number[]): void
     brush: [number, number] | null; onBrush(w: [number, number] | null): void
     align: boolean; onAlign?(on: boolean): void; referenceId?: number; maxLagS?: number
     band?: [number, number] | null; ticks?: { t: number; label: string }[]; unitLabel?: string; width: number; testid?: string }
   ```
   - It goes beyond the prompt's sketch (`channels`, `window`, `selected`, `onBrush`): the selection and the box are controlled by the parent, so Discovery can hold them in its own state.
   - The parent measures `width`. The page draws the tick labels, the header controls and the action strip itself. Discovery can reuse or replace those.
3. **Interaction.**
   - Clicking a name, or clicking without dragging near a trace (within 10 px), toggles bold.
   - Clicking empty space clears the box.
   - A drag of 4 px or more sets the box (`ov-brush`).
   - Keys: ↑/↓ move the bold channel; A toggles align; Esc clears the box.
4. **Box actions.**
   - `SpanActionStrip` with `onZoom` (writes `?t0=&t1=` = the box), Send unjudged (`reviewChannels` = bold), Mark artifact (picker pre-ticked with the bold channels via `defaultArtifactIds`), Open in Analyse, and `extra` = Open in Signal.
   - With nothing bold, the strip is disabled with a reason.
   - A caption names the box (s from onset, its length, the number of bold channels) and has a *clear* link.
5. **Not built:** a hand-drag lag adjustment (deferred until the measured lags prove wrong, as decided), the Discovery mount, and a bridge `px` change (not needed).

## 5. Tests

- **No red commit.** Nothing in Python changed (see Assumed), so there is no bridge behaviour to pin first.
- **Ran with the `webui/.venv` python:** `tests/test_webui_cross_channel.py` + `tests/test_webui_cross_window.py`, 16 passed.
- **Ran with the conda python:** `tests/test_import_boundaries.py`, 4 passed.

## 6. Smoke states: `webui/smoke_pages/zzzzzzzzzzz_overlay.json`

1. `overlay-stacked-is-default` (`explore/cross-channel/4`): the stack as before, with `view-seg` present, and `y-select` and `align-seg` still shown. No overlay.
2. `overlay-draws-every-channel` (`?view=overlay`): the overlay block carries `data-height`, which must be ≥ 420; it carries `data-lane` (≥ 28) and `data-channels` (16 on M2_aug minus any held out). It has one `ov-trace-*` path and one `ov-name-*` per channel, and the header shows align / all / none / box the span. `y-select`, `align-seg`, `reference-trace` and `ov-det-error` are absent. **By hand:** check that CH1 is at the top, that traces overlap their neighbours a little, and that no trace is a flat line.
3. `overlay-click-name-bolds`: clicking the first name makes it the only bold channel. Checked by `data-bold-count="1"`, `data-bold="yes"` on that name and path, `data-bold="no"` on the rest, and `bold=` in the address.
4. `overlay-align-shifts` (`&maxlag=60`): clicking `ov-align` gives `data-align="lag"`, every non-reference name prints its shift (`ov-shift-*[data-shift]`), at least one `ov-row-*` carries a non-zero `data-shift`, and the address holds `align=lag`. This has the same caveat as `aq-lag-aligned-moves-rows`: if every lag is 0 or past ±60 s, that is a finding about the data.
5. `overlay-box-shows-strip`: clicking `ov-box-span` draws `ov-brush`, the caption, `overlay-action-strip` and `ov-open-signal`. Nothing in the strip is clicked, so nothing is written.

**Worth doing by hand on real data:**
- drag a box, confirm *Mark artifact* is pre-ticked with exactly the bold channels;
- with align on, open a shifted channel in Signal and confirm it lands on the lined-up moment.

## 7. Gates I ran

- `tsc -b`: clean, exit 0 (run twice).
- `vite build`: built, with only the existing Gallery dynamic-import warning.
- Tests: the three files in §5.

## 8. Open questions and risks

- **Resolution:** at `px=600` the envelope is about 1,200 points per channel, roughly one per pixel on a 1,000 px plot. A very wide screen would want the page's `px` raised to the plot width. That is one number in `api/explore.ts::getCrossChannel` (the stack shares it), not a bridge change.
- **Gain:** the median range rule means one very lively channel can overrun several lanes, where it is clipped. The researcher may prefer a different rule, for example per-lane, or a smaller multiplier. It is one constant (`GAIN_LANES`).
- **Detections:** 16 `/spans` reads per window in overlay mode. They are cheap on the fixture, but not timed on the real database.
- **Run filter:** the overlay's detections are not filtered by the detections chip, which acts on the reference's runs only. Surrogate and window-part runs are already left out by the bridge.
- **The header row is crowded** at narrow widths. Polish is left to `polish-pass`.
- **Left for later:** the Discovery mount.

## 9. Commits

- `7fa6062` overlay: Cross-channel's overlay view (component, page wiring, css, smoke states)
- (this report)
