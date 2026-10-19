# family-actions — report (library-family-actions)

WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\family-actions
BRANCH: changes/family-actions (base 9ff6774)

## 1. Assumed

- **The rose reference already existed.** fixup-ae built `GET /api/library/rose-reference`. It returns the STORED
  45° (`value_mv_s`, `population`, ...). That value is the median over accepted motifs, but it falls back to
  "every motif above the floor" below 30 accepted, and it only moves when someone presses Recompute. The prompt
  wants a line that is live, has `n: 0` and no line when nothing is accepted, and moves after a verdict, so the two
  are different numbers. I kept the existing read unchanged (the Settings page and runtime use it). **`?unit=motifs`
  on the same path** returns the new line, `{unit, median_slope, n, field, computed_from}`. Any other unit gets a 400
  that says why. There is one route block in `library.py`: a helper and a cache placed above the existing GET, and
  one optional parameter added to that GET.
- **"Accepted" is the one resolver's `side == "yes"`** (interesting or seed). I reused
  `rose_reference.compute(conn, min_accepted=1)` and its accepted branch is exactly this population. I did not write
  a second slope reader.
- **The cache key is `(database, unit)`, with `_view_fingerprint(conn, 0)` as the "adjudication fingerprint".** It
  covers members, hand edits, annotations, adjudications, features, settings and units. A verdict moves it.
- **Where the line sits on a rose:** at the accepted median on that rose's OWN 45°. That 45° is read off the rose's
  events as `|slope| / tan|angle|`. On a raw or pooled rose every event gives the same value. On a recording- or
  event-scale rose the value differs per event, so the line is **not drawn** and the label says why. On a rose of
  anything other than `max_slope_mv_s` there is no line either. The label is printed in every case. Only the
  placement is computed in the browser; the median and n come from the bridge.
- **"Send to Review (the picked-queue mechanism, one detection)":** `sendDetectionsToReview` needs a Discovery run
  key and detection ids, and a Library member has neither. I used the family page's own one-member route instead:
  `sendFamilyUnjudged(family, grouping, view, [member])`, the same call the batch bar's *Send to Review* makes. The
  member joins the family's one Review queue. The button is disabled, with the reason, for a member that is already
  judged (the bridge would 409).
- **"Open in Explore"** sets Explore's own view state (`explore.channelId` / `view`, which the Signal page opens on)
  to the member's span with ±max(30 s, 2× its length), then navigates to `explore/signal/<recording>`. It does not
  touch `ub-proto-a:source`, because that is the Analyse source and overwriting it would change someone's chain.
- **"Remove from the family"** goes through the existing confirm modal (`remove-member-modal`) for the picked member,
  so it is the same hand edit with the same Undo.
- **"The family page's cluster strip":** the family page shows one family, and there is no strip of other clusters
  on it. I took the family's summary card to be its cluster card. Clicking the exemplar/medoid plot, or the new
  *Every member as a slideshow* link, opens the members in place in H's slideshow, using `FamilyMembersInPlace`, the
  atlas's host and the same loader (`?slides=1`, linkable). The **atlas motif card** already did this (fixup-ae).
  The **sequence atlas cards** are unchanged: the in-place host reads motif members, and a sequence family needs a
  different read.
- **Picked state is in the URL** (`?pick=m-…`) so a pick can be linked to, and so the smoke walk can test it
  deterministically.
- **Esc closes the in-place slideshow** on both the family page and the atlas. It does not close it when a nearer
  handler took the key (the overlay's own Esc clears the pick first) or when a modal is open.

## 2. In plain words

On a family page you can now click any grey trace in the overlay. It turns black, a small card names it (recording,
channel, time, verdict), and three buttons sit beside it: take it out of the family, send it to Review, or open it
in Explore at that moment. The arrow keys step through the traces. Clicking the family's summary plot lays every
member out side by side as a slideshow, right on the page, and Esc closes it. Every rose now also draws a dashed
purple ray where a "typical accepted fall" would sit: the median steepest slope of the motifs people have accepted,
with how many there are. It moves as soon as someone judges another one.

## 3. Files

Created:
- `webui/client/src/library/FamilyOverlay.tsx`: the hit-tested overlay (`FamilyOverlay`, `nearestTrace`) and the
  pick card (`PickCaption`).
- `webui/client/src/library/roseReference.ts`: the `useRoseReferenceLine()` hook.
- `tests/test_webui_library_family_actions.py` (venv).
- `webui/smoke_pages/zzzzzzzzzzz_family_actions.json`: seven states.
- this report.

Modified:
- `webui/server/library.py` **(shared)**: `_ROSE_LINE_CACHE`, `ROSE_LINE_UNITS` and `_rose_reference_line` are new,
  placed just above the existing `GET /rose-reference`. That GET gains an optional `unit` parameter and one `if`.
  Nothing else changed.
- `webui/client/src/api.ts` **(shared, append-only)**: `LibRoseReferenceLine` and `getRoseReferenceLine` at the end.
- `webui/client/src/kit/Rose.tsx` **(shared kit)**: `RoseData.field?`, the `RoseReferenceLine` type, the
  `fortyFiveOf` placement helper, the `reference` prop, the dashed ray (`rose-reference-mark`) and the label line
  (`rose-reference-line`). Existing behaviour is unchanged when no `reference` is passed.
- `webui/client/src/kit/index.ts` **(shared, append-only)**: one `export type { RoseReferenceLine }` line.
- The three rose sites, each with a hook line plus `reference={roseRef}`:
  - `interrogation/SlopePage.tsx`
  - `interrogation/SequencePage.tsx`
  - `analyse/views/registry.tsx` (`SpansToSpans`; the hook sits before its early return)
- `webui/client/src/library/FamilyPage.tsx`:
  - the overlay `MiniTrace` is replaced by `FamilyOverlay` plus `PickCaption`;
  - `?pick=` and `?slides=` were added;
  - the summary plot is now clickable, with the slideshow link and the in-place host beneath the summary.
- `webui/client/src/library/MemberSlideshow.tsx`: Esc closes `FamilyMembersInPlace`.

## 4. What was built

1. **Overlay pick.** The overlay is drawn in real pixels, with no stretched viewBox, so distances are screen pixels.
   - A click picks the member whose path passes nearest the pointer, if it is within 6 px (point-to-segment over at
     most 400 points per trace). A click on empty plot clears the pick.
   - ↑ / ↓ move the pick, wrapping. Esc clears it.
   - The picked trace is drawn heavy (`overlay-picked-trace`) and the medoid fades.
   - The caption card (`overlay-pick-card`) shows the id, recording · channel · onset h (start–end s) and the
     verdict, with three buttons: Remove from family, Send to Review, Open in Explore.
2. **Cluster click leads to the slideshow in place.**
   - Family page: the summary plot, or *Every member as a slideshow*, toggles `FamilyMembersInPlace` (testid
     `family-members`). This is the atlas's host and loader (`/api/channels/{id}/window`, the member's span with
     context).
   - Esc closes it there and on the atlas.
3. **Rose reference.**
   - The route returns `{median_slope, n, computed_from}`.
   - The kit `Rose` takes `reference` and draws a dashed purple ray labelled "`<v> mV/s · n <n>`". The side panel
     prints "reference line · accepted median v mV/s · n = N · at −θ°", or "not drawn: …", or "no reference line: …
     (n = 0)". A failed read prints "reference line not read: <error>" in red, and `useSourced` logs it to the
     console.
   - All three rose sites pass it.
   - `analyse/EventFeatures.tsx` holds a fourth `<Rose>` that the prompt did not name. I left it alone. It is a
     one-line follow-up if it is still reached.

## 5. Tests

- **Red** `2e452f0` (tests only), webui/.venv: 4 failed, 1 passed. The new shape was absent:
  - `assert 4 == 0` ×3 (the old above-floor n came back);
  - `assert 200 == 400` (an unknown unit was not refused).
- **Green** `tests/test_webui_library_family_actions.py` under **webui/.venv**: **5 passed**. It pins:
  - with nothing accepted, `n` is 0 and `median_slope` is None, with a reason in `computed_from`;
  - the median is over accepted motifs only and moves after a verdict, through the cache (an `interesting` window on
    hash1 gives n 1 and 2.0; a `seed` on hash3 gives n 2 and 3.0);
  - an `artifact` verdict does not count;
  - `unit=sequences` gets a 400 that names motifs;
  - the stored-45° read with no unit keeps its shape.
- `tests/test_webui_library.py` (webui/.venv): 59 passed, 3 xpassed
- `tests/test_webui_library_view.py` (webui/.venv, the existing rose-reference test): 9 passed
- `tests/test_import_boundaries.py` (conda): 4 passed

## 6. Smoke states — `webui/smoke_pages/zzzzzzzzzzz_family_actions.json`

All of these assume grouping `g-05`, which has `F-03` and member `m-856`, as `library.json` already uses.

1. `family-actions-a-picked-trace-names-its-detection`: `library/family/F-03?pick=m-856`. Must show:
   - the heavy trace `overlay-picked-trace[data-member=m-856]`;
   - the caption card with where and verdict;
   - the three buttons;
   - no hint line.
2. `family-actions-a-click-on-the-overlay-picks-a-trace`: a click on the overlay svg, then ArrowDown. One trace is
   picked either way (the click picks one or clears; ArrowDown moves on or picks the first). Must show the card and
   the three buttons.
3. `family-actions-the-family-opens-its-members-in-place`: click *Every member as a slideshow*. Must show
   `family-members[data-family=F-03]` with `family-members-slideshow` and `slide-m-…` cards, with the family page
   still there.
4. `family-actions-esc-closes-the-slideshow`: `?slides=1`, then Esc. The slideshow is gone and the page is still
   there.
5. `family-actions-esc-closes-the-atlas-slideshow`: click the atlas card F-03, wait for the slideshow, then Esc. It
   is gone.
6. `family-actions-the-sequence-rose-prints-the-reference`: `analyse/interrogation/sequence?id=1`. The rose card
   carries `rose-reference-line`.
7. `family-actions-the-slope-rose-prints-the-reference`: `analyse/interrogation/block/1`. The `rose` carries
   `rose-reference-line`.

On real data, the manager should look at two things:
- whether the sandbox DB has accepted motifs. If it has none, the label says "no reference line … (n = 0)" and no
  ray is drawn; that is correct, not a failure.
- that the dashed ray on a raw rose lands where expected. It sits at −45° exactly when the accepted median equals
  the rose's 45°.

## 7. Gates I ran

- `tsc -b`: clean (twice, after the client compiled and before reporting).
- `vite build`: built (twice).
- Test files, one at a time: see §5. I did not run the whole suite or `-n`, and did not run the browser smoke.

## 8. Open questions and risks

- **Two "rose references" now exist.** One is the stored 45° (Settings). The other is the live accepted-median line
  (this prompt). On a raw rose whose 45° is the stored accepted median, the line sits at −45° until verdicts move
  the live one. That is the point, but the researcher may want the Settings card to mention the line.
- **Send to Review uses the family queue, not Discovery's picked queue** (see Assumed). If "picked queue" was meant
  literally, a Library-member variant of `_send_picked` would be needed in `discovery.py`, which is not my file.
- **The 6 px hit radius is tight on a 222 px-wide overlay.** The keyboard and `?pick=` are the fallback. A wider
  overlay would be a layout change on the summary card.
- The sequence atlas cards do not open a slideshow in place (see Assumed).
- `EventFeatures.tsx`'s rose has no reference line (not named by the prompt).

## 9. Commits

- f366f9f family: pick a trace in the family overlay; the family's members in place; the rose reference line
- 2e452f0 family: red - the rose reference line is the live median over accepted motifs, n 0 with none
- (this report, committed last)

## Critic round (2026-10-19)

**In plain words.** The work does what the prompt asks. One real bug: the reference line is remembered until
"something about the verdicts changes", and the check for that change looked only at how many verdicts there are
and the newest one's number. Review changes a verdict by rewriting the existing row, so a member re-judged from
*interesting* to *artifact* left the line where it was. That is like a shop counting its receipts to see whether
the takings changed: an edited receipt goes unnoticed. The check now also reads the verdicts themselves.

**Checked and found right**
- The median by hand: accepted slopes |−2| and |−4| give 3.0, n 2; an *artifact* window does not count; nothing
  accepted gives n 0 and no line. `rose_reference.compute(min_accepted=1)` is the one slope reader; no second one.
- The angle placement. The core draws each event at `arctan(slope / ref)` (`gradients.slope_angles`), so
  `|slope| / tan|angle|` gives `ref` back exactly. I checked this on synthetic payloads in node. Pooled with
  ref 2.5: the line for median 3 sits at −50.194°, the same angle as the event of slope −3. Raw gives 1.0. A
  recording-scale rose over two recordings gives null, so no ray is drawn and the label says why. Correct.
  `_clean` does not round angles, so the 1e-3 agreement tolerance holds.
- Explore. `SignalBody.initial()` reads `explore.view` when `explore.channelId` matches the route's channel.
  `startS`/`endS` are seconds from the recording's start (`start_idx / fs`), and the recording id is the channel
  id (the same id the slideshow's `/api/channels/{id}/window` uses). So the Signal page opens on that span.
- The hit test. The SVG has no viewBox and its width is the measured width, so `clientX − rect.left` is in CSS px.
  devicePixelRatio does not enter. `useSize` re-measures on resize. A click on the SVG focuses the tabIndex=0 box,
  so ↑/↓ work straight after a click. The overlay's Esc calls preventDefault, so the slideshow's window listener
  stands back.
- The atlas card's onClick sets `?members=`, which opens `FamilyMembersInPlace` (fixup-ae). The smoke unit's
  grouping, family and member (g-05 / F-03 / m-856), and the routes `analyse/interrogation/sequence?id=1` and
  `.../block/1`, all appear in existing passing states (`library.json`, `interrogation.json`). The JSON parses.
  The harness supports `press`, `click_if` and `wait_for`.
- First commit `2e452f0` touches `tests/` only. The red run was 4 failed and 1 passed.

**Deviations judged**
- (a) Send to Review via the family queue: **accepted.** `sendDetectionsToReview` takes a Discovery run key that
  a Library member does not carry. The family queue lands the member in Review and judges it as a member, and
  its verdict comes back through the same resolver the line reads. A member does have detection ids behind its
  edges, but routing those through the picked queue would judge a detection rather than the member, and the
  family would not see it. That would be less faithful.
- (b) Explore view state rather than `ub-proto-a:source`: **accepted** (see above). Overwriting the Analyse
  source would change someone's chain.
- (c) The summary card as the "cluster strip": **accepted.** The family page has no strip of clusters, and the
  atlas card already opens its members in place.

**Fixed (b3de3b4)**
- *should-fix*: the cache key moves on a verdict changed in place (`_verdict_checksum`). New tests: a verdict
  changed in place moves the line (red before the fix); three reads compute once, and a new verdict computes again.
- *minor*: Esc typed in a text field no longer closes the slideshow.
- *minor*: the in-place host on the family page no longer offers a primary "Open family page" that navigates to
  the page you are already on.
- *cheap extra*: `analyse/EventFeatures.tsx`'s rose gets the reference line. `EventFeaturesPanel` currently has
  no caller, so this costs nothing.

**Not fixed (noted)**
- `_view_fingerprint` itself has the same blind spot for verdicts changed in place. That affects every other
  view cache that uses it, it predates this branch, and it is out of scope here.
- The 6 px radius is tight on a 222 px overlay; the keyboard and `?pick=` are the fallback.

**Gate after the critic's fixes**
- webui/.venv: `test_webui_library_family_actions.py` 7 passed; `test_webui_library.py` 59 passed, 3 xpassed;
  `test_webui_library_view.py` 9 passed.
- conda: `test_import_boundaries.py` 4 passed.
- `tsc -b` clean; `vite build` built.
