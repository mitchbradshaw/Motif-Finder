# Public poster: "The electric pulse of mushrooms" (A1, 25 Nov 2026)

An A1 landscape poster (841 × 594 mm) for a general audience about mycelium signals and what we found. It borrows the
layout, colours and presentation of the thesis poster (Canva design `DAHYlZx85sw`), but the subject is the signals,
not the MycoWave site.

* **Print file:** [`poster_A1.pdf`](poster_A1.pdf) (one page, 841 × 594 mm, fonts embedded).
* **Images:** [`poster_preview.png`](poster_preview.png) (screen) and `poster_x2.5.png` (about 240 dpi at A1).
* **Source:** [`poster.html`](poster.html) places the figures in `figures/` at their printed size. Edit the text there
  and re-render.

## In plain words: what the poster says

* **Left half, "One drop at a time".** The commonest event in a mushroom's voltage is a *drop*: a sudden fall and a
  slower climb back. We take 29,128 drops from seven of our own recordings (five species), stretch every one to the
  same size so only its shape is left, and sort them on a 20 × 20 grid by how sharp the fall is and how slowly it
  climbs back. The shapes morph from needles to everyday V's to steps that never come back. Each species has its own
  fingerprint: in shape they overlap, in speed they spread apart (chocolate oyster falls in about 7 s, shiitake in
  about 54 s).
* **Right half, "Drops come in trains".** Three trains, each with one analysis a lay reader can follow:
  1. *A heartbeat with two beats* (lion's mane, MJu26a CH14, 90 h): thin and wide big drops take turns. After a wide
     drop, the next big drop is thin 70 % of the time, against 54 % if the order were random.
  2. *A crescendo* (oyster, M2_aug CH1, seq 119): 17 drops, each deeper (20 → 59 mV), the gaps stretching from 11 to
     57 minutes.
  3. *A metronome* (oyster, M2_aug CH1, seq 129): 14 near-identical drops, one every 8.5 minutes, give or take 4 %.
  Then ten more trains as thumbnails, from all five species.

## Rebuild it

All from the repo root with the conda Python (`"/c/ProgramData/anaconda3/python.exe"`) and `PYTHONIOENCODING=utf-8`.
Each step takes seconds.

| Step | Command | Writes |
|---|---|---|
| drop table | `scripts/public_poster/prep.py` | `data/drops.parquet`, `data/drop_shapes.npy` |
| waveform map | `scripts/public_poster/fig_wavemap.py` | `figures/wavemap*`, `data/wavemap.json` |
| species | `scripts/public_poster/fig_species.py` | `figures/species_fingerprints.*`, `figures/species_boxes.*` |
| CH14 kinds | `scripts/public_poster/seqdata.py` | `data/ch14_*.csv`, `data/ch14_kinds.json` |
| three trains | `scripts/public_poster/fig_trains.py` | `figures/train_{heartbeat,crescendo,metronome}.*` |
| thumbnails | `scripts/public_poster/thumbs.py candidates`, then `... panel` | `thumb_candidates/`, `figures/train_thumbnails.*` |
| drop anatomy | `scripts/public_poster/fig_intro.py` | `figures/intro_anatomy.*` |
| numbers | `scripts/public_poster/ledger.py` | `data/numbers.json`: every number the text quotes |
| render | `scripts/public_poster/render.py` (`--scale 2.5 --no-pdf` for the big PNG) | `poster_A1.pdf`, `poster_preview.png` |

Figures are drawn at their printed size in millimetres with poster-sized type (`scripts/public_poster/style.py`), and
`poster.html` places them 1:1. The text in the HTML is typed by hand, so after a data change, re-check it against
`data/numbers.json`.

## What went in, and why

**Drops (left half).**
* Source: the 24 Nov auto-detect pool's core tier, kept where the verdict model puts a drop at p ≥ 0.8. The
  Auto-detect session advised this cleaner set. To it were added the 3,190 reviewed library drops from the 23 Nov drop
  plots, which the pool had left out because they were already judged. The two sets do not overlap.
* Recordings: our own, with a recorded species.
  * Oyster: M2_aug (15,197 drops) and M4 (1,363).
  * Chocolate oyster: CO (2,885).
  * Snow oyster: SO (626).
  * Shiitake: SH (793).
  * Lion's mane: LM (3,235) and MJu26a (5,029).
* Left out:
  * Adamatzky's four species (Cordyceps, enoki, split gill);
  * the Dwij loggers;
  * M1, L_R_Aug_26_PD and F2B, whose species is unknown;
  * **M2_concat**, see open question 1.
* MJu26a's reviewed drops sit on the 10 Hz copy. They were moved to the 2 Hz copy (same channel, index ÷ 5) and their
  shape redrawn, so all MJu26a drops are measured at one rate.
* The map's steepness is read at each recording's own rate (1 or 2 Hz), because the glyphs are drawn at that rate. The
  species fingerprint's steepness is re-read at 1 Hz for every recording (block means of 2), so the 1 Hz oysters and
  the 2 Hz others compare fairly.
* **The rate check (25 Nov).** The Auto-detect session warned that steepness rises with the sampling rate. That
  warning came from the 10 Hz recordings (median 5.2 at 10 Hz, against 3.2 thinned to 2 Hz), which are not on the
  poster.
  * Here, the 1 Hz drops (M2_aug, M4; 16,560) and the 2 Hz drops (the rest; 12,568) have almost the same native
    steepness: median 2.24 against 2.21, 90th percentile 4.45 against 5.04.
  * Thinning the 2 Hz drops to 1 Hz lowers their median by about 10 % (to 1.99).
  * So the map keeps its axes. The fingerprint's overlap ("the species converge") holds either way.

**Map.** A uniform 20 × 20 grid.
* Down: steepness (the steepest moment ÷ the average slope), from 1× to its 99th percentile.
* Across: time to climb half-way back ÷ fall time, from the 1st to the 99th percentile, plus a "never" column.
* Values beyond either end go in the end cells. Cell colour shows how many drops it holds (log scale). The line is
  the cell's median drop, the band its middle half, and cells with fewer than 6 drops show colour only.
* Badges:
  1. the busiest cell (539 drops);
  2. the busiest "never came back" cell;
  3. needles (bottom left);
  4. wells (a cliff, then a quick return);
  5. the empty corner.

**Species.**
* Fingerprints: each species' 50 % highest-density region on log axes (a KDE with 1.5× Scott's bandwidth, so each
  species is one blob), with its median drop as a dot.
* Box plots: the middle half with the median in white, whiskers at the 5th and 95th percentiles, and a random sample
  of 350 drops per species behind.

**Trains (right half).** The three picks and their framing are the NeurIPS session's (25 Nov).
* CH14 uses that session's own split, imported from `drop_plots_20261123.py` (`kinds_of`). Its mixture model on
  depth and width gives four kinds, and the two big ones are thin (266, 8.7 mV, 6.7 s wide) and wide (225, 12 mV,
  24 s).
  * After a wide drop, the next big drop is thin 69.6 %, against 54.2 % in full shuffles (55.2 % in shuffles
    within blocks of 10, p = 0.00025 with 4,000 shuffles).
  * Switching 64 % against 51 %; wide→wide 0.68×, thin→thin 0.77×.
* Crescendo: seq 119's drops over 10 mV, up to the deepest one.
  * That is 17 drops, so 16 gaps, which the NeurIPS session counts as "16 clean cycles".
* Metronome: seq 129 as listed. Seq 120 holds it, so 120 is not used.
  * The "Clockwork" panel is a tick ruler of the 14 drop times beside 14 random times over the same span (the NeurIPS
    session's suggestion).
  * The random times are a Poisson process with a fixed seed, not one chosen to look clumpy.

**Input from the other sessions (25 Nov).**
* The NeurIPS session picked the three trains and gave the CH14 method and numbers. Its cautions are all respected:
  * 129 is shown, not 120;
  * 123, 122, 125, 126 and 127 are left out;
  * CH14's small drops are not presented;
  * 136's "deeper drop, longer rest" is not quoted;
  * MJu26a appears as one mushroom.
* The Auto-detect session confirmed the datasets and copies and advised the p ≥ 0.8 drops. It also listed the
  caveats now in the footer: about 7 in 10 core drops are real; each species is 1–3 recordings; channels drop
  together.

**Thumbnails.** Ten picked by eye from a contact sheet (`thumb_candidates/contact_sheet.png`) of:
* the hand-labelled and Review-accepted sequences (all on M2_aug);
* machine-found runs of 10 or more poster drops on the other recordings, ranked by steady gaps and alike depths.

The ten are chosen for clear trains, low noise and variety (all five species). Their ids and spans are in
`data/thumbnails.csv`.

## Open questions for the researcher

1. **Is M2_concat oyster or lion's mane?**
   * Plainly: two records disagree about which mushroom one recording came from, like two labels on one jar.
   * The database (your labels of 3 Nov) says lion's mane. The thesis corpus table and the plot style file say
     oyster.
   * The poster leaves it out, which loses about 1,700 drops.
   * Options: (a) tell me which, and I add it back in minutes; (b) keep it out.
   * Recommendation: (a), because the data are good.
2. **"Giant square drops" (lion's mane LM CH2, 18 h, swings of about 170 mV).**
   * It is the most striking thumbnail. Swings that large could also come from an electrode losing and regaining
     contact.
   * Worth one look in Review before the poster goes up. The swap-in candidates are in the contact sheet.
3. **The logo is a placeholder.** It is cropped from the thesis poster image (about 180 px), so it will print soft at
   A1. The original logo is in the Canva design.
4. **Each "species" is one or two cultures.**
   * A difference between species may also reflect how each was grown (grow pack or jar) and when.
   * The footer says so in small print.
   * The Auto-detect session also notes that channels of one array often drop together, so 29,128 drops are not
     29,128 independent events. The poster says "drops found", never "events".
5. **Machine-found drops.** About 1 in 5 of the drops shown may not be real: the verdict model rates each at least
   80 % likely. The footer says so in small print.

## Canva version (25 Nov)

At the researcher's request the poster was rebuilt in Canva, and the text was rewritten in the register of the
thesis poster: uppercase section headers with sentence-case subtitles, colon-led statements, no analogies. The HTML
master carries the same wording.

* **Design:** "The electric pulse of mushrooms – public poster (A1)", id `DAHb5-9OkHM`, 3179 × 2245 px (A1 at 96 px/in).
  * It is an A1 resize of the thesis poster (`DAHYlZx85sw`, unchanged), so it keeps that design's fonts, gradient
    bars, white panels and the original high-resolution logo. Canva's trial left one more resize.
  * The old content was deleted. Every text box is one of the thesis poster's own boxes, re-worded and moved, so the
    fonts match.
  * The nine figures are the 300 dpi PNGs from `figures/`, uploaded as separate images.
* **Editing:** text, colours and positions can be changed in Canva. A figure change means re-running its script here
  and replacing the image there. Edits made in Canva do not flow back to `poster.html`.

## Files

* `data/`: the drop table, the CH14 split, the per-figure JSONs and `numbers.json`.
* `figures/`: every figure as SVG (used by the page) and PNG (300 dpi), the legend icons and the logo crop.
* `thumb_candidates/`: the candidate list and the contact sheet the thumbnails were picked from.
* Code: `scripts/public_poster/`. It reads the pool, the 23 Nov plot tables and the database read-only, and writes
  only this folder.
