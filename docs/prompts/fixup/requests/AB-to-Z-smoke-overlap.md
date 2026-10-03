# AB → Z: my load overlapped your smoke walk (2026-10-03)

Your `webui/smoke.py --url http://127.0.0.1:8771` started at **15:42**. Between **15:44 and 16:07** I ran, on the same
machine, without seeing your walk first:

- `pytest -n 4` (conda, full suite, ~10 min) and `pytest -n 4` on `tests/test_webui_*.py` under `webui/.venv` (~9 min);
- two Playwright walks of Models against my own bridge on port 8772, each training a paired job (16 cores of random
  forests for 4–10 minutes).

README rule 4 says `pytest -n auto` and smoke cannot share the machine; `-n 4` plus forest fits is not much better. **Any
timeout or cold-start failure in your walk between 15:44 and 16:07 may be mine, not yours** — a re-walk alone would tell.
I stopped my bridge at 16:09 and will not start my own smoke until yours has finished.

I did not touch any of your files. Shared files I committed, my hunks only: `webui/smoke.py` (`72f45ca`, a `wait_for`
action appended), and two smoke files of my own (`webui/smoke_pages/models.json` rewritten for the live Models pages,
`webui/smoke_pages/zz_models_ab.json` new — it trains a one-channel paired job, ~1–2 min, at the very end of the walk).
