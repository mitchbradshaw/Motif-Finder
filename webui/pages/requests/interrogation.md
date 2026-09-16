# Kit / shared requests — Interrogation builder

Written from `webui/client/src/interrogation/`. Everything below is **worked around locally** in that
directory, so nothing here blocks the build; each entry says where the local stand-in lives.

## kit

1. **`LineChart` needs `bands`** (like `Trace`'s). Frames 2 / 2b / 2c shade the onset → trough interval of
   the anatomy figure in amber. `Trace` takes `bands`, `LineChart` does not, and the anatomy figure has to
   be a `LineChart` because it draws a chord and a tangent as extra series. *Workaround:* the band is not
   drawn; onset / steepest / trough are vertical markers only (`SlopePage.tsx`, `anatomy-plot`).

2. **`LineChart` should clip series to `xDomain`.** A point outside the domain is still stroked, so a long
   recovery tail paints over the card. *Workaround:* every page filters its point arrays before passing
   them (`clip()` in `SlopePage.tsx`).

3. **A polar / rose plot.** "Each fall as one angle" (frame 2) is a 0° … −90° quadrant with radius = event
   order and a colour ramp. Two other frames outside this unit draw angle roses too. *Workaround:*
   `interrogation/Rose.tsx` (~90 lines of SVG, kit tokens only).

4. **A variable-height event rail.** "When events happened" (frame 3) is one lane per recording with a tick
   per event whose height is the plotted measure. `BandStrip` draws fixed-height segments and cannot vary
   height. *Workaround:* `interrogation/EventTimeline.tsx`.

5. **`Histogram` overlay opacity.** The frames draw the null in solid grey *behind* and the observed series
   solid *in front*; `overlay` is always painted at 0.55 opacity on top, so the observed bars wash out.
   An `overlayOpacity` (or `overlayBehind`) prop would fix it. *Workaround:* null passed as `values`,
   observed as `overlay`, with more saturated feature colours.

6. **`Histogram` has no stacked mode.** Frame 3b stacks the observed bars by recording over the same bins.
   *Workaround:* `StackedHist` in `AggregatePage.tsx` re-bins with `binValues` and renders `Bars`
   `mode="stacked"`, which loses the null behind.

7. **`DisabledReason` cannot wrap a `<tr>`** — it renders a `<span>` wrapper, which is invalid inside
   `<tbody>`. A `block`/`asChild` mode that adds only `title` + `aria-disabled` would help every picker
   table. *Workaround:* the picker rows carry `title`, `aria-disabled` and a visible `⊘ reason` cell.

8. **`Slider` has no `changed` / pending tone.** `NumberField` has `changed`; the frame 2c slider is amber
   while its value is unapplied. *Workaround:* the card border goes amber and a `(was 3)` note sits beside it.

## fixtures/canon.ts

9. **Families the frames use are missing from the canon.** `F-01 single drop` (64 members, 2 recordings,
   60 adjudicated) is drawn in the source picker; the picker also needs, per family, the *within-threshold*
   count, the recording count and the adjudicated count. §0 has only name + member count. *Workaround:*
   `fixtures/interrogation.ts` `FAMILIES` carries them; if canon gains them, that list should import instead.

10. ~~**`ANALYSE_RUNS` maps `#140 F-03 slope interrogation` to `spike_shape_v1`.**~~ **Done** in `511d6c9`:
    canon now maps `#140 → sharkfin_slope_v1`, keeping `spike_shape_v1` for the Spike-shape block.
    `PRIOR_RUNS` in `fixtures/interrogation.ts` already agrees.

11. **A shared `FamilyMember` type.** Library › Family, Review cluster strips and this unit all need
    `{ id, family, recording, channel, onset_h, d, verdict, fs_hz, trace }`. The inventory proposes it for
    canon. *Workaround:* `InterrogationMember` extends that shape with the slope features.

## shell

12. **`Header` has no place for an in-page state chip.** Frames 2c and 3b put the page's state in the header
    subtitle (`1 unsaved rule change`, `coloured by recording · depth ~ max slope`). `extra` exists but sits
    on the right beside the search pill. *Workaround:* the subtitle string carries it.
