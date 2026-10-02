"""
fixup_k_evidence.py
====================
Evidence for fixup K: where the Slope page's anatomy figure DREW each mark against
where the store's measurement puts it.

Before K the figure took its marks from `fixtures/interrogation.ts::eventMarks` and a
handful of constants in `SlopePage.tsx`:

    steepest   at duration / 2, drawn at a height of -depth / 2
    trough     at fall_duration_s, drawn at a height of -depth
    chord      from (0, the trace at the onset) to (fall_duration_s, -depth)
    tangent    through (duration / 2, -depth / 2) at the measured max slope
    window     10 s before the onset to fall + 14 s after it, whatever the padding

After K every mark is the store's: the detector's `onset_idx` / `trough_idx`, the
sample `gradients.fall_gradients` found steepest (`max_slope_idx`), and the snippet's
own values at those three samples.

    python scripts/fixup_k_evidence.py table            # the drawn-vs-measured table (json + md)
    python scripts/fixup_k_evidence.py shots URL LABEL  # element screenshots of the figure

Reads the tracked seed store only; writes under webui/screenshots/fixup/K/. Dev tooling.
"""
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

SEED_DIR = os.path.join(REPO, "DATA", "library_seed", "drop_motifs5", "motifs")
OUT = os.path.join(REPO, "webui", "screenshots", "fixup", "K")

#: (family, event) pairs the report shows and the screenshots open. The first is the event
#: the page opens on by default (the fourth of id001); the rest are one per morphology and
#: sampling regime, picked before looking at the result.
SHOWN = [
    ("id001", "id001_r1_1216093"),
    ("id001", "id001_r1_1234786"),
    ("id010", None),
    ("id024", None),
    ("id029", None),
    ("id385", None),
]


def measure():
    from Working.Detection.drop_motifs import gradients as G
    from Working.Detection.drop_motifs import store as S

    events = S.load_events(SEED_DIR)
    snips = S.load_snippets(SEED_DIR)
    rows = []
    for e, g in zip(events, G.event_gradients(events, snips)):
        v = np.asarray(snips[e["event_id"]]["detrended_mv"], dtype=float)
        fs = float(e["fs"])
        start = int(e["snippet_start_idx"])
        onset = int(np.clip(int(e["onset_idx"]) - start, 0, len(v) - 1))
        trough = int(np.clip(int(e["trough_idx"]) - start, 0, len(v) - 1))
        steep = g["max_slope_idx"]
        fall = float(e["fall_duration_s"])
        depth = float(e["drop_depth_mv"])
        measured_fall = (trough - onset) / fs
        row = {
            "event_id": e["event_id"],
            "family": e.get("span_key") or f"r{e['recording_id']}",
            "morphology": e.get("morphology"),
            "fs": fs,
            "onset_h": float(e["onset_h"]),
            "fall_s": fall,
            "max_slope_mv_s": g["max_slope_mv_s"],
            # what the page drew
            "drawn_steepest_s": round(fall / 2, 1),
            "drawn_steepest_mv": -depth / 2,
            "drawn_trough_s": fall,
            "drawn_trough_mv": -depth,
            "drawn_window_s": [-10.0, round(fall) + 14.0],
            # what the store measured
            "steepest_s": None if steep is None else (steep - onset) / fs,
            "steepest_mv": None if steep is None else float(v[steep]),
            "trough_s": measured_fall,
            "trough_mv": float(v[trough]),
            "onset_mv": float(v[onset]),
            "stored_window_s": [-onset / fs, (len(v) - 1 - onset) / fs],
        }
        if steep is not None and measured_fall > 0:
            row["steepest_frac_of_fall"] = row["steepest_s"] / measured_fall
            row["steepest_moved_s"] = row["steepest_s"] - row["drawn_steepest_s"]
            row["steepest_moved_mv"] = row["steepest_mv"] - row["drawn_steepest_mv"]
            row["trough_moved_mv"] = row["trough_mv"] - row["drawn_trough_mv"]
        rows.append(row)
    return rows


def _pct(a, q):
    return float(np.percentile(np.asarray(a, dtype=float), q))


def table():
    rows = measure()
    os.makedirs(OUT, exist_ok=True)
    ok = [r for r in rows if "steepest_frac_of_fall" in r]
    frac = [r["steepest_frac_of_fall"] for r in ok]
    moved = [abs(r["steepest_moved_s"]) for r in ok]
    moved_frac = [abs(r["steepest_moved_s"]) / r["trough_s"] for r in ok]
    y_moved = [abs(r["steepest_moved_mv"]) for r in ok]
    onset_mv = [abs(r["onset_mv"]) for r in rows]
    trough_moved = [abs(r["trough_moved_mv"]) for r in ok]
    summary = {
        "n": len(rows), "n_with_a_fall": len(ok), "n_without": len(rows) - len(ok),
        "steepest_frac_of_fall": {"median": _pct(frac, 50), "p10": _pct(frac, 10), "p90": _pct(frac, 90),
                                  "n_within_10pct_of_half": int(sum(abs(f - 0.5) <= 0.1 for f in frac)),
                                  "n_in_first_quarter": int(sum(f <= 0.25 for f in frac)),
                                  "n_in_last_quarter": int(sum(f >= 0.75 for f in frac))},
        "steepest_moved_s": {"median": _pct(moved, 50), "p90": _pct(moved, 90), "max": max(moved)},
        "steepest_moved_frac_of_fall": {"median": _pct(moved_frac, 50), "p90": _pct(moved_frac, 90)},
        "steepest_moved_mv": {"median": _pct(y_moved, 50), "p90": _pct(y_moved, 90)},
        "onset_level_abs_mv": {"median": _pct(onset_mv, 50), "p90": _pct(onset_mv, 90)},
        "trough_moved_mv": {"median": _pct(trough_moved, 50), "p90": _pct(trough_moved, 90)},
        "fall_duration_matches_anchors": int(sum(abs(r["trough_s"] - r["fall_s"]) < 1e-6 for r in rows)),
    }
    by_family = {}
    for r in ok:
        by_family.setdefault((r["family"], r["morphology"]), []).append(r["steepest_frac_of_fall"])
    summary["by_family"] = [{"family": k[0], "morphology": k[1], "n": len(v), "median_frac": _pct(v, 50),
                             "p10": _pct(v, 10), "p90": _pct(v, 90)} for k, v in sorted(by_family.items())]

    shown = []
    for fam, eid in SHOWN:
        pool = [r for r in rows if r["family"] == fam]
        if not pool:
            continue
        if eid is None:      # the page's own default: 4th of a small family, 45th of a large one
            pool.sort(key=lambda r: r["onset_h"])
            shown.append(pool[min(44 if len(pool) > 40 else 3, len(pool) - 1)])
        else:
            shown.append(next(r for r in pool if r["event_id"] == eid))

    with open(os.path.join(OUT, "drawn-vs-measured.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "shown": shown, "events": rows}, f, indent=1)

    lines = ["| event | morphology | fall s | steepest drawn at | steepest measured at | moved | steepest height drawn / measured mV | trough height drawn / measured mV | window drawn | stored context |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in shown:
        lines.append(
            f"| {r['event_id']} | {r['morphology']} | {r['fall_s']:.0f} | +{r['drawn_steepest_s']:.1f} s (50 %) | "
            f"+{r['steepest_s']:.1f} s ({100 * r['steepest_frac_of_fall']:.0f} %) | {r['steepest_moved_s']:+.1f} s | "
            f"{r['drawn_steepest_mv']:.2f} / {r['steepest_mv']:.2f} | {r['drawn_trough_mv']:.2f} / {r['trough_mv']:.2f} | "
            f"{r['drawn_window_s'][0]:.0f} … +{r['drawn_window_s'][1]:.0f} s | {r['stored_window_s'][0]:.0f} … +{r['stored_window_s'][1]:.0f} s |")
    lines += ["", "| family | morphology | n | steepest at, fraction of the fall: median [p10–p90] |", "|---|---|---|---|"]
    for b in summary["by_family"]:
        lines.append(f"| {b['family']} | {b['morphology']} | {b['n']} | {b['median_frac']:.2f} [{b['p10']:.2f}–{b['p90']:.2f}] |")
    with open(os.path.join(OUT, "drawn-vs-measured.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=1))
    print("\n".join(lines))


def shots(url, label):
    from playwright.sync_api import sync_playwright

    targets = SHOWN      # an event of None is the page's own default for that family
    os.makedirs(OUT, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1500, "height": 1100})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        for fam, eid in targets:
            q = f"family={fam}" + (f"&event={eid}" if eid else "")
            page.goto(f"{url}/#/analyse/interrogation/block/1?{q}", wait_until="networkidle")
            page.wait_for_selector('[data-testid="anatomy-plot"] svg', timeout=20000)
            page.wait_for_timeout(600)
            name = f"{label}-anatomy-{eid or fam}.png"
            page.locator('[data-testid="anatomy-card"]').screenshot(path=os.path.join(OUT, name))
            print("wrote", name)
        b.close()
    if errors:
        print("CONSOLE ERRORS:", errors)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "table":
        table()
    elif len(sys.argv) == 4 and sys.argv[1] == "shots":
        shots(sys.argv[2].rstrip("/"), sys.argv[3])
    else:
        print(__doc__)
        sys.exit(2)
