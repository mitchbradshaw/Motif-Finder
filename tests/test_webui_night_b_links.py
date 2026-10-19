"""
test_webui_night_b_links.py
===========================
night-b: links into Library › Family that the family page does not read.

The family page takes its id from the PATH (`#/library/family/<id>`, `library/index.tsx` routes on `parts[0]`).
Interrogation's *Open in Library →* wrote `#/library/family?family=id001`: the page saw no id and drew the
grouping's FIRST family (F-01) under the Library header — a different family from the one the button named, with
nothing on screen to say so (driven on the night fixture: source id001 → "F-01 · grouping g-01"). Source-level:
no client file builds a family link from a `?family=` query.
"""
import glob
import io
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")


def test_no_family_link_names_the_family_in_a_query():
    bad = []
    for path in glob.glob(os.path.join(CLIENT_SRC, "**", "*.ts*"), recursive=True):
        src = io.open(path, encoding="utf-8").read()
        for m in re.finditer(r"library/family\?family=", src):
            bad.append(f"{os.path.relpath(path, CLIENT_SRC)}:{src[:m.start()].count(chr(10)) + 1}")
    assert not bad, f"the family page reads its id from the path, not ?family=: {bad}"


def test_interrogation_opens_the_family_it_names():
    src = io.open(os.path.join(CLIENT_SRC, "interrogation", "SourcePage.tsx"), encoding="utf-8").read()
    assert re.search(r"navigate\(`library/family/\$\{encodeURIComponent\(fam\.id\)\}`\)", src)


def test_the_signal_page_does_not_call_its_live_read_demo():
    """night-b: `getSignalDemo` is the LIVE read (api/explore.ts: "Kept name for the pages: now the live read"), so
    `demo={!!demo}` printed *demo data* in the header, a *demo* tag on the span legend and "(demo canon)" on the
    ribbons of every live channel. The chips follow the read's `source`."""
    src = io.open(os.path.join(CLIENT_SRC, "explore", "SignalPage.tsx"), encoding="utf-8").read()
    for el in ("<Header ", "<SpanView ", "<Ribbons "):
        for m in re.finditer(re.escape(el), src):
            tag = src[m.start():src.index("/>", m.start())]
            assert "demo={!!demo}" not in tag, f"{el.strip()} is told the live read is demo"
    assert "demoRead.source === 'demo'" in src


def test_a_block_pages_fold_is_its_own():
    """night-b: `Headline` reads its open/closed state once, when it mounts. Moving between block pages in the app
    (intervals → trains by the ribbon) reuses the mounted one, so trains drew the fold intervals had opened, then
    folded on a reload (driven: intervals open → trains in-app open, reloaded closed, storage held intervals only).
    The block page's Headline is keyed by its page, so each page mounts its own."""
    src = io.open(os.path.join(CLIENT_SRC, "analyse", "views", "registry.tsx"), encoding="utf-8").read()
    assert "<Headline key={fold.page} page={fold.page}" in src


def test_a_template_link_by_name_is_resolved_or_refused_in_words():
    """night-c's walk: `#/analyse/chain?template=<name>` called getTemplate(Number(name)) → GET /api/templates/NaN →
    a red toast reading only "422 Unprocessable Content". A non-numeric value is looked up by name, and a name the
    database does not hold is refused in words."""
    src = io.open(os.path.join(CLIENT_SRC, "analyse", "ChainPage.tsx"), encoding="utf-8").read()
    assert "getTemplate(Number(qp.template))" not in src
    assert "no saved template called" in src


def test_cross_channel_says_demo_only_for_a_demo_read():
    """night-c's walk: the loading and error headers defaulted to the *demo data* chip on a live page, and a channel
    the read does not know was "not in the demo data"."""
    src = io.open(os.path.join(CLIENT_SRC, "explore", "CrossChannelPage.tsx"), encoding="utf-8").read()
    assert "(subtitle: string, demo = true)" not in src
    assert "in the demo data" not in src and "no demo data" not in src


def test_a_missing_block_page_names_itself():
    """night-c's walk: a block page past the chain's end titled itself "02 —"."""
    src = io.open(os.path.join(CLIENT_SRC, "analyse", "BlockPage.tsx"), encoding="utf-8").read()
    assert "page={`${pad2(index + 1)} —`}" not in src
