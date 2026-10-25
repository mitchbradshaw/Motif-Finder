"""
test_night_c_shell.py
=====================
night pass C (2026-10-19): site-wide polish and load fixes in the shell and the kit, pinned at source level
(the browser half is `scripts/night/walk_c.py`, run against a sandbox bridge on the scale fixture).

* **The kit barrel does not drag the gallery into every page.** `kit/index.ts` re-exported `KitGallery`, so the
  gallery and the fixture canon it draws landed in the entry chunk that every workspace loads first, while
  `App.tsx` already lazy-loads it from `kit/Gallery` (vite: INEFFECTIVE_DYNAMIC_IMPORT).
"""
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")


def _read(*parts):
    with open(os.path.join(SRC, *parts), encoding="utf-8") as f:
        return f.read()


def test_kit_barrel_does_not_reexport_the_gallery():
    barrel = _read("kit", "index.ts")
    assert "Gallery" not in barrel, "kit/index.ts must not re-export KitGallery: App.tsx lazy-loads it"


def test_nothing_imports_the_gallery_through_the_barrel():
    offenders = []
    for root, _dirs, files in os.walk(SRC):
        for name in files:
            if not name.endswith((".ts", ".tsx")) or name == "Gallery.tsx":
                continue
            text = open(os.path.join(root, name), encoding="utf-8").read()
            if re.search(r"import\s*\{[^}]*\bKitGallery\b[^}]*\}\s*from\s*'[^']*kit'", text):
                offenders.append(os.path.relpath(os.path.join(root, name), SRC))
    assert not offenders, offenders


def test_app_lazy_loads_the_gallery_from_its_module():
    assert re.search(r"import\('\./kit/Gallery'\)", _read("App.tsx"))


# ── the header: the right-hand cluster never shrinks, the search pill never wraps ──────────────────────────────
# On the scale fixture at 1440x900 the Review and Discovery headers (a long subtitle, the path strip's side pill)
# squeezed `.hdr-right`, and "Search spans, runs, families / Ctrl K" broke onto two lines inside a 28 px pill.

def _header_rule(selector):
    css = _read("shell", "Header.tsx")
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, f"no {selector} rule in shell/Header.tsx"
    return m.group(1)


def test_header_right_cluster_does_not_shrink():
    assert re.search(r"flex:\s*none", _header_rule(".hdr-right"))


def test_header_search_pill_does_not_wrap():
    assert re.search(r"white-space:\s*nowrap", _header_rule(".hdr-search"))


def test_header_titles_never_wrap_and_the_subtitle_gives_way():
    # Jobs at 1440x900: .hdr-left grew 10 px after first paint (a title broke onto two lines) - a layout shift
    for sel in (".hdr-ws", ".hdr-page"):
        assert re.search(r"white-space:\s*nowrap", _header_rule(sel)), sel
    assert re.search(r"min-width:\s*0", _header_rule(".hdr-sub"))


def test_the_app_fits_a_1024_px_window():
    # theme.css held `body { min-width: 1200px }` from the prototype: at 1024x700 every page scrolled sideways as a
    # whole (document 1200 > 1024), the header's need-you and held-out chips and every page's right edge off screen
    css = _read("theme.css")
    m = re.search(r"body\s*\{([^}]*)\}", css)
    assert m
    mw = re.search(r"min-width:\s*(\d+)px", m.group(1))
    assert mw is None or int(mw.group(1)) <= 1024


def test_a_key_cap_never_shrinks_below_its_label():
    # kit gallery at 1024x700: "Ctrl Z" spilled out of its kbd (34 px of text in a 30 px box) - a flex row squeezed
    # it; the same Kbd sits in Review's verdict bar and every shortcut hint
    css = _read("kit", "kit.css")
    m = re.search(r"\.k-kbd\s*\{([^}]*)\}", css)
    assert m and re.search(r"flex:\s*none", m.group(1))


def test_header_search_label_folds_away_on_a_narrow_window():
    css = _read("shell", "Header.tsx")
    m = re.search(r"@media\s*\(max-width:\s*(\d+)px\)\s*\{([^@]*?)\}\s*\}", css, re.S)
    assert m, "the header needs a narrow-window rule"
    assert int(m.group(1)) >= 1200
    assert ".hdr-search" in m.group(2) and "display: none" in m.group(2)


# ── the header's "N need you": one shared read, not one per header mount ──────────────────────────────────────
# `/api/review/counts` costs ~2.5 s on the scale fixture (10 k-item queue), and every Header mount asked again (a
# page renders its loading header, then its loaded one): four reads in the first 10 s of the Review inspector, and
# the chip flashed "0 need you" grey on each remount. One shared read holds one answer for every header (tq-reads,
# 2026-10-25: the night-c module `shell/sharedRead.ts` became the one primitive `api/sharedRead.ts`, so these run it
# there: `refresh()` is `read()`, `get()` is `snapshot().value`, and the header's failure rule is `onFailure: 'hold'`).
import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

import pytest  # noqa: E402

SHARED_TS = os.path.join(SRC, "api", "sharedRead.ts")


def _node(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(SHARED_TS), "api/sharedRead.ts is missing"
    url = "file:///" + SHARED_TS.replace("\\", "/").lstrip("/")
    script = (f"import * as M from {json.dumps(url)};\n(async () => {{ {body} }})()"
              ".then(v => console.log(JSON.stringify(v)), e => { console.error(e); process.exit(1) })")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_shared_read_asks_once_for_many_mounts():
    out = _node("""
      let calls = 0
      const s = M.makeSharedRead(async () => { calls++; await new Promise(r => setTimeout(r, 20)); return 7 }, { ttlMs: 10000, initial: 0 })
      await Promise.all([s.read(), s.read(), s.read()])
      await s.read()
      return { calls, value: s.snapshot().value }
    """)
    assert out == {"calls": 1, "value": 7}


def test_shared_read_keeps_the_last_answer_and_refreshes_after_its_ttl():
    out = _node("""
      let n = 0
      const s = M.makeSharedRead(async () => ++n, { ttlMs: 30, initial: 0 })
      const seen = []
      const off = s.subscribe(() => seen.push(s.snapshot().value))
      await s.read()
      await s.read()
      const kept = s.snapshot().value
      await new Promise(r => setTimeout(r, 50))
      await s.read()
      off()
      s.invalidate()
      await s.read()
      return { kept, now: s.snapshot().value, seen }
    """)
    assert out == {"kept": 1, "now": 3, "seen": [1, 2]}


def test_shared_read_failure_keeps_the_last_value_and_reports_it():
    out = _node("""
      let fail = false
      const s = M.makeSharedRead(async () => { if (fail) throw new Error('503 down'); return 5 }, { ttlMs: 0, initial: 0, onFailure: 'hold' })
      await s.read()
      fail = true
      const error = await s.read().then(() => null, e => e.message)
      return { value: s.snapshot().value, error }
    """)
    assert out == {"value": 5, "error": "503 down"}


def test_header_reads_need_you_through_the_shared_read():
    hdr = _read("shell", "Header.tsx")
    assert "useReviewNeedYou" not in hdr
    assert "useSharedNeedYou" in hdr
