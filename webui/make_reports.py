"""Assemble webui/PAGES.md and webui/PAGES_REPORT.md from what the overnight build left on disk.

    "/c/ProgramData/anaconda3/python.exe" webui/make_reports.py

Sources (no network, no database):
  * client/src/shell/pages.ts   — the page registry: id, workspace, title, route, frames, regions
  * smoke_pages/<unit>.json     — the states each page exposes, as the smoke test walks them
  * critique/<sub>/r<N>-<lens>.json — each critic's per-page score and findings
  * pages/status/<unit>.md      — each builder's own status table
  * screenshots/pages/<unit>/   — the smoke screenshot of every state
A page's score is the LOWER of its two critics in its last rated round (the brief's rule).
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "client", "src")

UNIT_OF = {"explore": "explore", "analyse": "analyse", "discovery": "discovery", "models": "models",
           "review": "review", "library": "library", "jobs": "jobs", "settings": "settings"}


def unit_of(page_id: str) -> str:
    head = page_id.split(".")[0]
    if head == "analyse":
        second = page_id.split(".")[1] if "." in page_id else ""
        if second in ("interrogation", "training"):
            return second
    return UNIT_OF.get(head, head)


def registry() -> list[dict]:
    """Parse the page registry (it is a literal table, so a regex is honest here)."""
    src = open(os.path.join(SRC, "shell", "pages.ts"), encoding="utf-8").read()
    out = []
    for m in re.finditer(r"P\('([^']+)', '([^']+)', '([^']+)', (?:'([^']*)'|\"([^\"]*)\"), '([^']+)', \[([^\]]*)\], \[([^\]]*)\]\)", src):
        pid, ws, title, sub1, sub2, route, frames, regions = m.groups()
        out.append({"id": pid, "workspace": ws, "title": title, "subtitle": sub1 or sub2, "route": route,
                    "frames": re.findall(r"'([^']+)'", frames), "regions": re.findall(r"'([^']+)'", regions)})
    # the sixteen Settings pages are generated from a literal list in the same file
    slugs = re.findall(r"\['([a-z-]+)', '([^']+)', '(settings-[^']+)'\]", src)
    for slug, title, frame in slugs:
        frames = [f"settings/{frame}"] + (["settings/settings-01b-import-recording"] if slug == "datasets" else [])
        out.append({"id": f"settings.{slug}", "workspace": "Settings", "title": title,
                    "subtitle": "personal · this browser" if slug in ("display", "keyboard") else "project · recorded with runs",
                    "route": f"settings/{slug}", "frames": frames, "regions": ["settings nav", "page sections"]})
    return out


def states() -> dict[str, list[dict]]:
    out = defaultdict(list)
    d = os.path.join(HERE, "smoke_pages")
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not fn.endswith(".json"):
            continue
        try:
            for e in json.load(open(os.path.join(d, fn), encoding="utf-8")):
                out[e.get("page", "?")].append(e)
        except Exception as ex:
            print(f"  ! {fn}: {ex}")
    return out


def critiques() -> tuple[dict, dict]:
    """page -> {round -> {lens -> {'score', 'rationale', 'findings'}}}, and sub-unit -> dirs seen."""
    out = defaultdict(lambda: defaultdict(dict))
    subs = {}
    root = os.path.join(HERE, "critique")
    for sub in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        for fn in sorted(os.listdir(os.path.join(root, sub))):
            m = re.match(r"r(\d+)-(fidelity|function)\.json$", fn)
            if not m:
                continue
            rnd, lens = int(m.group(1)), m.group(2)
            path = os.path.join(root, sub, fn)
            try:
                d = json.load(open(path, encoding="utf-8"))
            except Exception as ex:
                print(f"  ! {sub}/{fn} unreadable ({ex}) — treated as unrated")
                continue
            for p in d.get("pages", d if isinstance(d, list) else []):
                out[p.get("page")][rnd][lens] = p
                subs[p.get("page")] = sub
    return out, subs


def final_score(rounds: dict) -> tuple[int | None, int | None, int | None, int]:
    """(fidelity, function, final=min, rounds_rated) from the last round with any score."""
    rated = [r for r in sorted(rounds) if any(v.get("score") is not None for v in rounds[r].values())]
    if not rated:
        return None, None, None, 0
    last = rounds[rated[-1]]
    f = (last.get("fidelity") or {}).get("score")
    fn = (last.get("function") or {}).get("score")
    vals = [v for v in (f, fn) if v is not None]
    return f, fn, (min(vals) if vals else None), len(rated)


def main() -> None:
    pages, st, (crit, subs) = registry(), states(), critiques()
    rows = []
    for p in pages:
        u = unit_of(p["id"])
        f, fn, final, nrounds = final_score(crit.get(p["id"], {}))
        page_states = st.get(p["id"], [])
        shots = f"screenshots/pages/{u}"
        gaps = []
        for rnd in sorted(crit.get(p["id"], {})):
            for lens, v in crit[p["id"]][rnd].items():
                for x in v.get("findings", []) or []:
                    if x.get("severity") in ("P0", "P1"):
                        gaps.append(f"{x['severity']} ({lens} r{rnd}) {x.get('title')}")
        rows.append({**p, "unit": u, "fidelity": f, "function": fn, "final": final, "rounds": nrounds,
                     "states": page_states, "shots": shots, "gaps": gaps, "sub": subs.get(p["id"], "")})

    # ---------------- PAGES.md ----------------
    out = ["# PAGES.md — every concept frame, the page it became, and how it scored", "",
           "One row per page (a route/screen); a frame showing a state of that screen is a state of the page, not a",
           "page of its own. Scores are the two independent critics' (design fidelity · function) ratings of the last",
           "round; **the page's score is the lower of the two**, accepted at ≥ 8. Findings live in `webui/critique/<sub-unit>/`,",
           "screenshots of every state in `webui/screenshots/pages/<unit>/`, builder notes in `webui/pages/status/<unit>.md`,",
           "and each page's regions, interactions and fixtures in `webui/pages/inventory/`.", "",
           f"{len(rows)} pages · {sum(len(r['states']) for r in rows)} states · "
           f"{sum(len(r['frames']) for r in rows)} frame references.", ""]
    by_ws = defaultdict(list)
    for r in rows:
        by_ws[r["workspace"]].append(r)
    for ws in ["Explore", "Analyse", "Discovery", "Models", "Review", "Library", "Jobs", "Settings"]:
        if ws not in by_ws:
            continue
        out += [f"## {ws}", "",
                "| page | route | frames | states | fidelity | function | score | rounds | screenshots |",
                "|---|---|---|---|---|---|---|---|---|"]
        for r in by_ws[ws]:
            frames = " · ".join(f.split("/")[-1] for f in r["frames"])
            names = ", ".join(s.get("state", "?") for s in r["states"][:6]) + (" …" if len(r["states"]) > 6 else "")
            sc = "—" if r["final"] is None else str(r["final"])
            out.append(f"| `{r['id']}` | `#/{r['route']}` | {frames} | {len(r['states'])}: {names} | "
                       f"{r['fidelity'] if r['fidelity'] is not None else '—'} | {r['function'] if r['function'] is not None else '—'} | "
                       f"**{sc}** | {r['rounds']} | `{r['shots']}/` |")
        out.append("")
        for r in by_ws[ws]:
            if r["gaps"]:
                out += [f"**`{r['id']}` — open findings after the last round**"] + [f"- {g}" for g in r["gaps"][:12]] + [""]
    open(os.path.join(HERE, "PAGES.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out))

    # ---------------- PAGES_REPORT.md ----------------
    rated = [r for r in rows if r["final"] is not None]
    below = [r for r in rated if r["final"] < 8]
    unrated = [r for r in rows if r["final"] is None]
    rep = ["# PAGES_REPORT.md — what was built, how it scored, what is left", "",
           "## Summary", "",
           "| workspace | page | frames | fidelity | function | final | rounds | main remaining gaps | screenshots |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        gap = r["gaps"][0] if r["gaps"] else ("not rated" if r["final"] is None else "—")
        rep.append(f"| {r['workspace']} | `{r['id']}` | {len(r['frames'])} | {r['fidelity'] or '—'} | {r['function'] or '—'} | "
                   f"**{r['final'] if r['final'] is not None else '—'}** | {r['rounds']} | {gap[:90]} | `{r['shots']}/` |")
    avg = (sum(r["final"] for r in rated) / len(rated)) if rated else 0
    rep += ["", "## Statistics", "",
            f"- Pages: **{len(rows)}** over **{sum(len(r['frames']) for r in rows)}** frame references; "
            f"**{sum(len(r['states']) for r in rows)}** states walked by the smoke test.",
            f"- Rated: **{len(rated)}**; unrated (critic did not finish): **{len(unrated)}**.",
            f"- Mean final score: **{avg:.1f}**; accepted (≥ 8): **{len([r for r in rated if r['final'] >= 8])}** of {len(rated)}.",
            f"- Below 8: **{len(below)}**.", ""]
    if below:
        rep += ["## Pages below 8, and why", ""]
        for r in sorted(below, key=lambda r: r["final"]):
            rep += [f"### `{r['id']}` — {r['final']} (fidelity {r['fidelity']}, function {r['function']}, {r['rounds']} round(s))"] + \
                   [f"- {g}" for g in r["gaps"][:10]] + [""]
    if unrated:
        rep += ["## Not rated", "",
                "These pages were built but their critics did not finish (the account's usage limit stopped the run twice).", ""]
        for r in unrated:
            rep.append(f"- `{r['id']}` — {len(r['states'])} states in the smoke manifest; screenshots in `{r['shots']}/`")
        rep.append("")
    rep += ["## What needs your input", "",
            "- `docs/wayfinder/fog-of-war.md` §Frontend design collects every question the pages raised;",
            "  `webui/pages/fog/<unit>.md` holds each builder's raw notes.",
            "- `webui/BUILD_PROGRESS.md` lists the shared-kit requests builders worked around, queued for a later pass.", ""]
    open(os.path.join(HERE, "PAGES_REPORT.md"), "w", encoding="utf-8", newline="\n").write("\n".join(rep))
    print(f"PAGES.md and PAGES_REPORT.md written: {len(rows)} pages, {len(rated)} rated, {len(below)} below 8, "
          f"{len(unrated)} unrated, mean {avg:.1f}")


if __name__ == "__main__":
    main()
