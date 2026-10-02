"""
test_webui_block_views.py
==========================
fixup-h: a block shows its work.

Three halves:

* the client pins run anywhere (they read the client's sources): Analyse draws
  with the kit's plots rather than hand-rolled copies, the two fabricated nulls
  of the Aggregate page are gone along with the P10 claim they were labelled
  with, one rose survives and it is the kit's, and no interrogation thumbnail is
  interpolated;
* the classifier's card, which needs sklearn (conda);
* the route tests need FastAPI, which lives only in `webui/.venv`:

      webui/.venv/Scripts/python.exe -m pytest tests/test_webui_block_views.py
"""

import os
import re
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
SEED_DIR = os.path.join(PROJECT_ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
needs_seed = pytest.mark.skipif(not os.path.isdir(SEED_DIR), reason="seed store absent")


def _src(*parts):
    with open(os.path.join(CLIENT_SRC, *parts), encoding="utf-8") as f:
        return f.read()


def _tree(*parts):
    out = {}
    for root, _dirs, files in os.walk(os.path.join(CLIENT_SRC, *parts)):
        for fn in files:
            if fn.endswith((".ts", ".tsx")):
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    out[os.path.relpath(path, CLIENT_SRC).replace(os.sep, "/")] = f.read()
    return out


# ------------------------------------------------------------------ the client pins --

def test_analyse_draws_with_the_kits_plots():
    """`analyse/` imported zero plot components from the kit and hand-rolled its own histogram, while
    `Scatter`, `NullBand` and `SmallMultiples` had no caller outside the gallery."""
    views = "\n".join(src for path, src in _tree("analyse", "views").items())
    assert views, "analyse/views/ does not exist"
    for component in ("Histogram", "Bars", "SmallMultiples"):
        assert re.search(r"import\s*\{[^}]*\b%s\b[^}]*\}\s*from\s*'[./]+kit" % component, views, re.S), (
            f"analyse/views never imports the kit's {component}")
    assert "function Histogram(" not in _src("analyse", "BlockPage.tsx"), "BlockPage.tsx still hand-rolls a histogram"


def test_the_aggregate_page_draws_no_fabricated_null():
    """The scatter null multiplied each real point by random factors, three times; the histogram null was three
    uniforms summed, centred on the observed range. Both were labelled with P10's wording, and P10 is specified
    and not built (QUESTIONS.md Q27)."""
    page = _src("interrogation", "AggregatePage.tsx")
    for gone in ("nullSample", "nullPoints", "nullFit", "seeded(", "matched windows", "shuffled onsets"):
        assert gone not in page, f"AggregatePage.tsx still carries `{gone}`"
    assert "null-beta-tile" not in page, "the null-beta tile compared the fit with a regression-diluted copy of itself"


def test_no_interrogation_page_claims_a_p10_null():
    hits = {path: [m for m in ("matched random windows", "200×", "carries a null (P10)", "a null behind every plot")
                   if m in src]
            for path, src in {**_tree("interrogation"), "fixtures/interrogation.ts": _src("fixtures", "interrogation.ts")}.items()}
    hits = {p: m for p, m in hits.items() if m}
    assert not hits, f"an unbuilt null is still claimed: {hits}"


def test_one_rose_survives_and_it_is_the_kits():
    assert not os.path.exists(os.path.join(CLIENT_SRC, "interrogation", "Rose.tsx")), "the fixture-era rose is still there"
    assert "export function Rose(" in _src("kit", "Rose.tsx")
    assert "function RoseFan(" not in _src("analyse", "EventFeatures.tsx"), "a second rose is still defined in analyse/"
    for path, src in {**_tree("interrogation"), **_tree("analyse")}.items():
        if "<Rose " in src or "<Rose\n" in src:
            assert re.search(r"import\s*\{[^}]*\bRose\b[^}]*\}\s*from\s*'[./]+kit", src, re.S), f"{path} draws a rose that is not the kit's"


def test_no_interrogation_thumbnail_is_interpolated():
    """`liveEventCurve` resampled the stored snippet to one value per second by linear interpolation: a drawn
    curve implying samples the recording does not have."""
    for path, src in {**_tree("interrogation"), "api/interrogation.ts": _src("api", "interrogation.ts")}.items():
        assert "liveEventCurve" not in src, f"{path} still draws the interpolated curve"


def test_small_multiples_can_give_every_panel_its_own_domain_and_a_scale_bar():
    """Q15: per-panel measured domain plus an explicit scale bar - not a shared y, which draws most of a
    scale-invariant family as flat lines."""
    plots = _src("kit", "plots.tsx")
    assert "'per-panel'" in plots, "SmallMultiples has no per-panel domain mode"
    assert "export function ScaleBar(" in _src("charts", "ScaleBar.tsx")


# ---------------------------------------------------------------- the model's card --

def test_the_classifier_reports_its_accuracy_per_class():
    """`Renderer.tsx` said "a model has no natural plot". That is only true of the joblib: the holdout the block
    already takes has an accuracy per class, and the card did not carry it."""
    pytest.importorskip("sklearn")
    import pandas as pd
    from Adapters.registry import discover_adapters, get_adapter
    from Working.types import Grouping, WindowSet
    discover_adapters()
    rng = np.random.default_rng(0)
    n = 60
    labels = np.repeat([1, 2, 3], n // 3)
    feats = pd.DataFrame({f"f{k}": rng.normal(labels * (k + 1), 0.2) for k in range(4)})
    ws = WindowSet(starts=np.arange(n) * 60, length=60, fs=1.0, features=feats)
    spec = get_adapter("catalogue.classifier")
    params = spec.validate_params({"n_estimators": 20})
    x = rng.normal(size=n * 60)
    r = spec.run(x, np.arange(len(x), dtype=float), 1.0, **params, value=Grouping(labels=labels), windows=ws)
    per = r.meta["per_class_accuracy"]
    assert set(per) == {1, 2, 3} and all(0.0 <= v <= 1.0 for v in per.values())
    counts = r.meta["holdout_class_counts"]
    assert sum(counts.values()) == r.meta["n_holdout"]
    weighted = sum(per[k] * counts[k] for k in per) / r.meta["n_holdout"]
    assert weighted == pytest.approx(r.meta["holdout_accuracy"]), "the per-class bars must add up to the headline number"


# ---------------------------------------------------------------------- the routes --

@pytest.fixture
def client(tmp_path):
    pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
    pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")
    from fastapi.testclient import TestClient

    from Working.database.schema import init_db
    from server.app import create_app
    from server.runtime import Runtime

    db_dir = tmp_path / "db"; db_dir.mkdir()
    conn = init_db(str(db_dir / "annotations.sqlite"))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES ('syn.mat', 0, 1.0, 10, 0, 'x.npy')")
    conn.commit(); conn.close()
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261002-views", db_source=str(db_dir / "annotations.sqlite"),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


@needs_seed
def test_the_members_route_says_which_edges_sit_at_the_cap(client):
    from Working.Detection.drop_motifs import store as S
    from Working.Detection.drop_motifs.extent import capped_edges
    d = client.get("/api/interrogation/families/id001/members?snippets=false").json()
    by_id = {e["event_id"]: e for e in S.load_events(SEED_DIR)}
    for m in d["members"]:
        assert (m["left_capped"], m["right_capped"]) == capped_edges(by_id[m["event_id"]]), m["event_id"]
    c = d["capped"]
    assert c["n"] == len(d["members"]) and c["cap_mult"] == 6.0
    assert c["left"] == sum(m["left_capped"] for m in d["members"])


@needs_seed
def test_the_members_route_serves_the_sequence_frame_and_the_purity(client):
    d = client.get("/api/interrogation/families/id001/members?snippets=false").json()
    members = sorted(d["members"], key=lambda m: m["onset_idx"])
    assert members[0]["sequence_frame"]["first"] is True
    for prev, m in zip(members, members[1:]):
        f = m["sequence_frame"]
        gap_s = (m["onset_idx"] - prev["trough_idx"]) / m["fs"]
        assert f["pre_s"] <= gap_s + 1e-9, "a sequence frame never reaches past the previous trough"
        assert f["pre_s"] <= 14.0 * m["fall_duration_s"] + 1e-9
    assert all("purity" in m for m in members), "the impurity flag is the store's own purity count"


@needs_seed
def test_a_member_snippet_is_real_samples_or_a_min_max_envelope_never_a_stride(client):
    """The route picked every k-th sample (`np.linspace(...).round()`), which deletes a narrow event - the one
    thing a snippet exists to show."""
    from Working.Detection.drop_motifs import store as S
    snips = S.load_snippets(SEED_DIR)
    d = client.get("/api/interrogation/families/id001/members").json()
    longest = max(d["members"], key=lambda m: m["snippet"]["n"])
    for m in (d["members"][0], longest):
        s, full = m["snippet"], np.asarray(snips[m["event_id"]]["detrended_mv"], dtype=float)
        assert s["n"] == len(full)
        if not s["decimated"]:
            assert s["detrended_mv"] == pytest.approx(full.tolist())
        else:
            assert min(s["detrended_mv"]) == pytest.approx(full.min()) and max(s["detrended_mv"]) == pytest.approx(full.max()), (
                "a min/max envelope keeps the true extremes; a stride does not")
        assert s["mismatch"] is None


@needs_seed
def test_the_slope_route_serves_the_rose_in_the_shape_the_kit_draws(client):
    d = client.get("/api/interrogation/families/id001/slope").json()
    rose = d["rose"]
    for key in ("n", "counts", "bin_centres_deg", "bin_width_deg", "angles_deg", "event_index", "mean_deg", "resultant_length"):
        assert key in rose, f"the slope route's rose has no `{key}`"
    assert rose["n"] == len(d["members"]) == len(rose["angles_deg"])
    assert sum(rose["counts"]) == rose["n"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
