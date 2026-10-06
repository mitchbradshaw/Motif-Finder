"""Smoke test + screenshot capture for the web UI (webui/).

    "/c/ProgramData/anaconda3/python.exe" smoke.py [--url http://127.0.0.1:8765] [--no-run]

Fails (non-zero exit) if:
  * any browser console error or page error occurs on any view (a render error that
    reaches the console is loud by design — the ErrorBoundary logs it);
  * a pane that must paint did not: the corpus heatmap has < 800 filled cells, an
    envelope path has an empty `d`, the chain rows have no plot path/rects/canvas;
  * the server log contains a traceback that was not deliberately provoked;
  * a Must-view flow (open channel → send span → run chain → suffix re-run) breaks.

Screenshots land in screenshots/<nn>-<name>.png, paired to concept frames in REPORT.md.
Uses the repo's Playwright (conda python), not a Node harness.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.environ.get("SMOKE_SHOTS") or os.path.join(HERE, "screenshots")   # two agents' smoke runs must not write the same files

#: Discovery's page states walk live content, so the smoke run first makes two
#: real runs over this section (stage-3 prompt 04). Four hours of two channels
#: is small enough to run in seconds and large enough to have reviewed
#: coverage, which is what gives the scoreboard a denominator.
SMOKE_SECTION_H = (80.0, 84.0)
SMOKE_TEMPLATE = "mp_threshold"
#: fixup-L: the `detection.threshold` value at which the default chain finds spans on the smoke span
#: (recording 4, samples 1002725–1003475): 6.0 → 2 spans, 5.0 → 5, 4.0 → 6 (measured 2026-10-03). The
#: chain's default 8.0 finds none, and *Pass 0 to Review* is rightly grey.
SMOKE_PASS_THRESHOLD = 6.0
#: added but never started, so the Runs page has something pending to route
SMOKE_PENDING_TEMPLATE = "drop_detection_v1"
#: The k the seed page itself asks for (SeedPage.tsx::SEED_K). A result computed
#: under a different k is a different cache key and the page finds nothing.
SMOKE_SEED_K = 200
#: The seed run's key. Pinned so the page states can name it.
SMOKE_SEED_RUN = "smoke_seed"


class Smoke:
    def __init__(self, url: str, run_chain: bool, pages_only: bool = False, only: str | None = None):
        self.url = url.rstrip("/")
        self.run_chain = run_chain
        self.pages_only = pages_only
        self.only = only
        self.errors: list[str] = []
        self.failures: list[str] = []
        self.shots: list[str] = []
        self.evidence: dict = {}
        self.n = 0

    # ------------------------------------------------------------ helpers --
    @staticmethod
    def write_shot(page, path: str, full_page: bool = False):
        """Take a screenshot and write it, retrying the WRITE. The picture is taken once, in memory; only
        putting it on disk is retried. On this machine a write into the tracked screenshot tree fails now
        and then with `[Errno 22] Invalid argument` (a different file each run - something else holds the
        file for a moment), and that used to count as the page state failing although the page had
        rendered and every assertion about it had already passed (fixup-h)."""
        png = page.screenshot(full_page=full_page)
        last = None
        for attempt in range(5):
            try:
                with open(path, "wb") as f:
                    f.write(png)
                return
            except OSError as e:
                last = e
                time.sleep(0.4 * (attempt + 1))
        raise last

    def shot(self, page, name: str):
        self.n += 1
        path = os.path.join(SHOTS, f"{self.n:02d}-{name}.png")
        self.write_shot(page, path)
        if os.path.getsize(path) > 1_000_000:          # gitignore rule: *.big.png
            big = path.replace(".png", ".big.png"); os.replace(path, big); path = big
        self.shots.append(path)
        return path

    def check(self, cond: bool, msg: str):
        if not cond:
            self.failures.append(msg)
            print("  FAIL:", msg)
        else:
            print("  ok:", msg)

    #: JS that measures every `.time-axis` label on the page and returns the
    #: overlapping pairs. `d3`'s `.ticks(n)` picks positions knowing nothing
    #: about how wide `fmtAxis` renders them, and `TimeAxis` used to de-collide
    #: only the two ends and only when `ends` was asked for (fixup-a item 17).
    #: A real browser measurement is the only honest check of a text width.
    _AXIS_OVERLAP_JS = """() => {
      const bad = [];
      for (const g of document.querySelectorAll('g.time-axis')) {
        const boxes = Array.from(g.querySelectorAll('text'))
          .map(t => ({ s: t.textContent, r: t.getBoundingClientRect() }))
          .filter(b => b.r.width > 0)
          .sort((a, b) => a.r.left - b.r.left);
        for (let i = 1; i < boxes.length; i++) {
          if (boxes[i].r.left < boxes[i - 1].r.right - 0.5) {
            bad.push(boxes[i - 1].s + ' | ' + boxes[i].s);
          }
        }
      }
      return bad;
    }"""

    def axis_labels(self, page, where: str):
        """No two time-axis labels may overlap, on any surface (fixup-a 17)."""
        bad = page.evaluate(self._AXIS_OVERLAP_JS)
        n = page.evaluate("() => document.querySelectorAll('g.time-axis text').length")
        self.evidence[f"axis_labels_{where}"] = {"labels": n, "overlaps": bad[:8]}
        self.check(not bad, f"{where}: {n} time-axis labels, none overlapping" + (f" — {bad[:4]}" if bad else ""))

    #: JS that measures every trace against its plot box (fixup-c's acceptance test: no motif is clipped in its
    #: own thumbnail). `MiniTrace` used to clamp silently, so a trace past its domain ran along the frame and
    #: read as data; it no longer clamps, and every plot marks its box (`[data-plot-box]`, the svg itself for a
    #: MiniTrace, the ground rect for a Trace) and its traces (`[data-trace]`). A path's client rect is its
    #: geometry, unclipped by the svg, so a trace drawn off its domain is measured as leaving the box.
    _TRACES_IN_BOX_JS = """() => {
      const out = { traces: 0, outside: [] };
      for (const svg of document.querySelectorAll('svg')) {
        const box = svg.hasAttribute('data-plot-box') ? svg : svg.querySelector('[data-plot-box]');
        if (!box) continue;
        const b = box.getBoundingClientRect();
        if (b.width === 0 || b.height === 0) continue;
        for (const g of svg.querySelectorAll('[data-trace]')) {
          for (const p of g.querySelectorAll('path')) {
            const r = p.getBoundingClientRect();
            if (!(p.getAttribute('d') || '') || (r.width === 0 && r.height === 0)) continue;
            out.traces++;
            if (r.top < b.top - 1 || r.bottom > b.bottom + 1 || r.left < b.left - 1 || r.right > b.right + 1) {
              const host = svg.closest('[data-testid]');
              out.outside.push(((host && host.getAttribute('data-testid')) || 'svg') + ' '
                + Math.round(r.top - b.top) + '/' + Math.round(b.bottom - r.bottom));
            }
          }
        }
      }
      return out;
    }"""

    #: fixup-g: the Review context card's trace and its highlight band are in ONE coordinate system. Before,
    #: the bridge served a decimated envelope's values without its `t` and the client drew them one per second
    #: while the band was drawn in true seconds, so detection 102's drop was drawn a third of the way early and
    #: the band appeared to miss it (U2). This measures the DOM: the trace path's lowest vertex against the band
    #: rect (`feature_in_band`, for an item whose event IS the window's minimum), and the band's distance from
    #: each edge of the plot (`band_centred`, the padding is symmetric — U3).
    _CONTEXT_AXIS_JS = """() => {
      const host = document.querySelector('[data-testid="context-trace"]');
      if (!host) return { error: 'no context trace' };
      const svg = host.querySelector('svg');
      const boxEl = svg && svg.querySelector('[data-plot-box]');
      const band = svg && svg.querySelector('.span-bands rect');
      const path = svg && svg.querySelector('[data-trace] > path:last-of-type');
      if (!boxEl || !band || !path) return { error: 'context trace has no ' + (!boxEl ? 'plot box' : !band ? 'band' : 'path') };
      const box = boxEl.getBoundingClientRect(), br = band.getBoundingClientRect();
      const pts = Array.from((path.getAttribute('d') || '').matchAll(/[ML]([-\\d.]+) ([-\\d.]+)/g)).map(m => [parseFloat(m[1]), parseFloat(m[2])]);
      let low = null; for (const p of pts) if (!low || p[1] > low[1]) low = p;
      const sr = svg.getBoundingClientRect();
      return { points: pts.length, lowestX: low ? low[0] + sr.left : null, bandLeft: br.left, bandRight: br.right,
               padLeft: br.left - box.left, padRight: box.right - br.right, timed: svg.getAttribute('data-timed') };
    }"""

    def context_axis(self, page, e: dict, where: str):
        """`feature_in_band`: the context trace's lowest vertex lies inside the band. `band_centred`: the band
        is the same distance from both edges of the plot (within 2 px, or 1.5 % of the plot)."""
        want_feature, want_centred = bool(e.get("feature_in_band")), bool(e.get("band_centred"))
        if not (want_feature or want_centred):
            return True, ""
        m = page.evaluate(self._CONTEXT_AXIS_JS)
        self.evidence.setdefault("context_axis", {})[where] = m
        if m.get("error"):
            return False, f" — {m['error']}"
        msgs, ok = [], True
        if want_feature:
            inside = m["lowestX"] is not None and m["bandLeft"] - 1 <= m["lowestX"] <= m["bandRight"] + 1
            ok &= inside
            msgs.append(" · the trace's minimum sits inside the band" if inside else
                        f" — the trace's minimum is drawn at x={m['lowestX']}, outside the band [{m['bandLeft']:.0f}, {m['bandRight']:.0f}]")
        if want_centred:
            tol = max(2.0, 0.015 * (m["padLeft"] + m["padRight"] + (m["bandRight"] - m["bandLeft"])))
            centred = abs(m["padLeft"] - m["padRight"]) <= tol
            ok &= centred
            msgs.append(" · padding symmetric" if centred else
                        f" — padding is one-sided: {m['padLeft']:.0f} px left, {m['padRight']:.0f} px right")
        return bool(ok), "".join(msgs)

    def traces_in_box(self, page, where: str):
        """No trace's rendered path leaves its plot box (fixup-c)."""
        m = page.evaluate(self._TRACES_IN_BOX_JS)
        self.evidence.setdefault("traces_in_box", {})[where] = {"traces": m["traces"], "outside": m["outside"][:8]}
        return m["traces"] > 0 and not m["outside"], (
            f" — {m['traces']} traces measured" if m["traces"] == 0 else
            f" — {len(m['outside'])} of {m['traces']} traces leave their plot box: {m['outside'][:4]}" if m["outside"] else "")

    #: fixup-k: the Slope page's anatomy figure, measured in the browser against the payload it claims to draw.
    #: The marker lines are found by their stroke, the tangent and the chord by theirs; everything is compared
    #: in pixels and as ratios, so no axis scale has to be recovered from the DOM.
    _ANATOMY_MARKS_JS = """async () => {
      const fig = document.querySelector('[data-testid="anatomy-figure"]');
      const svg = fig && fig.querySelector('svg');
      if (!svg) return { error: 'no anatomy figure on the page' };
      const fam = fig.getAttribute('data-family'), ev = fig.getAttribute('data-event');
      const res = await fetch('/api/interrogation/families/' + encodeURIComponent(fam) + '/slope');
      if (!res.ok) return { error: 'slope route answered ' + res.status };
      const m = (await res.json()).members.find(x => x.event_id === ev);
      if (!m) return { error: 'event ' + ev + ' is not in the slope payload of ' + fam };
      const vline = c => { const l = Array.from(svg.querySelectorAll('line')).find(l => l.getAttribute('stroke') === c && l.getAttribute('x1') === l.getAttribute('x2')); return l ? parseFloat(l.getAttribute('x1')) : null; };
      const seg = c => { const p = svg.querySelector('path[stroke="' + c + '"]'); if (!p) return null;
        const pts = Array.from((p.getAttribute('d') || '').matchAll(/[ML]([-\\d.]+) ([-\\d.]+)/g)).map(q => [parseFloat(q[1]), parseFloat(q[2])]);
        return pts.length === 2 ? pts : null; };
      return { event: ev, family: fam, onsetX: vline('var(--blue)'), steepestX: vline('#7446E0'), troughX: vline('var(--red)'),
               tangent: seg('#7446E0'), chord: seg('#9ca3af'),
               served: { onset: m.onset_offset, steepest: m.steepest_offset, trough: m.trough_offset,
                         max_slope: m.max_slope_mv_s, chord_slope: m.mean_slope_mv_s } };
    }"""

    def anatomy_marks(self, page, where: str):
        """`anatomy_marks`: every mark of the Slope page's anatomy figure is where the served payload puts it.
        The steepest marker divides onset..trough in the served ratio (within 1.5 px), the chord runs from the
        onset marker to the trough marker, and the tangent passes through the steepest marker with a slope that
        stands to the chord's as the served `max_slope_mv_s` stands to the served chord slope."""
        m = page.evaluate(self._ANATOMY_MARKS_JS)
        self.evidence.setdefault("anatomy_marks", {})[where] = m
        if m.get("error"):
            return False, f" — {m['error']}"
        need = [k for k in ("onsetX", "steepestX", "troughX", "tangent", "chord") if m.get(k) is None]
        if need:
            return False, f" — the figure draws no {need}"
        sv = m["served"]
        if sv["steepest"] is None or sv["trough"] <= sv["onset"]:
            return False, " — the payload has no steepest sample or no fall for this event, and the figure drew marks anyway"
        fall_px = m["troughX"] - m["onsetX"]
        want = m["onsetX"] + fall_px * (sv["steepest"] - sv["onset"]) / (sv["trough"] - sv["onset"])
        msgs, ok = [], True
        at = abs(m["steepestX"] - want) <= 1.5
        ok &= at
        msgs.append(f" · steepest drawn at {100 * (m['steepestX'] - m['onsetX']) / fall_px:.0f} % of the fall, as served" if at else
                    f" — steepest drawn at x={m['steepestX']:.1f}, the payload puts it at x={want:.1f} "
                    f"({100 * (sv['steepest'] - sv['onset']) / (sv['trough'] - sv['onset']):.0f} % of the fall)")
        (cx0, cy0), (cx1, cy1) = m["chord"]
        chord_ok = abs(cx0 - m["onsetX"]) <= 1 and abs(cx1 - m["troughX"]) <= 1
        ok &= chord_ok
        if not chord_ok:
            msgs.append(f" — the chord runs x={cx0:.1f}..{cx1:.1f}, not onset {m['onsetX']:.1f} .. trough {m['troughX']:.1f}")
        (tx0, ty0), (tx1, ty1) = m["tangent"]
        through = tx0 - 1 <= m["steepestX"] <= tx1 + 1
        # pixel slopes share one pair of axes, so their ratio is the ratio of the mV/s slopes
        want_dy = (cy1 - cy0) / (cx1 - cx0) * (sv["max_slope"] / sv["chord_slope"]) * (tx1 - tx0) if cx1 != cx0 and sv["chord_slope"] else None
        slope_ok = want_dy is not None and abs((ty1 - ty0) - want_dy) <= 1.0 + 0.05 * abs(want_dy)
        ok &= through and slope_ok
        msgs.append(" · tangent through it at the served slope" if through and slope_ok else
                    f" — the tangent x={tx0:.1f}..{tx1:.1f} misses the steepest marker at {m['steepestX']:.1f}" if not through else
                    f" — the tangent falls {ty1 - ty0:.1f} px where the served max slope gives {want_dy if want_dy is None else round(want_dy, 1)} px")
        return bool(ok), "".join(msgs)

    #: fixup-h: RULE 9 of `Pipelines/drop_motifs/drawing_rules.py` ("a drop must look like a drop", `check_drop_shape`),
    #: ported to the browser. The thesis rule measures a figure's height-to-width against the median event; a UI
    #: plot is not aspect-locked, so the port keeps what the rule is FOR and measures it on what was drawn. Every
    #: view marks its plot (`svg[data-rule9]`) and its traces (`[data-trace] path`), and for each trace:
    #:   * it VARIES - the path has more than one distinct y;
    #:   * it is NOT FLATTENED - its drawn height is at least `RULE9_MIN_FILL` of its plot's height. A trace drawn
    #:     on a domain much wider than itself (a shared y, a stale domain, an offset left in) is the flat-line
    #:     failure the rule exists to stop. A plot whose DATA is constant says so (`data-flat="1"`) and is exempt:
    #:     a flat line is then the honest picture, and the exemption is the view's claim about its payload;
    #:   * NO AXIS CLIPS IT - every vertex lies inside the plot.
    #: A page with no rule-9 plot at all fails too: the check must have something to measure.
    RULE9_MIN_FILL = 0.2
    _RULE9_JS = """(minFill) => {
      const out = { plots: 0, traces: 0, exempt: 0, constant: [], flat: [], clipped: [] };
      for (const svg of document.querySelectorAll('svg[data-rule9]')) {
        const b = svg.getBoundingClientRect();
        if (b.width === 0 || b.height === 0) continue;
        out.plots++;
        const host = svg.closest('[data-testid]');
        const name = ((host && host.getAttribute('data-testid')) || 'svg') + ':' + svg.getAttribute('data-rule9');
        if (svg.getAttribute('data-flat') === '1') { out.exempt++; continue; }
        for (const p of svg.querySelectorAll('[data-trace] path')) {
          const ys = Array.from((p.getAttribute('d') || '').matchAll(/[ML]([-\\d.]+) ([-\\d.]+)/g)).map(m => parseFloat(m[2]));
          if (ys.length < 2) continue;
          out.traces++;
          const r = p.getBoundingClientRect();
          if (Math.max(...ys) - Math.min(...ys) < 0.5) { out.constant.push(name); continue; }
          if (r.height / b.height < minFill) out.flat.push(name + ' ' + Math.round(100 * r.height / b.height) + '%');
          if (r.top < b.top - 1.5 || r.bottom > b.bottom + 1.5) out.clipped.push(name + ' ' + Math.round(r.top - b.top) + '/' + Math.round(b.bottom - r.bottom));
        }
      }
      return out;
    }"""

    def rule9(self, page, where: str):
        """`rule9`: every drawn trace varies, is not flattened, and is not clipped by its axis."""
        m = page.evaluate(self._RULE9_JS, self.RULE9_MIN_FILL)
        self.evidence.setdefault("rule9", {})[where] = {k: (v if isinstance(v, int) else v[:8]) for k, v in m.items()}
        bad = []
        if m["traces"] == 0:
            bad.append(f"no trace to measure ({m['plots']} rule-9 plots, {m['exempt']} declared flat)")
        if m["constant"]:
            bad.append(f"{len(m['constant'])} traces do not vary: {m['constant'][:3]}")
        if m["flat"]:
            bad.append(f"{len(m['flat'])} traces are flattened below {int(100 * self.RULE9_MIN_FILL)} % of their plot: {m['flat'][:3]}")
        if m["clipped"]:
            bad.append(f"{len(m['clipped'])} traces are clipped by their axis: {m['clipped'][:3]}")
        return not bad, (f" · rule 9: {m['traces']} traces vary, fill their plots, unclipped" if not bad else " — rule 9: " + "; ".join(bad))

    #: fixup-ac: a wavelet decomposition's layers are SAMPLE-ALIGNED with the recording (a stationary transform), and
    #: the block page draws them stacked on one time axis. Measured the way fixup-g's `feature_in_band` is, on the DOM.
    #: The DROP is the fall on the input row: its lowest vertex (the trough) and the highest vertex in the twentieth of
    #: the plot before it (the onset). The layers that CARRY it are the detail layers fine enough to resolve it (an
    #: octave time scale, 2^level samples, no longer than the fall) in which it is a prominent feature (their deepest
    #: vertex near the fall in the bottom 40 % of their own row). Each must have that deepest vertex INSIDE the fall,
    #: give or take its own time scale. A fast layer marks the steepest part of a fall, not its bottom, so a single
    #: vertex is the wrong target; and a slower layer's trough is wider than any offset worth catching. A padding or
    #: span-offset bug would put the carrying layers minutes away. The residual carries the trend and is left out.
    _LAYERS_ALIGNED_JS = r"""() => {
      const host = document.querySelector('[data-testid="wavelet-layers"]');
      if (!host) return { error: 'no wavelet layers on the page' };
      const [xd0, xd1] = host.getAttribute('data-x-domain').split(',').map(Number);
      const [xr0, xr1] = host.getAttribute('data-x-range').split(',').map(Number);
      const fs = Number(host.getAttribute('data-fs'));
      const pxPerS = (xr1 - xr0) / (xd1 - xd0), tOf = px => xd0 + (px - xr0) / pxPerS;
      const rows = Array.from(host.querySelectorAll('svg[data-render="signal-layer"]'));
      const pts = s => { const p = s.querySelector('[data-trace] path');
        return Array.from(((p && p.getAttribute('d')) || '').matchAll(/[ML]([-\d.]+) ([-\d.]+)/g)).map(m => [parseFloat(m[1]), parseFloat(m[2])]); };
      const input = rows.find(s => s.getAttribute('data-input') === '1');
      if (!input) return { error: 'the layers have no input row' };
      const I = pts(input);
      let trough = null; for (const q of I) if (!trough || q[1] > trough[1]) trough = q;
      if (!trough) return { error: 'the input row drew nothing' };
      const width = xr1 - xr0, look = 0.05 * width;
      let onset = trough; for (const q of I) if (q[0] >= trough[0] - look && q[0] <= trough[0] && q[1] < onset[1]) onset = q;
      const fallS = (trough[0] - onset[0]) / pxPerS;
      const out = { onsetT: tOf(onset[0]), troughT: tOf(trough[0]), fallS: +fallS.toFixed(1), fs, layers: [] };
      for (const s of rows) {
        const level = Number(s.getAttribute('data-level'));
        if (s.getAttribute('data-input') === '1' || !(level > 0)) continue;
        const scaleS = Math.pow(2, level) / fs, tolPx = Math.max(2, scaleS * pxPerS);
        const [r0, r1] = s.getAttribute('data-y-range').split(',').map(Number);   // [bottom px, top px]
        const P = pts(s); if (!P.length) continue;
        const lo = onset[0] - (trough[0] - onset[0]) - tolPx, hi = trough[0] + (trough[0] - onset[0]) + tolPx;
        let loc = null; for (const q of P) if (q[0] >= lo && q[0] <= hi && (!loc || q[1] > loc[1])) loc = q;
        const depth = loc ? (loc[1] - r1) / (r0 - r1) : 0;                            // 0 at the row's top, 1 at its bottom
        const resolves = scaleS <= Math.max(fallS, 2 / pxPerS);
        out.layers.push({ layer: s.getAttribute('data-layer'), level, scaleS, depth: +depth.toFixed(3), resolves,
                          carries: resolves && depth >= 0.6, atT: loc ? +tOf(loc[0]).toFixed(1) : null,
                          aligned: !!loc && loc[0] >= onset[0] - tolPx && loc[0] <= trough[0] + tolPx });
      }
      return out;
    }"""

    def layers_aligned(self, page, where: str):
        """`layers_aligned`: every detail layer that carries the input's deepest fall has its deepest vertex inside
        that fall, give or take its own octave's time scale."""
        m = page.evaluate(self._LAYERS_ALIGNED_JS)
        self.evidence.setdefault("layers_aligned", {})[where] = m
        if m.get("error"):
            return False, f" — {m['error']}"
        carriers = [L for L in m["layers"] if L["carries"]]
        off = [L for L in carriers if not L["aligned"]]
        fall = f"the fall {m['onsetT'] / 3600:.3f}–{m['troughT'] / 3600:.3f} h ({m['fallS']:.0f} s)"
        if not carriers:
            return False, f" — no detail layer carries {fall}: {[(L['layer'], L['resolves'], L['depth']) for L in m['layers']]}"
        if off:
            return False, f" — layers drawn off {fall}: " + ", ".join(f"{L['layer']} at {L['atT']} s" for L in off)
        return True, f" · {fall} sits at the same time on the {len(carriers)} layers that carry it ({', '.join(L['layer'] for L in carriers)})"

    def goto(self, page, hash_: str, settle_ms=600):
        page.goto(f"{self.url}/#/{hash_}", wait_until="networkidle")
        page.wait_for_timeout(settle_ms)

    # --------------------------------------------------------------- views --
    def corpus(self, page):
        print("[corpus]")
        self.goto(page, "explore/corpus", 1200)
        page.wait_for_selector('[data-testid="corpus-heatmap"]', timeout=20000)
        cells = page.locator('[data-testid="heatmap-cell"]')
        n = cells.count()
        filled = page.evaluate("""() => Array.from(document.querySelectorAll('[data-testid="heatmap-cell"]')).filter(r => { const f = getComputedStyle(r).fill || r.getAttribute('fill'); return f && f !== 'none' }).length""")
        distinct = page.evaluate("""() => new Set(Array.from(document.querySelectorAll('[data-testid="heatmap-cell"]')).map(r => r.getAttribute('fill') || getComputedStyle(r).fill)).size""")
        self.evidence["heatmap_cells"] = n; self.evidence["heatmap_distinct_fills"] = distinct
        self.check(n >= 16 * 28, f"heatmap has {n} cells (>= 448)")
        self.check(filled >= 800, f"heatmap painted {filled} cells (>= 800)")
        self.check(distinct >= 3, f"heatmap uses {distinct} distinct fills (>= 3, i.e. real counts, not one colour)")
        self.check(page.locator('[data-testid="nav-rail"]').count() == 1, "nav rail present")
        self.check(page.locator('[data-testid="header"]').count() == 1, "header present")
        self.axis_labels(page, "corpus")

        # fixup-a 6: "N need you" is the live route's number, never a constant.
        # The chip adds this tab's failed runs to it, so the chip's own title
        # carries the review figure apart and THAT is what is compared.
        need = page.locator('[data-testid="need-you"]')
        self.check(need.count() == 1, "the header's need-you chip is present")
        if need.count():
            title = need.first.get_attribute("title") or ""
            counts = json.load(__import__("urllib.request").request.urlopen(self.url + "/api/review/counts"))
            live = int(counts.get("need_you") or 0)
            said = int(re.match(r"\s*(\d+)", title).group(1)) if re.match(r"\s*(\d+)", title) else -1
            self.evidence["need_you"] = {"route": live, "header": said, "chip": need.first.inner_text().strip()}
            self.check(said == live, f"the header's review count is /api/review/counts ({said} vs {live})")

        # fixup-a 13/14: the rail's tag filter is a MultiPick over the LIVE
        # vocabulary, and nothing on this page claims the database has no tags
        rail = page.locator('[data-testid="corpus-rail"]')
        rail_txt = rail.inner_text().lower() if rail.count() else ""
        self.check("no tags in this database" not in rail_txt and "has no tags" not in rail_txt,
                   "the rail no longer claims this database has no tags")
        self.check(rail.count() == 1 and rail.locator('[data-testid="demo-tag"]').count() == 0,
                   "no demo chip is left on the Corpus rail (every read on it is live)")
        tagpick = page.locator('[data-testid="rail-tags"]')
        self.check(tagpick.count() == 1, "the Morphology tag filter is the rail's MultiPick, not 36 checkboxes")
        self.shot(page, "explore-1-corpus")
        if tagpick.count():
            tagpick.first.click(); page.wait_for_timeout(400)
            opts = page.locator('[data-testid^="rail-tags-opt-"]').count()
            self.evidence["rail_tag_terms"] = opts
            self.check(opts >= 10, f"the tag list offers {opts} live vocabulary terms")
            # no screenshot here on purpose: the flow shots are numbered and REPORT.md
            # pairs them to concept frames, so inserting one renumbers twenty files.
            # The assertion above is the pin; the page walk has the rail's own state.
            page.keyboard.press("Escape"); page.wait_for_timeout(300)
        # colour-by toggle
        for label in ("detections", "disagree", "both"):
            b = page.get_by_role("button", name=re.compile(rf"^{label}$", re.I))
            if b.count():
                b.first.click(); page.wait_for_timeout(500)
        self.shot(page, "explore-1-corpus-colour-by")
        # select a channel row
        row = page.locator('[data-testid="heatmap-row-CH4_A2"]')
        if row.count():
            row.first.locator('[data-testid="heatmap-cell"]').first.click(); page.wait_for_timeout(400)
        bar = page.locator('[data-testid="corpus-bottom-bar"]')
        self.check(bar.count() == 1 and "annotations" in bar.inner_text().lower(), "bottom bar shows channel counts")
        self.shot(page, "explore-1-corpus-selected")
        open_btn = page.locator('[data-testid="open-channel"]')
        self.check(open_btn.count() == 1, "Open channel button present")
        open_btn.first.click()
        page.wait_for_timeout(1500)

    def signal(self, page):
        print("[signal]")
        if "explore/signal" not in page.url:
            self.goto(page, "explore/signal/4", 1500)
        page.wait_for_selector('[data-testid="signal-overview"]', timeout=20000)
        page.wait_for_timeout(1200)
        d_len = page.evaluate("""() => [document.querySelector('[data-testid="signal-overview"] path[d]'), document.querySelector('[data-testid="signal-span"] path[d], [data-testid="envelope-path"]')].map(p => p ? (p.getAttribute('d')||'').length : 0)""")
        self.evidence["envelope_path_lengths"] = d_len
        self.check(len(d_len) == 2 and all(l > 500 for l in d_len), f"overview + span envelope paths painted (d lengths {d_len})")
        bands = page.locator('[data-testid="span-bands"] rect').count()
        self.evidence["span_bands"] = bands
        self.check(bands >= 1, f"{bands} tinted span bands drawn in the viewport")
        self.axis_labels(page, "signal")
        self.shot(page, "explore-2-signal")
        # zoom in with the wheel over the span plot, measuring the latency instrumentation
        box = page.locator('[data-testid="signal-span"]').bounding_box()
        if box:
            cx, cy = box["x"] + box["width"] * 0.55, box["y"] + box["height"] * 0.5
            page.mouse.move(cx, cy)
            for _ in range(8):
                page.mouse.wheel(0, -240); page.wait_for_timeout(120)
            page.wait_for_timeout(700)
            # pan
            page.mouse.move(cx, cy); page.mouse.down(); page.mouse.move(cx - 200, cy, steps=8); page.mouse.up()
            page.wait_for_timeout(700)
        stats = page.evaluate("() => window.__zoomStats || []")
        self.evidence["zoom_stats"] = stats[-12:]
        self.check(len(stats) >= 2, f"viewport refetch instrumentation recorded {len(stats)} fetches")
        if stats:
            rts = [s.get("round_trip_ms", 0) for s in stats]
            self.evidence["zoom_round_trip_ms"] = {"min": min(rts), "max": max(rts), "median": sorted(rts)[len(rts) // 2]}
        self.shot(page, "explore-2-signal-zoomed")
        # select a motif via next-motif button
        nxt = page.locator('[data-testid="motif-next"]')
        if nxt.count():
            nxt.first.click(); page.wait_for_timeout(900)
        self.check(page.locator('[data-testid="signal-motif"]').count() == 1, "motif tier present")
        self.shot(page, "explore-2-signal-motif")
        # send span to analyse
        send = page.locator('[data-testid="send-span"]')
        self.check(send.count() == 1, "Send span to Analyse present")
        send.first.click(); page.wait_for_timeout(1200)
        self.check("analyse" in page.url, "sending a span navigates to Analyse")

    def m4(self, page):
        print("[held-out]")
        self.goto(page, "explore/signal/52", 1200)
        txt = page.locator("body").inner_text()
        self.check("held out" in txt.lower(), "M4 channel shows a held-out / locked state")
        self.shot(page, "explore-m4-held-out")

    def analyse(self, page):
        print("[analyse]")
        self.goto(page, "analyse/chain", 1500)
        page.wait_for_selector('[data-testid="chain-page"]', timeout=20000)
        page.wait_for_timeout(800)
        rows = page.locator('[data-testid^="chain-row-"]').count()
        self.check(rows >= 4, f"{rows} chain rows (source + 3 steps)")
        # the axis primitive is shared with Explore, so both workspaces check it
        self.axis_labels(page, "analyse-chain")
        self.shot(page, "chain-1-chain-before-run")
        # insert modal
        ins = page.locator('[data-testid="insert-2"]')
        if ins.count():
            ins.first.click(); page.wait_for_timeout(700)
            self.check(page.locator('[data-testid="insert-modal"]').count() == 1, "insert-stage modal opens")
            cards = page.locator('[data-testid^="modal-card-"]').count()
            self.check(cards >= 20, f"modal lists {cards} adapters")
            disabled = page.evaluate("""() => Array.from(document.querySelectorAll('[data-testid^="modal-card-"]')).filter(c => c.disabled || c.getAttribute('aria-disabled') === 'true' || /nofit|disabled|unfit/.test(c.className)).length""")
            self.check(disabled >= 10, f"{disabled} incompatible adapters shown disabled with reasons")
            self.shot(page, "chain-2-insert-stage")
            page.keyboard.press("Escape"); page.wait_for_timeout(300)
            if page.locator('[data-testid="insert-modal"]').count():
                page.get_by_role("button", name=re.compile("cancel", re.I)).first.click(); page.wait_for_timeout(300)
        if not self.run_chain:
            return
        run = page.locator('[data-testid="run-button"]')
        self.check(run.count() == 1 and run.first.is_enabled(), "run button present and enabled")
        t = time.time(); run.first.click()
        # wait for completion: the terminal footer says "last run" or a failure
        for _ in range(120):
            page.wait_for_timeout(250)
            ft = page.locator('[data-testid="footer-terminal"]').inner_text().lower() if page.locator('[data-testid="footer-terminal"]').count() else ""
            if "last run" in ft or "no result" in ft or "failed" in ft:
                break
        self.evidence["run_wall_s"] = round(time.time() - t, 2)
        badges = [page.locator(f'[data-testid="row-badge-{i}"]').inner_text().strip() for i in range(1, 4) if page.locator(f'[data-testid="row-badge-{i}"]').count()]
        self.evidence["badges_after_run"] = badges
        self.check(all(("cached" in b.lower() or "done" in b.lower()) for b in badges) and len(badges) == 3, f"all rows completed: {badges}")
        painted = page.evaluate("""() => [1,2,3].map(i => { const el = document.querySelector('[data-testid="row-plot-'+i+'"]'); if (!el) return 'missing'; const p = el.querySelector('path[d]'); const r = el.querySelectorAll('rect').length; const c = el.querySelector('canvas'); return (p && p.getAttribute('d').length > 200) ? 'path' : r > 2 ? 'rects' : c ? 'canvas' : 'blank' })""")
        self.evidence["row_plots"] = painted
        self.check(all(p != "blank" and p != "missing" for p in painted), f"every result row painted something: {painted}")
        self.shot(page, "chain-1-chain-completed")
        self.pass_to_review(page)
        # block page for the threshold (step index 2) with a draggable line
        page.locator('[data-testid="settings-step-3"]').first.click() if page.locator('[data-testid="settings-step-3"]').count() else self.goto(page, "analyse/block/2", 800)
        page.wait_for_timeout(900)
        self.check(page.locator('[data-testid="block-page"]').count() == 1, "block page opens")
        line = page.locator('[data-testid="threshold-line"]')
        self.check(line.count() >= 1, "draggable threshold line present")
        self.shot(page, "chain-7b-block-threshold")
        if line.count():
            b = line.first.bounding_box()
            if b:
                page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2); page.mouse.down()
                page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2 - 30, steps=6); page.mouse.up()
                page.wait_for_timeout(600)
        self.shot(page, "chain-7b-block-threshold-dragged")
        # back to chain: rows 1,2 should be cached, 3 stale; re-run → suffix cache hit
        self.goto(page, "analyse/chain", 900)
        badges = [page.locator(f'[data-testid="row-badge-{i}"]').inner_text().strip().lower() for i in range(1, 4) if page.locator(f'[data-testid="row-badge-{i}"]').count()]
        self.evidence["badges_after_edit"] = badges
        self.check(len(badges) == 3 and "stale" in badges[2], f"editing the threshold marked row 3 stale: {badges}")
        run = page.locator('[data-testid="run-button"]')
        run.first.click()
        for _ in range(80):
            page.wait_for_timeout(250)
            ft = page.locator('[data-testid="footer-terminal"]').inner_text().lower() if page.locator('[data-testid="footer-terminal"]').count() else ""
            if "last run" in ft or "no result" in ft:
                break
        page.wait_for_timeout(400)
        badges = [page.locator(f'[data-testid="row-badge-{i}"]').inner_text().strip().lower() for i in range(1, 4)]
        titles = [page.locator(f'[data-testid="row-badge-{i}"]').get_attribute("title") or "" for i in range(1, 4)]
        self.evidence["badges_after_rerun"] = badges; self.evidence["badge_titles_after_rerun"] = titles
        self.check("cached" in badges[0] and "cached" in badges[1], f"prefix rows cached after suffix re-run: {badges}")
        self.check(any("0.0" in (b + t) or "0 s" in (b + t) for b, t in zip(badges[:2], titles[:2])), f"prefix rows report 0 s core timings: {list(zip(badges[:2], titles[:2]))}")
        self.shot(page, "chain-1-chain-suffix-rerun")
        # history popover
        h = page.locator('[data-testid="history-button"]')
        if h.count():
            h.first.click(); page.wait_for_timeout(700)
            self.check(page.locator('[data-testid="history-popover"]').count() == 1, "history popover opens")
            self.shot(page, "chain-1b-run-history")
            page.keyboard.press("Escape"); page.wait_for_timeout(300)
        # invalid junction: delete step 2 (matrix profile)
        d = page.locator('[data-testid="delete-step-2"]')
        if d.count():
            d.first.click(); page.wait_for_timeout(900)
            self.check(page.locator('[data-testid="junction-error"]').count() >= 1, "deleting the Scores producer shows the red junction")
            self.shot(page, "chain-1e-invalid-junction")
            undo = page.get_by_role("button", name=re.compile("undo", re.I))
            if undo.count():
                undo.first.click(); page.wait_for_timeout(700)
        # failed block: window_min too long, via the block page param
        self.goto(page, "analyse/block/1", 900)
        p = page.locator('input[data-testid="param-window_min"], [data-testid="param-window_min"] input[type=number]')
        if p.count():
            p.first.fill("500"); p.first.press("Enter"); page.wait_for_timeout(500)
            self.goto(page, "analyse/chain", 800)
            page.locator('[data-testid="run-button"]').first.click()
            for _ in range(80):
                page.wait_for_timeout(250)
                if page.locator('[data-testid="error-card"]').count():
                    break
            page.wait_for_timeout(300)
            self.check(page.locator('[data-testid="error-card"]').count() >= 1, "failed block shows an error card in place of the plot")
            self.shot(page, "chain-1f-failed-block")
            # restore
            self.goto(page, "analyse/block/1", 900)
            p = page.locator('input[data-testid="param-window_min"], [data-testid="param-window_min"] input[type=number]')
            p.first.fill("1"); p.first.press("Enter"); page.wait_for_timeout(400)
        # running state: seed a 20 h source span (72,000 samples, under MP's 80,527 ceiling; MP takes ~3 s)
        page.evaluate("""() => sessionStorage.setItem('ub-proto-a:source', JSON.stringify({recording_id: 4, channel_name: 'CH4_A2', source_file: 'M2_aug_concat_fs1.mat', fs: 1, start_idx: 995040, end_idx: 1067040, label: 'smoke 20 h span'}))""")
        page.reload(wait_until="networkidle"); page.wait_for_timeout(1200)
        run = page.locator('[data-testid="run-button"]')
        if run.count() and run.first.is_enabled():
            run.first.click(); page.wait_for_timeout(700)
            self.shot(page, "chain-1d-running")
            c = page.locator('[data-testid="cancel-button"]')
            if c.count():
                c.first.click(); page.wait_for_timeout(1500)
                self.shot(page, "chain-cancelled")
            for _ in range(120):
                page.wait_for_timeout(250)
                if not page.locator('[data-testid="cancel-button"]').count():
                    break
        # restore the example span for anyone using the page after the smoke test
        page.evaluate("""() => sessionStorage.setItem('ub-proto-a:source', JSON.stringify({recording_id: 4, channel_name: 'CH4_A2', source_file: 'M2_aug_concat_fs1.mat', fs: 1, start_idx: 995040, end_idx: 1002240, label: 'example span'}))""")

    def loud_failure(self, page):
        print("[loud failure]")
        self.goto(page, "analyse/chain?throw=1", 1200)
        self.check(page.locator('[data-testid="render-error"]').count() >= 1, "a thrown render error is shown as a red card (not a blank pane)")
        self.check(any("deliberate render failure" in e for e in self.errors), "the thrown render error reached the browser console")
        self.shot(page, "loud-failure-render-error")
        self.errors = [e for e in self.errors if "deliberate render failure" not in e]

    def pass_to_review(self, page):
        """fixup-L: the chain footer's *Pass N to Review* is the slideshow's *Send N to
        Review* on the same run — one call, two buttons — and it opens the queue it made.

        At the chain's default threshold (8.0) the smoke span yields 0 spans, and 0 spans
        is *no spans to review*: the grey button must say so. Then the threshold is set to
        one that finds spans on this span (`SMOKE_PASS_THRESHOLD`, measured 2026-10-03:
        6.0 → 2 spans; 5.0 → 5; 4.0 → 6), the chain re-run, and the button pressed.
        """
        pass_btn = page.locator('[data-testid="pass-to-review"]')
        self.check(pass_btn.count() == 1, "the chain footer has Pass to Review")
        if not pass_btn.count():
            return
        if not pass_btn.first.is_enabled():
            title = pass_btn.first.get_attribute("title") or ""
            self.check(bool(title.strip()), f"a grey Pass to Review carries its reason ({title!r})")
        self.goto(page, "analyse/block/2", 900)
        p = page.locator('input[data-testid="param-threshold"], [data-testid="param-threshold"] input[type=number]')
        self.check(p.count() >= 1, "the threshold block page has its threshold parameter")
        if not p.count():
            return
        p.first.fill(str(SMOKE_PASS_THRESHOLD)); p.first.press("Enter"); page.wait_for_timeout(400)
        self.goto(page, "analyse/chain", 900)
        page.locator('[data-testid="run-button"]').first.click()
        for _ in range(120):
            page.wait_for_timeout(250)
            ft = page.locator('[data-testid="footer-headline"]').inner_text().lower() if page.locator('[data-testid="footer-headline"]').count() else ""
            if "last run" in ft or "no result" in ft or "failed" in ft or "cancelled" in ft:
                break
        page.wait_for_timeout(600)
        head = page.locator('[data-testid="footer-headline"]').inner_text().strip()
        pass_btn = page.locator('[data-testid="pass-to-review"]')
        plabel = pass_btn.first.inner_text().strip()
        m = re.search(r"Pass (\d+) to Review", plabel)
        n = int(m.group(1)) if m else 0
        self.check(pass_btn.first.is_enabled() and n > 0,
                   f"Pass N to Review is enabled after a run that found spans ({head!r} · {plabel!r} · {pass_btn.first.get_attribute('title')!r})")
        if not (pass_btn.first.is_enabled() and n > 0):
            return
        pass_btn.first.click()
        page.wait_for_selector('[data-testid="queue-progress"]', timeout=20000)
        page.wait_for_timeout(1200)
        where = page.evaluate("() => location.hash")
        self.check(where.startswith("#/review/queue/"), f"Pass to Review opened the queue it made ({where})")
        self.check("adjudications" in page.locator('[data-testid="writes-chip"]').inner_text(),
                   "the chain's queue writes adjudications")
        prog = page.locator('[data-testid="queue-progress"]').inner_text()
        pm = re.search(r"(?<!\d)0\s*/\s*(\d+)", prog)
        # the queue leaves out a span that is a rediscovery of a judged annotation, so it holds at most N
        self.check(pm is not None and 1 <= int(pm.group(1)) <= n,
                   f"the queue holds the spans the footer offered, less rediscoveries ({prog!r} for {n})")
        self.evidence["pass_to_review"] = {"label": plabel, "headline": head, "landed": where, "progress": prog}
        self.shot(page, "chain-8-pass-to-review-queue")
        self.goto(page, "analyse/chain", 1200)

    def discovery(self, page):
        """Discovery (stage-3 prompt 04, spec §7).

        The page states that follow walk live content, so this first puts two
        real runs in the sandbox through the bridge's own routes — a template
        applied across two channels of a four-hour section, and the same
        section's seeded search. Driving it through the API rather than the UI
        is deliberate: the runs are the *fixture* for the page walk, and a
        flow that clicked its way there would fail for a reason that had
        nothing to do with what the states are checking.
        """
        print("[discovery]")
        scope = self.discovery_scope()
        if scope is None:
            self.check(False, "discovery: could not scope a session on this database")
            return
        self.goto(page, "discovery/runs", 1500)
        page.wait_for_selector('[data-testid="discovery-runs-page"]', timeout=20000)
        page.wait_for_timeout(1200)
        rows = page.locator('[data-testid^="run-row-"]').count()
        self.evidence["discovery_run_rows"] = rows
        self.check(rows >= 2, f"{rows} run rows (the human reference plus the runs just made)")
        strips = page.evaluate("""() => Array.from(document.querySelectorAll('[data-testid="scope-strips"] path[d]'))
                                          .map(p => (p.getAttribute('d') || '').length)""")
        self.evidence["discovery_strip_paths"] = strips
        self.check(len(strips) >= 1 and max(strips or [0]) > 200,
                   f"the scope strips painted real overviews (path lengths {strips})")
        cells = page.locator('[data-testid="fires-cell"]').count()
        self.evidence["discovery_fires_cells"] = cells
        self.check(cells > 0, f"where-each-run-fires painted {cells} bins")
        board = page.locator('[data-testid="scoreboard-table"]').inner_text() if \
            page.locator('[data-testid="scoreboard-table"]').count() else ""
        self.check(bool(board.strip()), "the scoreboard has rows")

        # fixup-a 4: a reload keeps the layout height. The 600 px Loading card
        # was a SIBLING of the content, so the 2 s poll inserted it above a
        # painted page every two seconds for the life of a run.
        self.check(page.locator('[data-testid="discovery-refreshing"]').count() == 1,
                   "the Runs page has the quiet in-place reload indicator")
        self.check(page.locator('[data-testid="discovery-loading"]').count() == 0,
                   "the 600 px first-load card is gone once the page has content")
        h0 = page.evaluate("() => document.querySelector('.k-page-inner')?.getBoundingClientRect().height || 0")
        page.wait_for_timeout(2600)      # one full poll interval
        h1 = page.evaluate("() => document.querySelector('.k-page-inner')?.getBoundingClientRect().height || 0")
        self.evidence["discovery_page_height"] = [h0, h1]
        self.check(abs(h1 - h0) < 1.0, f"the page height is unchanged across a poll ({h0} -> {h1})")
        self.shot(page, "discovery-1-runs-live")

        self.send_to_review_walk(page, scope)
        self.band_scope_walk(page, scope)

        self.goto(page, "discovery/seed", 2000)
        page.wait_for_timeout(1500)
        hist = page.locator('[data-testid="cut-histogram"]').count()
        self.check(hist >= 1, "the seed page draws its match-distance histogram")
        self.shot(page, "discovery-2-seed-live")

        self.goto(page, f"discovery/compare?a={scope['a']}&b={scope['b']}", 2500)
        page.wait_for_timeout(1500)
        self.check(page.locator('[data-testid="what-differs"]').count() >= 1,
                   "compare opens with what differs")
        self.shot(page, "discovery-3-compare-live")

    def _api(self, path, body=None, method="GET"):
        import urllib.error
        import urllib.request
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            return {"__error__": e.code, "body": e.read().decode(errors="replace")[:300]}

    def _adjudications(self):
        """Every `adjudications` row in the bridge's sandbox copy, with the run that
        wrote its detection and whether that run is a paired surrogate. Read-only."""
        import sqlite3
        db = self._api("/api/runtime").get("db_path")
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(
                "SELECT a.id, a.detection_id, a.verdict, a.created_at, d.run_id, r.surrogate_of_run_id "
                "FROM adjudications a JOIN detections d ON d.id = a.detection_id "
                "JOIN runs r ON r.id = d.run_id ORDER BY a.id").fetchall()]
        finally:
            conn.close()

    def send_to_review_walk(self, page, scope):
        """fixup-L — the researcher's walk, §7.4 → §10.1.

        *Send N unjudged to Review* makes a real `review_queues` row and the toast's
        *Open Review* opens THAT queue (its name, *writes adjudications*, `0 / N`);
        `I` on the first item writes one `adjudications` row on a detection of a
        REAL run — never of the paired surrogate that shares the run group; back in
        Discovery the acts read *Sent N* and link to the queue, and *Refresh after
        reviewing* re-reads the scoreboard. Then the same send from the seed run.
        """
        print("[discovery → review]")
        a_key = scope["a"]
        self.goto(page, f"discovery/runs?run={a_key}", 1500)
        page.wait_for_selector('[data-testid="run-acts"]', timeout=20000)
        page.wait_for_timeout(800)
        btn = page.locator('[data-testid="send-to-review"]')
        label = btn.first.inner_text().strip() if btn.count() else ""
        m = re.search(r"Send (\d+) unjudged", label)
        offered = bool(m) and int(m.group(1)) > 0 and btn.first.is_enabled()
        self.check(offered, f"the run acts offer to send ({label!r})")
        if not offered:
            return
        row_sel = f'[data-testid="score-row-{a_key}"]'
        before = page.locator(row_sel).inner_text() if page.locator(row_sel).count() else ""
        btn.first.click()
        page.wait_for_selector('[data-testid="toasts"] button', timeout=15000)
        page.wait_for_timeout(500)
        toast = page.locator('[data-testid="toasts"]').inner_text()
        mine = [q for q in (self._api("/api/review/queues") or []) if q.get("name") == f"Discovery · {a_key}"]
        self.check(len(mine) == 1, f"one review_queues row named 'Discovery · {a_key}' ({len(mine)} found)")
        if len(mine) != 1:
            return
        q = mine[0]
        self.evidence["fixup_l"] = {"toast": toast, "queue": {k: q.get(k) for k in (
            "id", "name", "source_kind", "writes_to", "unit", "total", "judged", "remaining", "filters")}}
        self.check(f"'{q['name']}'" in toast and "write adjudications" in toast,
                   f"the toast names the queue and what a verdict writes ({toast!r})")
        self.check(q["total"] == q["remaining"] > 0 and f"{q['remaining']} unjudged" in toast,
                   f"the toast's count is the queue's own ({q['remaining']} of {q['total']})")
        real_runs = set(q["filters"].get("run_ids") or [])
        self.check(bool(real_runs), f"the queue filters by run ids ({sorted(real_runs)})")
        self.shot(page, "discovery-4-send-to-review-toast")

        page.locator('[data-testid="toasts"] button', has_text="Open Review").first.click()
        page.wait_for_selector('[data-testid="queue-progress"]', timeout=20000)
        page.wait_for_timeout(1500)
        where = page.evaluate("() => location.hash")
        self.check(where.startswith(f"#/review/queue/{q['id']}"), f"Open Review landed on queue {q['id']} ({where})")
        chip = page.locator('[data-testid="queue-chip"]').inner_text() if page.locator('[data-testid="queue-chip"]').count() else ""
        self.check(q["name"] in chip, f"the toolbar names the queue ({chip!r})")
        writes = page.locator('[data-testid="writes-chip"]').inner_text()
        self.check("adjudications" in writes, f"the toolbar says what a verdict writes ({writes!r})")
        prog = page.locator('[data-testid="queue-progress"]').inner_text()
        # "0 / 23" is followed by the pace text with no space between, so no word boundary after the total
        self.check(re.search(r"(?<!\d)0\s*/\s*{}(?!\d)".format(q["total"]), prog) is not None, f"progress reads 0 / {q['total']} ({prog!r})")
        self.shot(page, "discovery-5-review-opens-that-queue")

        adj_before = {r["id"] for r in self._adjudications()}
        page.keyboard.press("i")
        page.wait_for_timeout(2000)
        self.check(page.locator('[data-testid="write-refused"]').count() == 0, "the verdict was not refused")
        new = [r for r in self._adjudications() if r["id"] not in adj_before]
        self.evidence["fixup_l"]["adjudications_written"] = new
        self.check(len(new) == 1 and new[0]["surrogate_of_run_id"] is None and new[0]["run_id"] in real_runs,
                   f"I wrote one adjudications row, on a detection of a real run in the queue ({new})")
        prog = page.locator('[data-testid="queue-progress"]').inner_text()
        self.check(re.search(r"(?<!\d)1\s*/\s*{}(?!\d)".format(q["total"]), prog) is not None, f"progress reads 1 / {q['total']} ({prog!r})")
        self.shot(page, "discovery-6-review-verdict-written")

        self.goto(page, f"discovery/runs?run={a_key}", 1500)
        page.wait_for_selector('[data-testid="run-acts"]', timeout=20000)
        page.wait_for_timeout(800)
        sent = page.locator('[data-testid="send-to-review"][data-queue]')
        self.check(sent.count() == 1 and sent.first.get_attribute("data-queue") == str(q["id"]),
                   f"the acts read 'Sent N' and link to queue {q['id']} ({sent.first.inner_text().strip() if sent.count() else 'absent'!r})")
        page.locator('[data-testid="refresh-scores"]').first.click()
        page.wait_for_timeout(3000)
        after = page.locator(row_sel).inner_text() if page.locator(row_sel).count() else ""
        self.evidence["fixup_l"]["score_row_before"] = before
        self.evidence["fixup_l"]["score_row_after"] = after
        self.check(bool(after.strip()), f"the scoreboard re-read after reviewing ({after!r})")
        self.shot(page, "discovery-7-refresh-after-reviewing")

        # the same gesture from the seed run makes a seed-search queue
        b_key = scope.get("b")
        if b_key and b_key != "human":
            self.goto(page, f"discovery/runs?run={b_key}", 1500)
            page.wait_for_selector('[data-testid="run-acts"]', timeout=20000)
            page.wait_for_timeout(800)
            btn = page.locator('[data-testid="send-to-review"]')
            if btn.count() and btn.first.is_enabled() and "Send" in btn.first.inner_text():
                btn.first.click()
                page.wait_for_selector('[data-testid="toasts"] button', timeout=15000)
                page.wait_for_timeout(500)
                seed_q = [x for x in (self._api("/api/review/queues") or []) if x.get("name") == f"Discovery · {b_key}"]
                self.evidence["fixup_l"]["seed_queue"] = seed_q[0] if seed_q else None
                self.check(len(seed_q) == 1 and seed_q[0]["source_kind"] == "seed-search" and seed_q[0]["writes_to"] == "adjudications",
                           f"the seed run's queue is a seed-search queue writing adjudications ({seed_q[0]['source_kind'] if seed_q else 'none'})")
                self.shot(page, "discovery-8-seed-run-sent")
            else:
                self.check(False, f"the seed run offers nothing to send ({btn.first.inner_text().strip() if btn.count() else 'no button'!r})")

    def band_scope_walk(self, page, scope):
        """fixup-Z — the researcher's walk for Q4, through the page.

        *Apply template* with a band scope: `symbol_search` ticked, the band scope
        set to the seeded list, *Add and run* → one run per band, each across the
        channels in scope, and one band-set row. Compare A = the smoke's raw run
        against the band set: the union's overlap, the per-band rows, the verdict
        split. *Send only-B unjudged to Review* → the toast's *Open Review* opens
        that queue → `I` writes one verdict on a band run's own detection → back in
        Compare the only-B row reads one more judged and accepted. Then the band
        list in Settings › Analysis defaults.
        """
        print("[discovery · band scope → compare by verdict]")
        tpl = "symbol_search"
        self.goto(page, "discovery/runs?modal=add-template", 1500)
        page.wait_for_selector('[data-testid="add-template-modal"]', timeout=20000)
        page.wait_for_selector(f'[data-testid="template-check-{tpl}"]', timeout=20000)
        page.locator(f'[data-testid="template-check-{tpl}"]').first.click()
        page.locator('[data-testid="band-scope-mode"] button', has_text="band").first.click()
        page.wait_for_selector('[data-testid="band-scope"] input[type="checkbox"]', timeout=15000)
        page.wait_for_timeout(500)
        ticked = page.locator('[data-testid="band-scope"] input[type="checkbox"]:checked').count()
        offered = (self._api("/api/discovery/bands") or {}).get("bands") or []
        self.evidence["fixup_z"] = {"bands_offered": offered}
        self.check(ticked == len(offered) >= 1, f"the band scope offers the Settings list, every band ticked ({ticked} of {len(offered)})")
        mult = page.locator('[data-testid="add-multiplier"]').inner_text()
        self.check(f"× {ticked} band" in mult, f"the footer multiplies by the bands ({mult!r})")
        self.shot(page, "discovery-9-band-scope")
        page.locator('[data-testid="add-and-run"]').first.click()
        page.wait_for_selector('[data-testid="toasts"]', timeout=20000)
        toast = page.locator('[data-testid="toasts"]').inner_text()
        self.check(f"{ticked} bands" in toast or f"{ticked} band" in toast, f"the toast counts the band runs ({toast!r})")

        def band_runs():
            rows = [r for r in (self._api("/api/discovery/runs") or []) if r.get("template") == tpl and r.get("bandSet")]
            newest = max((r["bandSet"] for r in rows), key=lambda k: (len(k), k), default=None)
            return [r for r in rows if r["bandSet"] == newest], newest
        t0 = time.time()
        runs, band_set = band_runs()
        while time.time() - t0 < 1800 and (len(runs) < ticked or any(r["status"] not in ("done", "failed") for r in runs)):
            time.sleep(2.0)
            runs, band_set = band_runs()
        self.evidence["fixup_z"]["band_runs"] = [{k: r.get(k) for k in ("key", "label", "status", "found", "channelsDone", "band")} for r in runs]
        n_ch = len(scope["channels"])
        self.check(len(runs) == ticked and all(r["status"] == "done" and r.get("channelsDone") == f"{n_ch} / {n_ch}" for r in runs),
                   f"{ticked} band runs, each across the {n_ch} channels in scope ({[(r['key'], r['status'], r.get('channelsDone')) for r in runs]})")
        if not band_set:
            return
        self.goto(page, "discovery/runs", 1500)
        page.wait_for_selector(f'[data-testid="band-set-row-{band_set}"]', timeout=20000)
        self.check(all(page.locator(f'[data-testid="run-row-{r["key"]}"]').count() == 1 for r in runs),
                   "every band run has its own row")
        self.shot(page, "discovery-10-band-runs-and-set")

        a_key, side = scope["a"], f"set:{band_set}"
        self.goto(page, f"discovery/compare?a={a_key}&b={side}", 2500)
        page.wait_for_selector('[data-testid="verdict-split"]', timeout=30000)
        page.wait_for_timeout(800)
        cmp_ = self._api(f"/api/discovery/compare?a={a_key}&b={side}&channels={','.join(scope['channels'])}&t0={scope['t0']}&t1={scope['t1']}")
        tot, ob = cmp_.get("total") or {}, (cmp_.get("verdicts") or {}).get("onlyB") or {}
        self.evidence["fixup_z"]["compare_before"] = {"total": tot, "verdicts": cmp_.get("verdicts"),
                                                      "perBand": cmp_.get("perBand"), "likeForLike": cmp_.get("likeForLike"),
                                                      "differing": cmp_.get("differing")}
        per_band = page.locator('[data-testid^="per-band-"]').count()
        self.check(per_band == ticked, f"one per-band row per band ({per_band})")
        self.check(cmp_.get("b", {}).get("found") == tot.get("both", 0) + tot.get("onlyB", 0),
                   f"the set side counts its union ({cmp_.get('b', {}).get('found')} = both {tot.get('both')} + only B {tot.get('onlyB')})")
        sentence = page.locator('[data-testid="remainder-sentence"]').inner_text() if page.locator('[data-testid="remainder-sentence"]').count() else ""
        self.check(f"{ob.get('n')} region" in sentence, f"the remainder sentence reads the only-B count ({sentence!r})")
        self.check(page.locator('[data-testid="like-for-like"]').count() == 1, "the band set names its like-for-like comparison")
        self.shot(page, "discovery-11-compare-band-set")
        if not ob.get("unjudged"):
            self.check(False, f"the band set found nothing only-B and unjudged on the smoke scope ({ob})")
            return
        page.locator('[data-testid="step-filter"] button', has_text="only B").first.click()
        page.wait_for_timeout(1200)
        bands_named = page.locator('[data-testid="step-bands"]').inner_text() if page.locator('[data-testid="step-bands"]').count() else ""
        self.check(bands_named.startswith("band"), f"the stepper names the band that fired ({bands_named!r})")

        page.locator('[data-testid="send-only-b"]').first.click()
        page.wait_for_selector('[data-testid="toasts"] button', timeout=15000)
        page.wait_for_timeout(500)
        toast = page.locator('[data-testid="toasts"]').inner_text()
        mine = [q for q in (self._api("/api/review/queues") or []) if str(q.get("name", "")).startswith("Compare · only B")]
        self.check(len(mine) >= 1 and f"{ob['unjudged']} unjudged" in toast, f"the remainder queue exists and the toast counts it ({toast!r})")
        if not mine:
            return
        q = mine[-1]
        self.evidence["fixup_z"]["queue"] = {k: q.get(k) for k in ("id", "name", "source_kind", "writes_to", "total", "judged", "remaining")}
        self.check(q["total"] == ob["n"] and q["writes_to"] == "adjudications",
                   f"one queue row per only-B region, writing adjudications ({q['total']} of {ob['n']})")
        self.shot(page, "discovery-12-remainder-sent")
        page.locator('[data-testid="toasts"] button', has_text="Open Review").first.click()
        page.wait_for_selector('[data-testid="queue-progress"]', timeout=20000)
        page.wait_for_timeout(1500)
        where = page.evaluate("() => location.hash")
        self.check(where.startswith(f"#/review/queue/{q['id']}"), f"Open Review landed on the remainder queue {q['id']} ({where})")
        adj_before = {r["id"] for r in self._adjudications()}
        page.keyboard.press("i")
        page.wait_for_timeout(2000)
        new = [r for r in self._adjudications() if r["id"] not in adj_before]
        self.evidence["fixup_z"]["adjudication_written"] = new
        self.check(len(new) == 1 and new[0]["surrogate_of_run_id"] is None,
                   f"I wrote one verdict, on a real band run's detection ({new})")
        self.shot(page, "discovery-13-remainder-judged")

        self.goto(page, f"discovery/compare?a={a_key}&b={side}", 2500)
        page.wait_for_selector('[data-testid="verdicts-onlyB"]', timeout=30000)
        page.wait_for_timeout(800)
        after = self._api(f"/api/discovery/compare?a={a_key}&b={side}&channels={','.join(scope['channels'])}&t0={scope['t0']}&t1={scope['t1']}")
        ob2 = (after.get("verdicts") or {}).get("onlyB") or {}
        self.evidence["fixup_z"]["compare_after"] = {"verdicts": after.get("verdicts")}
        row = page.locator('[data-testid="verdicts-onlyB"]').inner_text()
        self.check(ob2.get("judged") == ob.get("judged", 0) + 1 and ob2.get("accepted") == ob.get("accepted", 0) + 1
                   and f"judged {ob2.get('judged')}" in row.replace("\n", " "),
                   f"back in Compare the only-B row reads one more judged and accepted ({row!r})")
        self.shot(page, "discovery-14-compare-after-review")

        self.goto(page, "settings/analysis-defaults", 1500)
        page.wait_for_selector('[data-testid="bands-card"]', timeout=20000)
        n_rows = page.locator('[data-testid^="band-label-"]').count()
        self.check(n_rows == len(offered), f"Settings › Analysis defaults lists the {len(offered)} bands ({n_rows})")
        self.shot(page, "settings-bands")

    def discovery_scope(self):
        """Set the session's scope and make two runs, through the bridge.

        Returns the two run keys, or None if this database cannot supply the
        scope (no M2_aug recording, say) — in which case the caller says so
        rather than the page states failing one by one with a selector miss.
        """
        import urllib.error
        import urllib.request

        def call(path, body=None, method="GET"):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(self.url + path, data=data, method=method,
                                         headers={"content-type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=1800) as r:
                    return json.loads(r.read().decode() or "null")
            except urllib.error.HTTPError as e:
                return {"__error__": e.code, "body": e.read().decode(errors="replace")[:300]}

        recs = call("/api/discovery/session").get("recordings") or []
        rec = next((r for r in recs if r["key"].startswith("M2_aug") and not r["heldOut"]), None) \
            or next((r for r in recs if not r["heldOut"]), None)
        if rec is None or len(rec["channels"]) < 2:
            return None
        channels = rec["channels"][:2]
        t1 = min(SMOKE_SECTION_H[1], rec["hours"])
        t0 = max(0.0, min(SMOKE_SECTION_H[0], t1 - 1.0))
        s = call("/api/discovery/session", {"name": "smoke", "recording": rec["key"],
                                            "channels": channels, "section": [t0, t1],
                                            "null": {"method": "phase randomisation", "n": 3}}, "PUT")
        if s.get("__error__"):
            return None
        applied = call("/api/discovery/templates/apply",
                       {"templates": [SMOKE_TEMPLATE], "channels": channels, "t0": t0, "t1": t1,
                        "run": True}, "POST")
        if not isinstance(applied, list) or not applied:
            return None
        a_key = applied[0]["run_key"]
        self._wait_job(call, applied[0].get("job_id"))

        # one template added and NOT started: §7.5's cluster route is about a run
        # that exists and has not run, and `?modal=slurm` needs one to write a
        # script for. `run: false` is the modal's own *Create SLURM script* path.
        call("/api/discovery/templates/apply",
             {"templates": [SMOKE_PENDING_TEMPLATE], "channels": channels, "t0": t0, "t1": t1,
              "run": False}, "POST")

        b_key = None
        # the seed page opens on the draft's seed, so compute the result for THAT
        # seed with the page's own k — a result under any other key is a cache
        # miss and the histogram has nothing to draw
        setup = call("/api/discovery/seed/setup")
        draft = (setup.get("draft") or {}) if not setup.get("__error__") else {}
        seed_id = draft.get("seedId")
        if seed_id:
            # the seed page finds its finished run by the DRAFT's label, and the
            # page states name the run key, so both are pinned to one name here
            # rather than to a hash that changes with the seed
            call("/api/discovery/seed/draft", {"label": SMOKE_SEED_RUN}, "PUT")
            seed_label = SMOKE_SEED_RUN
            started = call("/api/discovery/seed/results",
                           {"seedId": seed_id, "channels": channels, "t0": t0, "t1": t1,
                            "k": SMOKE_SEED_K, "maxDistance": 0.0}, "POST")
            self._wait_job(call, started.get("job_id"))
            run = call("/api/discovery/seed/run", {"seedId": seed_id, "channels": channels,
                                                   "t0": t0, "t1": t1, "k": SMOKE_SEED_K,
                                                   # the seed page looks its finished run up by the
                                                   # draft's own label, so the run must carry it
                                                   "label": seed_label or "smoke_seed"}, "POST")
            if not run.get("__error__"):
                b_key = run["run_key"]
                self._wait_job(call, run.get("job_id"))
        self.evidence["discovery_scope"] = {"recording": rec["key"], "channels": channels,
                                            "section_h": [t0, t1], "runs": [a_key, b_key]}
        return {"a": a_key, "b": b_key or "human", "channels": channels, "t0": t0, "t1": t1}

    @staticmethod
    def _wait_job(call, job_id, timeout_s=1800):
        if not job_id:
            return None
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            snap = call(f"/api/jobs/{job_id}")
            if snap.get("__error__") or snap.get("status") in ("completed", "failed", "cancelled"):
                return snap
            time.sleep(1.0)
        return None

    # ------------------------------------------- states pinned against live data --
    def pin_grouping(self, page, pins: dict):
        """fixup-smoke: a state that names a family (`F-03`, `F-130`) is about ONE grouping, but the Library opens on
        the NEWEST grouping of each unit (`chrome.tsx::useResolvedGroupingId`, the bridge's `_default_grouping`), and
        the researcher makes groupings in the database the sandbox copies (g-07..g-09 on 2026-10-05). Nothing in the
        URL names a grouping (the client ignores `?grouping=`), so the walk picks it the way a person does: the
        grouping bar's basis chip, then the option. The pick lives in the client's in-memory store and survives the
        walk's hash navigations, so it is done once and re-done only when the store says otherwise. The pick is
        verified, never assumed: a grouping id that is no longer offered, or a store that did not take it, raises,
        and the state fails with that reason."""
        for unit, gid in pins.items():
            key = f"library.grouping.{unit}"
            read = "k => (window.__demoStore && window.__demoStore.get(k)) || ''"
            if page.evaluate(read, key) == gid:
                continue
            page.goto(f"{self.url}/#/library/atlas{'?unit=sequences' if unit == 'sequences' else ''}", wait_until="networkidle")
            page.wait_for_selector('[data-testid="basis-chip"]', timeout=30000)
            page.locator('[data-testid="basis-chip"]').first.click()
            opt = page.locator(f'[data-testid="grouping-option-{gid}"]')
            opt.first.wait_for(timeout=15000)
            opt.first.click()
            # the pick raises a toast; toasts older than one second are cleared on the next hash change, so the
            # state's own page does not inherit it
            page.wait_for_timeout(1200)
            got = page.evaluate(read, key)
            if got != gid:
                raise AssertionError(f"pinning the {unit} grouping to {gid} did not take (the store holds {got!r})")
            # the pick happens on an atlas that first opened on the newest grouping, so two cold view builds queue
            # behind one sqlite connection; wait here until the pinned grouping's atlas has painted, so the state
            # that follows meets the warm page its own settle time was measured against
            page.wait_for_selector('[data-testid="atlas-grid"], [data-testid="sequences-banner"]', timeout=180000)

    def smoke_run_keys(self) -> dict:
        """fixup-smoke: the keys of the two Discovery runs the walk itself made (`discovery_scope`), for the page
        states that compare them. They used to be written into the manifests as `mp_threshold` and `smoke_seed`,
        but a key is only the label when nothing in the session already holds that label or that seed: the
        researcher's own seed searches on the same seed (2026-10-04) make the walk's run differ from the first, so
        it is labelled `smoke_seed · 2 ch · 80.0–84.0 h` and keyed `smoke_seed_2_ch_80.0_84.0_h` — and every state
        naming `smoke_seed` compared against a run that does not exist. A manifest names them `{run:a}` /
        `{run:b}`. A full walk uses the keys `discovery_scope` returned; a page-only walk reads them off the
        session: the first finished `SMOKE_TEMPLATE` run, and the newest seed run labelled `SMOKE_SEED_RUN`."""
        runs = (self.evidence.get("discovery_scope") or {}).get("runs") or []
        keys = {"a": runs[0] if runs else None, "b": runs[1] if len(runs) > 1 else None}
        if not (keys["a"] and keys["b"]):
            rows = self._api("/api/discovery/runs")
            rows = rows if isinstance(rows, list) else []
            keys["a"] = keys["a"] or next((r["key"] for r in rows if r.get("template") == SMOKE_TEMPLATE
                                           and r.get("label") == SMOKE_TEMPLATE and r.get("status") == "done"
                                           and not r.get("bandSet")), None)
            keys["b"] = keys["b"] or next((r["key"] for r in reversed(rows) if not r.get("template")
                                           and str(r.get("label", "")).startswith(SMOKE_SEED_RUN)), None)
        self.evidence["smoke_run_keys"] = keys
        return keys

    def branch_on_store(self, e: dict):
        """fixup-smoke: a state about an EMPTY store (no window set, no paired run) asserts the empty state only when
        the store the page reads really is empty, and otherwise asserts the populated state the same page draws over
        the same read. Both arms must name something to find, so neither side is a no-op; the message says which
        arm ran and over how many rows. `branch_on`: {"api": route, "items": dotted key of the list in the answer
        ("" = the answer is the list), "where": {field: value} rows must match, "empty": {expect, expect_absent},
        "populated": {expect, expect_absent}}."""
        b = e.get("branch_on")
        if not b:
            return e, ""
        for arm in ("empty", "populated"):
            if not (b.get(arm) or {}).get("expect"):
                raise ValueError(f"branch_on.{arm} names nothing to expect: a branch must check something real")
        data = self._api(b["api"])
        if isinstance(data, dict) and data.get("__error__"):
            raise RuntimeError(f"branch_on: {b['api']} answered {data['__error__']}: {data.get('body')}")
        items = data
        for k in filter(None, (b.get("items") or "").split(".")):
            items = items[k]
        where = b.get("where") or {}
        rows = [x for x in items if all(x.get(k) == v for k, v in where.items())]
        side = "populated" if rows else "empty"
        arm = b[side]
        e = {**e, "expect": list(e.get("expect", [])) + list(arm.get("expect", [])),
             "expect_absent": list(e.get("expect_absent", [])) + list(arm.get("expect_absent", []))}
        return e, f" [{b['api']}{' ' + str(where) if where else ''}: {len(rows)} rows, so the {side} state]"

    # ----------------------------------------------------- every page state --
    def routes(self, page):
        """Every route and state named in webui/smoke_pages/<workspace>.json renders: the page mounts,
        the header is present, the main area is not blank, no render-error card appears (unless the
        state expects one), every `expect` selector is present, and no console/page error fires.
        Manifest entry: {"page": "models.launch", "state": "default", "hash": "models/launch?x=1",
        "actions": [{"click": "[data-testid=add-arm]"}, {"press": "Escape"}, {"fill": ["sel", "text"]},
        {"wait": 300}, {"hash": "#/models/results"}], "expect": ["[data-testid=launch-sources]"], "expect_absent": [], "allow_error_card": false}"""
        print("[routes]")
        # the live flows ran in this same tab: start the page walk from a hard reload, so a row whose error
        # boundary the loud-failure flow tripped (?throw=1) or an in-memory write (a span sent from Explore)
        # cannot leak into the first states. The states themselves keep sharing the tab, as the builders ran them.
        page.goto(f"{self.url}/#/", wait_until="networkidle")
        # the app keeps the source span and the chain in sessionStorage across a reload (state.tsx), so a
        # reload alone is not a fresh tab: clear both storages first, as a new tab would have them
        page.evaluate("() => { try { sessionStorage.clear(); localStorage.clear() } catch (e) {} }")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(300)
        mdir = os.path.join(HERE, "smoke_pages")
        entries = []
        for fn in sorted(os.listdir(mdir)) if os.path.isdir(mdir) else []:
            if not fn.endswith(".json") or (self.only and not fn.startswith(self.only)):
                continue
            try:
                with open(os.path.join(mdir, fn), encoding="utf-8") as f:
                    for e in json.load(f):
                        entries.append((fn[:-5], e))
            except Exception as e:
                self.failures.append(f"smoke_pages/{fn} unreadable: {e}")
        self.evidence["route_states"] = len(entries)
        self.check(len(entries) > 0, f"{len(entries)} page states listed in smoke_pages/*.json")
        pdir = os.path.join(SHOTS, "pages")
        run_keys = self.smoke_run_keys() if any("{run:" in json.dumps(e) for _, e in entries) else {}
        for unit, e in entries:
            if "{run:" in json.dumps(e):
                txt = json.dumps(e)
                for k, v in run_keys.items():
                    if v:
                        txt = txt.replace("{run:%s}" % k, v)
                e = json.loads(txt)
            name = f"{e.get('page', '?')}--{e.get('state', 'default')}"
            before = len(self.errors)
            try:
                if "{run:" in json.dumps(e):
                    raise RuntimeError(f"the state names a smoke run the walk could not find ({run_keys})")
                # fixup-smoke: the Library states that name a family open the grouping they were written against
                if e.get("grouping"):
                    self.pin_grouping(page, e["grouping"])
                # fixup-smoke: an empty-store state asserts whichever of empty / populated the store really is
                e, branch_msg = self.branch_on_store(e)
                if e.get("grouping"):
                    branch_msg = f" [grouping {', '.join(e['grouping'].values())}]" + branch_msg
                page.goto(f"{self.url}/#/{e['hash'].lstrip('#/')}", wait_until="networkidle")
                page.wait_for_timeout(e.get("settle_ms", 500))
                for a in e.get("actions", []):
                    if "click" in a: page.locator(a["click"]).first.click(); page.wait_for_timeout(250)
                    # an optional click: the control is only on the page in some states (the example-span button once a source is set)
                    elif "click_if" in a:
                        if page.locator(a["click_if"]).count(): page.locator(a["click_if"]).first.click(); page.wait_for_timeout(250)
                    elif "press" in a: page.keyboard.press(a["press"]); page.wait_for_timeout(200)
                    elif "fill" in a: page.locator(a["fill"][0]).first.fill(a["fill"][1]); page.wait_for_timeout(200)
                    # fixup-ah: choose an option of a <select> (a click opens the native list, which a walk cannot pick from)
                    elif "select" in a: page.locator(a["select"][0]).first.select_option(a["select"][1]); page.wait_for_timeout(250)
                    elif "hover" in a: page.locator(a["hover"]).first.hover(); page.wait_for_timeout(200)
                    elif "wait" in a: page.wait_for_timeout(int(a["wait"]))
                    # fixup-ab: wait for a selector, up to a timeout (ms) — a live job (a window set measured, a
                    # paired model trained) takes as long as it takes; a fixed wait is either flaky or slow
                    elif "wait_for" in a: page.wait_for_selector(a["wait_for"][0], timeout=int(a["wait_for"][1]))
                    # an in-app walk: the hash changes and the page does NOT reload, so in-memory state survives
                    elif "hash" in a: page.evaluate("h => { location.hash = h }", a["hash"]); page.wait_for_timeout(400)
                main_txt = page.locator(".main").inner_text() if page.locator(".main").count() else ""
                ok = page.locator('[data-testid="header"]').count() == 1 and len(main_txt.strip()) > 40
                missing = [s for s in e.get("expect", []) if page.locator(s).count() == 0]
                present = [s for s in e.get("expect_absent", []) if page.locator(s).count() > 0]
                err_card = page.locator('[data-testid="render-error"]').count()
                # fixup-c: a state flagged `traces_in_box` also asserts that no trace leaves its plot box
                in_box, box_msg = self.traces_in_box(page, name) if e.get("traces_in_box") else (True, "")
                # fixup-g: a Review state may also assert the context trace and its band share one axis
                axis_ok, axis_msg = self.context_axis(page, e, name)
                in_box, box_msg = in_box and axis_ok, box_msg + axis_msg
                # fixup-k: a Slope state may also assert its anatomy marks are where the payload puts them
                if e.get("anatomy_marks"):
                    marks_ok, marks_msg = self.anatomy_marks(page, name)
                    in_box, box_msg = in_box and marks_ok, box_msg + marks_msg
                # fixup-ac: a state may also assert a decomposition's layers sit at the same time as the drop they carry
                if e.get("layers_aligned"):
                    la_ok, la_msg = self.layers_aligned(page, name)
                    in_box, box_msg = in_box and la_ok, box_msg + la_msg
                # fixup-h: a state may also assert rule 9 on every plot the type views drew
                if e.get("rule9"):
                    r9_ok, r9_msg = self.rule9(page, name)
                    in_box, box_msg = in_box and r9_ok, box_msg + r9_msg
                # A state may declare console errors it provokes on purpose (a read that rejects renders a
                # loud error card — the brief's failure state). Declared ones are dropped from the run's
                # error list so they neither fail this state nor the whole run; anything else still fails.
                allowed = e.get("allow_console_error") or []
                if allowed:
                    kept = [x for x in self.errors[before:] if not any(a in x for a in allowed)]
                    self.errors = self.errors[:before] + kept
                self.check(ok and in_box and not missing and not present and (err_card == 0 or e.get("allow_error_card")) and len(self.errors) == before,
                           f"{unit}: {name} renders" + branch_msg + (" · every trace inside its plot box" if e.get("traces_in_box") and in_box else "") + box_msg
                           + (f" — missing {missing}" if missing else "") + (f" — unexpected {present}" if present else "")
                           + (" — render-error card" if err_card and not e.get("allow_error_card") else "") + ("" if ok else " — blank or no header")
                           + (f" — {len(self.errors) - before} console errors" if len(self.errors) > before else ""))
                os.makedirs(os.path.join(pdir, unit), exist_ok=True)
                # fixup-smoke: a state name is prose and may hold `/` or `:` ("padding +/-30 s", "context axis: 102's
                # drop"). `/` made a sub-directory that only exists in a tree an earlier walk left behind, so in a fresh
                # SMOKE_SHOTS the write failed; `:` wrote an NTFS alternate data stream behind an empty file. The file
                # name swaps the characters Windows refuses for `-`; the state's own name, in the check above, is kept.
                path = os.path.join(pdir, unit, re.sub(r'[<>:"/\\|?*]', "-", name) + ".png")
                self.write_shot(page, path, bool(e.get("full_page")))
                self.shots.append(path)
            except Exception as ex:
                self.failures.append(f"{unit}: {name}: {type(ex).__name__}: {ex}")
                print("  EXC:", name, ex)

    # ------------------------------------------------------------ driver --
    def run(self):
        from playwright.sync_api import sync_playwright
        os.makedirs(SHOTS, exist_ok=True)
        for f in (os.listdir(SHOTS) if not self.pages_only else []):   # a page-only walk keeps the flow screenshots
            if re.match(r"^\d\d-.*\.(big\.)?png$", f):
                os.remove(os.path.join(SHOTS, f))
        rt = json.load(__import__("urllib.request").request.urlopen(self.url + "/api/runtime"))
        log_path = rt["log_path"]
        log_start = os.path.getsize(log_path) if os.path.isfile(log_path) else 0
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda m: self.errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
            # A run's event stream is CLOSED BY THE CLIENT when `run_end` lands (api.ts `subscribeRun`). When that
            # close beats the server's own end-of-response the browser reports the request as aborted - a
            # deliberate close, not a failed request. It only shows on runs short enough to lose the race, which
            # the walk did not have until fixup-h's page states ran five chains.
            def _failed(r):
                if "fonts.g" in r.url:
                    return
                if r.url.endswith("/events") and "ERR_ABORTED" in (r.failure or ""):
                    return
                self.errors.append(f"requestfailed: {r.url}")
            page.on("requestfailed", _failed)
            steps = (self.routes,) if self.pages_only else (self.corpus, self.signal, self.m4, self.analyse, self.discovery, self.loud_failure, self.routes)
            for step in steps:
                try:
                    step(page)
                except Exception as e:  # keep going, report everything
                    self.failures.append(f"{step.__name__}: {type(e).__name__}: {e}")
                    print("  EXC:", step.__name__, e)
                    try: self.shot(page, f"{step.__name__}-exception")
                    except Exception: pass
            browser.close()
        # server log check
        tail = ""
        if os.path.isfile(log_path):
            with open(log_path, encoding="utf-8", errors="replace") as f:
                f.seek(log_start); tail = f.read()
        tb = [l for l in tail.splitlines() if "Traceback" in l or "ERROR" in l]
        allowed = ("/api/boom", "deliberate", "must be shorter than the span", "RecipeExecutionError", "run", "window (m=")
        unexpected = [l for l in tb if not any(a in l for a in allowed)]
        self.evidence["server_log_error_lines"] = tb[:20]
        self.check(not unexpected, f"no unexpected server tracebacks ({len(unexpected)} unexpected of {len(tb)} error lines)")
        self.check(not self.errors, f"no browser console/page errors ({len(self.errors)})")
        for e in self.errors[:20]:
            print("   browser:", e[:300])
        out = {"failures": self.failures, "browser_errors": self.errors, "evidence": self.evidence, "screenshots": self.shots}
        with open(os.path.join(SHOTS, "smoke-result.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"\n{len(self.shots)} screenshots, {len(self.failures)} failures")
        return 0 if not self.failures else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("WEBUI_URL", "http://127.0.0.1:8765"))
    ap.add_argument("--no-run", action="store_true", help="skip the run/cancel/fail flows")
    ap.add_argument("--pages-only", action="store_true", help="only walk the page states in smoke_pages/*.json")
    ap.add_argument("--only", default=None, help="restrict the page walk to smoke_pages/<prefix>*.json")
    a = ap.parse_args()
    sys.exit(Smoke(a.url, not a.no_run, a.pages_only, a.only).run())
