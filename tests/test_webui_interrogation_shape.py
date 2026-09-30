"""
test_webui_interrogation_shape.py
===================================
fixup-e: the Interrogation Aggregate page stops inventing its measurements.

Before this prompt the page's `featureOf` returned `half_width_s = duration x 0.84`,
`rise_s = duration x 0.31` and `isi_s = duration x 4.2` for the live spike-shape
upstream, and computed recovery in the browser (90 %, on a 400-point decimated
snippet) reporting an event that never recovered as 0 s. Every number the page draws
must now come from the core: this route serves `interrogation.event_shape`'s measures
of every member of a seed family, measured on the store's own snippet from the
detector's own anchors (fixup-d, `Working/library/features.py::measure_snippet`) or
read back from `motif_features` when the Library carries them.

FastAPI lives only in `webui/.venv`, so this file skips under the conda pytest; run it
with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_interrogation_shape.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from Working.library import features as F  # noqa: E402
from Working.library.identity import content_hash  # noqa: E402
from Working.Detection.drop_motifs import store as S  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

SEED_DIR = os.path.join(PROJECT_ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
needs_seed = pytest.mark.skipif(not os.path.isdir(SEED_DIR), reason="seed store absent")
EVENT = "id001_r1_1213252"          # the seed's reference event: depth 15.06 mV, fall 99 s (events.csv)


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES ('syn.mat', 0, 1.0, 10, 0, 'x.npy')")
    conn.commit(); conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture
def rt(tmp_path):
    rt = Runtime(mode="sandbox", stamp="20260930-shape", db_source=str(_db(tmp_path)), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        yield rt
    finally:
        rt.restore()


@pytest.fixture
def client(rt):
    with TestClient(create_app(rt)) as c:
        yield c


@needs_seed
def test_the_shape_route_serves_the_cores_measures_for_every_member(client):
    d = client.get("/api/interrogation/families/id001/shape").json()
    assert d["source"] == "seed" and d["family"] == "id001"
    assert d["counts"]["n"] == 17 and len(d["members"]) == 17
    by_id = {m["event_id"]: m for m in d["members"]}
    f = by_id[EVENT]["features"]
    # the detector's own anchors define the event, so its depth IS the detector's depth (fixup-d: 410/410)
    assert f["event_amplitude_mv"] == pytest.approx(15.06168, abs=1e-3)
    assert f["event_width_s"] == pytest.approx(99.0)
    for k in ("fwhm_s", "recovery_time_s", "duration_s", "rise_time_s", "precursor_height_mv", "max_slope_mv_s", "polarity"):
        assert k in f, k
    # every member says whether its numbers were read from motif_features or measured on the spot
    assert all(m["stored"] is False for m in d["members"]), "the synthetic database carries no motif_features"


@needs_seed
def test_never_recovered_is_null_and_counted_never_zero(client):
    d = client.get("/api/interrogation/families/id001/shape").json()
    rec = [m["features"]["recovery_time_s"] for m in d["members"]]
    assert all(r is None or r > 0 for r in rec), "0 s is not a recovery"
    n_none = sum(1 for r in rec if r is None)
    assert n_none > 0, "id001 is a sharkfin span: fixup-d found events that do not half-recover inside the bound"
    assert d["counts"]["n_not_recovered"] == n_none
    assert d["counts"]["n_no_fwhm"] == sum(1 for m in d["members"] if m["features"]["fwhm_s"] is None)
    # the bound the rule was measured with is on the payload, so the page can print it
    assert d["recovery"] == {"frac": 0.5, "max_mult": 10.0}


@needs_seed
def test_a_drop_has_no_rise_time_on_the_route_either(client):
    d = client.get("/api/interrogation/families/id001/shape").json()
    assert all(m["features"]["rise_time_s"] is None for m in d["members"])
    assert d["counts"]["n_no_rise"] == 17


@needs_seed
def test_nothing_on_the_route_is_a_constant_multiple_of_the_width(client):
    """The three fabrications: half_width = 0.84 x duration, rise = 0.31 x, isi = 4.2 x.
    On id010 (84 trough events) FWHM is measured on 83; on id001 (sharkfin) it is measured on
    none — every event stays low until the next rise, so its half level is never re-crossed."""
    d = client.get("/api/interrogation/families/id010/shape").json()
    width = np.array([m["features"]["event_width_s"] for m in d["members"]], dtype=float)
    fwhm = np.array([np.nan if m["features"]["fwhm_s"] is None else m["features"]["fwhm_s"] for m in d["members"]])
    ok = np.isfinite(fwhm)
    assert ok.sum() >= 80
    ratio = fwhm[ok] / width[ok]
    assert np.std(ratio) > 1e-3, "FWHM over width is not a constant on real events"


@needs_seed
def test_the_rules_ride_beside_the_numbers(client):
    d = client.get("/api/interrogation/families/id001/shape").json()
    names = {r["name"] for r in d["rules"]}
    assert {"recovery", "recovery_time", "fwhm", "rise_time", "event_width", "anchors", "units"} <= names
    anchors = next(r for r in d["rules"] if r["name"] == "anchors")
    assert "detector" in anchors["rule"]
    units = next(r for r in d["rules"] if r["name"] == "units")
    assert "mV" in units["rule"]


@needs_seed
def test_stored_features_are_read_back_by_content_hash(rt):
    """When the Library carries a member's features (fixup-d's backfill), the route reads
    them instead of re-measuring, and says so."""
    snip = S.load_snippets(SEED_DIR)[EVENT]["detrended_mv"]
    digest = content_hash(np.asarray(snip, dtype=float))
    from server import corpus
    conn = corpus.connect(rt.db_path)
    try:
        F.write_features(conn, [{"content_hash": digest, "fs": 1.0, "measures": {"event_amplitude_mv": 15.06168, "fwhm_s": 123.0},
                                 "detector": {"drop_depth_mv": 15.06168}}])
    finally:
        conn.close()
    with TestClient(create_app(rt)) as c:
        d = c.get("/api/interrogation/families/id001/shape").json()
    m = next(x for x in d["members"] if x["event_id"] == EVENT)
    assert m["stored"] is True and m["features"]["fwhm_s"] == 123.0
    assert m["detector"]["drop_depth_mv"] == pytest.approx(15.06168)
    assert d["counts"]["n_stored"] == 1


def test_an_unknown_family_is_404(client):
    assert client.get("/api/interrogation/families/nope/shape").status_code == 404


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
