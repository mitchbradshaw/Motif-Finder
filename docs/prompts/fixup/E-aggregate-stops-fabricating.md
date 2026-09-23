# Fixup E — Interrogation › Aggregate stops inventing its measurements

**Ready to run.** Highest-value item left: this is the per-event statistics page **both** the
researcher and the supervisor read (`CLAUDE.md`: *where their needs coincide, that path must be the
most reliable in the app*), and three of the numbers on it are constants multiplied by duration and
drawn as measurements.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/prompts/fixup/reports/D-event-features.md`
(**the whole thing** — it built the measurements you are going to use, and its §1 states the exact rule
behind each), `docs/BLOCK_INTEGRATION.md` for the rise-time parameter, and
`docs/prompts/fixup/QUESTIONS.md` Q19.

Commit prefix `fixup-e:`. Test-first; first commit touches only `tests/` and must fail.

## The defect

`webui/client/src/api/interrogation.ts::featureOf`, for the live `spike-shape` upstream:

    half_width_s = duration × 0.84
    rise_s       = duration × 0.31
    isi_s        = duration × 4.2

Three constants, multiplied by a real duration, **rendered as measured features** on the Aggregate
page's relationship plot and distributions. A reader cannot tell them from the real ones beside them.
Worse, they are *plausible* — a scatter of `half_width` against `duration` will show a perfect straight
line at gradient 0.84 and look like a scaling law.

Separately, the same file **computes recovery in the browser** and reports an event that never
recovered as **`0 s`** — indistinguishable from an event that recovered instantly, and at the wrong end
of the distribution.

Prompt `D` found this and deliberately did not fix it: it is page code, and a half-fix puts `NaN` into
React attributes, which the smoke gate reads as console errors. Do it properly here.

## What you have to replace it with

`D` measures all of these for real, and they are already in the database on this machine:
`motif_features` holds **71,980 values over 3,599 content hashes** (50,386 from
`interrogation.event_shape`, 21,594 from the detector), filled by the researcher on 2026-09-24.

Read `D`'s report §1 for the exact rule behind each measure and **carry those rules onto the page**.
`webui/server/interrogation_routes.py:118-123` already prints a `rules` list beside its numbers; that
is the pattern. A measure whose rule is unstated cannot be argued with, and this page has just spent
its credibility.

**Do not recompute anything in the browser.** Every number comes from the core or the table. The
browser-side recovery computation is part of the defect, not a fallback.

## Work (test-first per seam)

### 1. Rise time joins the shape block, as a parameter, null for drops

The researcher's decision (Q19): rise time is the one measure `D` left unmeasured, and it belongs on
`interrogation.event_shape` as a **parameter**, returning **null** for a detected drop event.

**Null, not zero.** A drop has no rise; a rise of zero height is a different statement. `D`'s report
notes `rise_height_mv` is already `0.000` for **85.8 %** of `drop_motifs10` — zero has been doing
double duty as "absent" once in this codebase already and it misled everyone. Make absence explicit and
make every consumer — the page, the table, the distributions — treat null as *not measured* rather than
as a value at the bottom of the range.

Follow `BLOCK_INTEGRATION.md`: a `ParamSpec`, a test in `tests/test_adapter_event_shape.py`, and the
rule in the docstring.

### 2. `featureOf` reads measurements

Delete the three constants. Serve the real values. **Where a measure genuinely is not available for an
event, the page must say so and the event must be absent from that distribution** — not present at a
fabricated value, and not silently dropped without a count. An `n` that changes between panels is
information; state it.

### 3. Recovery comes from the core, and "never recovered" is not zero

`D` defines recovery with `recovery_frac = 0.5` and a bound of 10 event widths, never past the next
window's start. An event that does not recover inside that bound is **not measured**, and must render
as such. Report how many events in the live store are in that class — if it is a large fraction, that
is a finding about the data the researcher needs, not a rendering detail to smooth over.

### 4. The scatter the researcher actually asked for

`D`'s report §8.6 notes the block page draws the feature table, rose and rules but **no scatter**, and
that the Aggregate page is where `width vs recovery` belongs. That relationship — *drop width against
recovery time* — is the concrete thing the researcher named back in round 2. Draw it here, on real
measurements, with the fit and null the page already has machinery for.

Keep it to the relationships the measurements support. **This prompt is not the place to redesign the
page's visual language** — that is prompt `H` (blocks must show their work), and doing it twice
produces two idioms.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **Redesigning how analysis blocks present results** (slideshows of spans, bespoke process views, replacing tables with figures) | Prompt `H`, symptoms U7–U9. One visual idiom, one owner |
| **The plot-domain rule, units, the mV→V core conversion** | `B`/`C` done; the core conversion is Q20's own prompt |
| **Library filters over `motif_features`** (noise floor, `is_pure`, `fall_duration_s`) | Q-X2.5/Q21/Q22, the Library prompt |
| **Fan-out** (Q-B-CHAIN) | deferred by the researcher |
| **Review's pixelation, padding and highlight offset** | prompt `G` |

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` against a `--sandbox` bridge **restarted immediately
beforehand** (and **never while `pytest -n auto` is running** — prompt `B`'s report §9 records 23
spurious smoke failures from that collision); `pytest` against the **1775 passed / 6 skipped / 0
failed** baseline, comparing failure **sets**. FastAPI files under `webui/.venv`, where
`test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` fails pre-existing and
is not yours. Smoke's four Settings registration-state failures are likewise pre-existing.

**Evidence.** A before/after of the Aggregate page into `webui/screenshots/fixup/E/`, and **a table in
your report of every number the page used to invent against what it now measures, for the same
events** — including how far the fabricated value was from the truth. The researcher has been reading
this page; they are owed the size of the error.

## Report

`docs/prompts/fixup/reports/E-aggregate-stops-fabricating.md`: the fabricated-vs-measured table; the
rise-time parameter and how null flows through; how many events do not recover within the bound;
defaults taken; items left; out-of-scope files touched; the gate; a short chat summary.

Then close `03-analyse-interrogation.md` I1–I4 and `QUESTIONS.md` Q19.
