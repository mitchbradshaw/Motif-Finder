# UX-1015 — the manager's evaluation (the researcher's 2026-10-13 list, run 2026-10-15 → 16)

**Status: in progress.** Sections are written as each prompt merges; AN, AL and AP are pending. The ledger
(`UX-1015-ledger.md`) holds the timeline, the decisions and every gate's numbers.

## In plain words

You gave two lists on the 13th: small things to fix straight away, and bigger things that each needed their own
agent. The small things are in. Of the seven bigger things, four are merged and pushed as this is written, two
are in their fix rounds, and the last (the grey-text sweep) runs once everything else has landed. Each of the
bigger ones was built by one agent, checked by a second agent that tried to break it, fixed once, and then put
through the same gate: its tests under both Python interpreters, the client type-check and build, and its own
browser states walked on a sandbox copy of your database. Nothing below was merged on an agent's word alone.

Two things need your word, because nobody could ask you while you were away; both are safe either way and are
marked **decide** below.

## The small list (on main, 2026-10-15)

| Item | What changed | Evidence |
|---|---|---|
| Browse detections lag | the card shows a loading bar and dims the old detection while a run's list is re-read | wired to the reader's `loading`; too fast to catch on the sandbox (< 25 ms) |
| Default chain on opening Analyse | a fresh session opens on an empty canvas with four starts: import a template, add the first block, the old mp_threshold chain as "Example", and "Restore <last chain>" when this browser has one | 4 new page states 4/0; the 47 existing Analyse states 47/0 with the walk seeding the old chain |
| Delete a block from its page | a Delete block button on the block page, the same delete-with-undo the canvas uses | page state passes; Ctrl Z on the chain page undoes it |
| Legacy-detections warning spam | warned once per process per run, then one DEBUG line counting repeats | test red then green (12 pass); nothing about those runs changed |
| Slideshow after a pick | the grid jumps to a picked card's page only when the selection changes | hand check on 33 spans: resample shows a new set and keeps it; show-in-order + next page moves and stays |

## AK — the spike detection block (merged 06f94db)

**Asked:** say what it does, why it misses, what to tune. **Shipped:** spans are spikes (one per event, not the
gaps between), a signed test with `polarity` both/up/down, the threshold in millivolts (`delta_mv`, converted by
the recording's declared unit), a vectorised core (2.6 M samples in 0.2 s), the page's one-sentence face with
"tune delta_mv first", a readout row saying how far δ sits above this span's own noise (amber below 4×), the
up/down counts and the unit note on the chain row.

**The critic's blocker, fixed:** the paper's keep-first refractory rule put a dip's spike at the edge of a "halo"
the dip casts on the local mean, so a 10 mV × 10 s dip read as three rises and never as a dip. Now candidates
closer than d samples are one cluster, placed at the sample furthest from the raw baseline outside the cluster;
each of 10 mV × 10 s, 3 mV × 30 s, 30 mV × 3 s and 60 mV × 5 s dips on +2, −2 and −0.43 V baselines gives exactly
one spike, marked inside the dip, nothing under `up`.

**Decide:** the default δ of 1 mV is a placeholder measured clean at M2's noise (0 false positives per hour at
0.025 mV per sample; 61–64/h at 0.1 mV) and wrong for noisier channels (713 false spikes in 12 h at 0.25 mV
innovations). The readout row tells you when to raise it. Also: an undeclared unit is read as volts with a note,
not refused — your Q20 choice of 2026-10-15 applied consistently; the prompt had said refuse.

**Check on your data:** the spike count on M2 CH4 over one hour at δ = 1 mV against what the old block counted
(the gaps), and the δ-vs-deviation row on a quiet stretch. No saved template names `spike_v1` with the old
`delta`, so the rename refuses nothing you have.

## AM — peak- and trough-aligned windows (merged eb2c57a)

**Asked:** "peak aligned" as a third alignment; the prompt opened with a question you could not answer.
**Built (decision D3, the prompt's own recommendation):** `align` in {grid, centre, peak, trough} plus an
`anchor_frac` in [0, 1]. `peak` is the highest point and `trough` the lowest of the same guarded departure the
existing `centre` uses, so a one-sample glitch is never chosen; the anchor says where that point lands in the
window (0.5 the middle; 0.33 a third in, so a slow recovery fits).

**Bit for bit at the defaults:** the critic ran 8 combinations against main's code on a 1,200-window pool — keys,
vectors, frames and tree keys identical at (centre, 0.5); the key moves for peak, trough and any other anchor, so
no cached pool or tree can answer for the wrong alignment. The B.2 model recipe carries the anchor when it is not
the default, so a model trained from a trough-at-a-third chain rebuilds the same windows.

**Decide:** keep `centre` at 0.5 as the default (as built), or make trough-at-a-third the default for drop work.
Also a small follow-up not made: the Models › Launch setup display still shows align and detrend but not the anchor.

**Checked on the real pool at the gate:** the Ward build at trough and anchor 0.33 ran and the tree card named it.

## AO — the Decompose block (merged 868795d)

**Asked:** split a signal into baseline, noise and frequency components and choose which continues. **Shipped:**
`preprocessing.decompose` — baseline (the core's running median over a reflect-padded span, or Detrend's rolling
mean), noise (the Highpass block's filter on input minus baseline, cut fs/8 by default), signal (the rest); the
three add back to the input to 1e-16; `pass_on` picks the layer that goes on; the block page draws the three
rows with the wavelet block's existing drawing, and a click on a row sets `pass_on` through the same path the
Parameters panel uses. The frequency case is the existing Wavelet bands block, which the page points at.

**The critic's measurement, now on the face:** a running median absorbs an event longer than about half its
window. At the default 600 s a drop with a 10 s onset and 60 s recovery keeps 0.98 of its depth in `signal`; one
with a 60 s onset and 600 s recovery keeps 0.14 (0.86 goes to the baseline); a dense train of 10-minute
recoveries keeps 0.15 at 600 s and 0.56 at 1800 s. Noise never takes a drop (≤ 0.003). The help and description
now say: an event longer than about half the window starts going to the baseline; for drops that recover over
5–10 minutes use 1800–3600 s. A drop cut off by the span end now keeps 0.996 of its depth (it kept 0.056 under
the end-sample padding the first round used).

**Decide:** whether 600 s should stay the default for your data, where recoveries of 5–10 minutes are common. The
prompt fixed 600 s; the help tells you when to raise it.

## AQ — Explore › Cross-channel finished (merged aee1dcc)

**Asked:** finish the page — rows that plot, a window picker that picks. **Shipped:** rows fill their height at
one shared gain equal to the widest drawn row's range (the note used to print a padded domain, about twice the
truth — that was the 20.74 mV); the picker, the arrows and the deep links drive one window; each pair's lag, r and
bin come from one call of the core's classifier on the window with each channel's straight-line trend removed;
lag-aligned shifts rows by their lag; disabled cards print their reason; the lock says how to change the
reference.

**Your six zero lags, explained and confirmed on your own window** (recording 2 = CH2_A1, 0.772–0.950 h, through
the merged bridge): as recorded, CH7_B2, CH8_B2, CH9_C1, CH10_C1 and CH11_C2 all read lag 0.0 and r −0.96 to −0.98,
exactly the screenshot's rows. With the trend out they read |r| 0.45–0.72 at lags between −313 and +221 s and bin
independent. A shared drift over the window, not a curved one (the curved-drift flag is off on every row) and not
simultaneous pickup. The rows were binned independent before too, correctly: the artifact line is |r| ≥ 0.98
since fixup-AD, not the 0.5 the tooltip used to claim.

**What the page now says that it did not:** a row with |r| ≥ 0.9 both detrended and as recorded at |lag| ≤ 1 s
is marked "may be curved drift" (a straight line cannot remove a curved one; a cubic detrend is on the bridge,
`detrend=cubic`, not yet a page control); about 1 in 6 pairs of unrelated random walks bins "propagation" over a
640 s window because the lag search covers the whole window — an Explore propagation badge is a lead, not
evidence, and RQ6 now says so.

## AN — the Library dendrogram (pending: fix round)

*(critic: merge after fixes — results exact at every cut on 300 and 3,000 members, rule 4 holds, schema
additive, reuse calls linkage once; the preview took 3–6 s at low cuts, the linear tree axis squeezed the useful
range, the file self-check skipped the arrays)*

## AL — send one detection to Review (pending: fix round)

*(critic: merge after fixes — one picked queue per session, the no-op repeat, rule 5 and the run-wide send all
held; the "in Review" tick could show for a pick Review will never serve)*

## AP — the grey-text sweep (pending: runs last)

## The gates

Per prompt: its tests under conda and `webui/.venv`, `tsc -b`, `vite build`, a sandbox bridge restarted on the
merged tree, its own smoke states walked. Numbers in the ledger. The full `pytest -n 4` and the full smoke walk
run once after the last merge; their results close this file.
