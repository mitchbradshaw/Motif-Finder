"""The NeurIPS demo's front door and the shared seed worker (docs/neurips_demo/DECISIONS.md, Q2/Q3).

The hub (port 8900) is the one address visitors are given (the QR code on its page). It hands every new device its
own station: a free copy, by redirect to that station's port with a claim token. It watches the stations and resets
a claimed one after 10 minutes without input. A device that comes back to the hub while its station is still its own
is sent back to the same station, not given a second one. When all copies are busy, the visitor sees a wait page
that retries by itself. /admin?key=... is the operator's table, with a reset button per station.

The seed worker (127.0.0.1 only) holds the core's matrix-profile code once for every station, so a live seed search
does not cost each station 270 MB and a six-second compile.
"""
from __future__ import annotations

import html
import secrets
import socket
import threading
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from demo_qr import qr_svg

IDLE_RESET_S = 600.0
POLL_S = 5.0
COOKIE = "mw_station"


def lan_urls(port: int) -> list[str]:
    """This machine's IPv4 addresses a phone or laptop on the same network could reach, hotspot first
    (Windows Mobile Hotspot is 192.168.137.1)."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    ips = [ip for ip in ips if not ip.startswith("127.") and not ip.startswith("169.254.")]
    ips.sort(key=lambda ip: (not ip.startswith("192.168.137."), not ip.startswith("192.168."), ip))
    return [f"http://{ip}:{port}/" for ip in ips]


class Station:
    def __init__(self, n: int, port: int):
        self.n, self.port = n, port
        self.claim: str | None = None
        self.idle_s = 0.0
        self.alive = False
        self.claimed_at = 0.0
        self.runs = 0

    def base(self):
        return f"http://127.0.0.1:{self.port}"


def create_hub(*, stations: list[Station], admin_key: str, port: int, public_url: str | None = None,
               http: httpx.Client | None = None, poll: bool = True) -> FastAPI:
    """`http` and `poll` are for tests: a client whose transport reaches in-process stations, and no poller thread."""
    app = FastAPI(title="MycoWave demo hub", docs_url=None, redoc_url=None, openapi_url=None)
    lock = threading.Lock()
    hdr = {"x-demo-admin": admin_key}
    client = http or httpx.Client(timeout=3.0)

    def poll_once():
        for st in stations:
            try:
                r = client.get(f"{st.base()}/api/demo/admin/status", headers=hdr)
                r.raise_for_status()
                d = r.json()
                with lock:
                    st.alive, st.claim, st.idle_s, st.runs = True, d["claim"], float(d["idle_s"]), int(d["runs"])
                if st.claim and st.idle_s > IDLE_RESET_S:
                    client.post(f"{st.base()}/api/demo/admin/reset", headers=hdr)
                    with lock:
                        st.claim = None
            except Exception:
                with lock:
                    st.alive = False

    def poller():
        while True:
            poll_once()
            time.sleep(POLL_S)

    if poll:
        threading.Thread(target=poller, name="hub-poller", daemon=True).start()

    def public():
        if public_url:
            return public_url
        urls = lan_urls(port)
        return urls[0] if urls else f"http://127.0.0.1:{port}/"

    def claim_station(prefer: tuple[int, str] | None):
        poll_once()
        with lock:
            if prefer:
                for st in stations:
                    if st.n == prefer[0] and st.alive and st.claim == prefer[1]:
                        return st, prefer[1], False
            free = [st for st in stations if st.alive and not st.claim]
            if not free:
                free = [st for st in stations if st.alive and st.claim and st.idle_s > IDLE_RESET_S]
            if not free:
                return None, None, False
            st = free[0]
            token = secrets.token_urlsafe(12)
            st.claim, st.claimed_at, st.idle_s = token, time.time(), 0.0
        client.post(f"{st.base()}/api/demo/admin/claim", headers=hdr, json={"token": token}).raise_for_status()
        return st, token, True

    @app.get("/", response_class=HTMLResponse)
    def front():
        return HTMLResponse(_FRONT.replace("{{URL}}", html.escape(public())), headers={"Cache-Control": "no-store"})

    @app.get("/qr.svg")
    def qr():
        return Response(qr_svg(public(), module=7), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})

    @app.get("/claim")
    def claim(request: Request):
        prefer = None
        ck = request.cookies.get(COOKIE)
        if ck and ":" in ck:
            n, tok = ck.split(":", 1)
            if n.isdigit():
                prefer = (int(n), tok)
        st, token, _new = claim_station(prefer)
        if st is None:
            return RedirectResponse("/busy", status_code=303)
        host = request.url.hostname or "127.0.0.1"
        r = RedirectResponse(f"http://{host}:{st.port}/?claim={token}#/welcome", status_code=303)
        r.set_cookie(COOKIE, f"{st.n}:{token}", max_age=3600, samesite="lax")
        return r

    @app.get("/busy", response_class=HTMLResponse)
    def busy():
        with lock:
            alive = [st for st in stations if st.alive]
            soon = min((max(0.0, IDLE_RESET_S - st.idle_s) for st in alive if st.claim), default=None)
        wait = "about a minute" if soon is None or soon < 90 else f"about {int(round(soon / 60))} minutes"
        return HTMLResponse(_BUSY.replace("{{WAIT}}", wait), headers={"Cache-Control": "no-store"})

    @app.get("/api/hub/status")
    def status():
        with lock:
            return {"stations": len(stations), "alive": sum(st.alive for st in stations),
                    "free": sum(1 for st in stations if st.alive and not st.claim), "url": public()}

    @app.get("/admin", response_class=HTMLResponse)
    def admin(key: str = ""):
        if key != admin_key:
            raise HTTPException(403, "admin only: /admin?key=<the key the launcher printed>")
        with lock:
            rows = "".join(
                f"<tr><td>{st.n}</td><td>{st.port}</td><td>{'up' if st.alive else '<b style=color:#e5484d>down</b>'}</td>"
                f"<td>{'in use' if st.claim else 'free'}</td><td>{st.idle_s:.0f} s</td><td>{st.runs}</td>"
                f"<td><form method=post action='/admin/reset/{st.n}?key={key}'><button>Reset</button></form></td></tr>"
                for st in stations)
        return HTMLResponse(_ADMIN.replace("{{ROWS}}", rows).replace("{{URL}}", html.escape(public())),
                            headers={"Cache-Control": "no-store"})

    @app.post("/admin/reset/{n}")
    def admin_reset(n: int, key: str = ""):
        if key != admin_key:
            raise HTTPException(403, "admin only")
        st = next((s for s in stations if s.n == n), None)
        if st is None:
            raise HTTPException(404, f"no station {n}")
        client.post(f"{st.base()}/api/demo/admin/reset", headers=hdr).raise_for_status()
        with lock:
            st.claim = None
        return RedirectResponse(f"/admin?key={key}", status_code=303)

    return app


class LiveSeed(BaseModel):
    slice: int
    a: int
    b: int


def create_seed_worker(*, admin_key: str) -> FastAPI:
    from demo_station import Store, STORE
    import demo_live

    store = Store(STORE)
    app = FastAPI(title="MycoWave demo seed worker", docs_url=None, redoc_url=None, openapi_url=None)
    ready = threading.Event()

    def warm():
        demo_live.warm(store)            # every channel's and noise copy's FFT, once
        ready.set()

    threading.Thread(target=warm, name="seed-warm", daemon=True).start()

    @app.get("/health")
    def health():
        return {"ready": ready.is_set()}

    @app.post("/search")
    def search(body: LiveSeed, request: Request):
        if request.headers.get("x-demo-admin") != admin_key:
            raise HTTPException(403, "stations only")
        ready.wait(60)
        try:
            return demo_live.live_search(store, body.slice, body.a, body.b)
        except ValueError as e:
            raise HTTPException(400, str(e))

    return app


_STYLE = """
<style>
 :root{--blue:#0a84ff;--green:#22a06b;--green-600:#1a8a5a;--text:#111827;--muted:#6b7280;--border:#e5e7eb;--bg:#f5f6f8}
 *{box-sizing:border-box} body{margin:0;font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;color:var(--text);
 background:radial-gradient(1200px 600px at 20% 0%,#e6f1ff 0%,var(--bg) 55%);min-height:100vh;display:flex;align-items:center;justify-content:center}
 .card{background:#fff;border:1px solid var(--border);border-radius:18px;box-shadow:0 20px 60px rgba(17,24,39,.08);padding:44px 52px;max-width:880px;width:92vw}
 h1{font-size:44px;margin:0 0 6px;letter-spacing:-.02em} h1 span{color:var(--blue)} .sub{font-size:19px;color:var(--muted);margin:0 0 28px;line-height:1.45}
 .row{display:flex;gap:40px;align-items:center;flex-wrap:wrap} .go{display:inline-block;background:var(--green);color:#fff;font-size:20px;font-weight:600;
 padding:16px 34px;border-radius:12px;text-decoration:none;box-shadow:0 6px 18px rgba(34,160,107,.35)} .go:hover{background:var(--green-600)}
 .qr{text-align:center;color:var(--muted);font-size:14px} .qr img{width:190px;height:190px;border:1px solid var(--border);border-radius:12px;display:block;margin:0 auto 8px}
 .url{font-family:'Geist Mono',Consolas,monospace;font-size:15px;color:var(--text)} .small{color:var(--muted);font-size:14px;margin-top:22px}
 .wave{height:56px;margin:4px 0 18px} table{border-collapse:collapse;width:100%;font-size:15px} td,th{border-bottom:1px solid var(--border);padding:8px;text-align:left}
</style>"""

_WAVE = ('<svg class="wave" viewBox="0 0 600 56" preserveAspectRatio="none"><path fill="none" stroke="#0a84ff" stroke-width="2.2" '
         'd="M0 22 L60 22 L70 20 L78 46 L96 24 L150 22 L162 21 L170 50 L190 25 L260 23 L268 21 L276 40 L292 24 L360 22 L372 20 '
         'L380 52 L402 26 L470 23 L478 21 L486 44 L504 24 L600 22"/></svg>')

_FRONT = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>MycoWave · live demo</title>{_STYLE}</head><body><div class=card>
<h1>Myco<span>Wave</span></h1>{_WAVE}
<p class=sub>Fungi send electrical spikes through their mycelium. MycoWave finds them in weeks of recordings,
sorts them into families, and lets you search for more like any one you pick.</p>
<div class=row><div><a class=go id=go href="/claim">Start the demo</a>
<p class=small>You get your own private copy. Nothing you do affects anyone else. <span id=free></span></p></div>
<div class=qr><img src="/qr.svg" alt="QR code"><div>Scan to try it on your own laptop or tablet</div><div class=url>{{{{URL}}}}</div></div></div>
<div id=phone style="display:none" class=small><b>On a phone?</b> MycoWave draws long recordings and needs a wider screen:
please use a laptop or a tablet, or the screen on the table. <a href="/claim">Continue anyway</a></div>
</div><script>
async function free() {{ try {{ const r = await (await fetch('/api/hub/status')).json();
  document.getElementById('free').textContent = r.free + ' of ' + r.stations + ' copies free.' }} catch (e) {{}} }}
free(); setInterval(free, 5000);
if (Math.min(screen.width, screen.height) < 600 && /Mobi|Android|iPhone/i.test(navigator.userAgent)) {{
  document.getElementById('phone').style.display = 'block'; document.getElementById('go').style.display = 'none' }}
</script></body></html>""".replace("{{{{URL}}}}", "{{URL}}")

_BUSY = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta http-equiv=refresh content="10;url=/claim"><title>MycoWave · all stations busy</title>{_STYLE}</head><body><div class=card>
<h1>Myco<span>Wave</span></h1><p class=sub>Every copy of the demo is in use right now. A copy frees up after its visitor
has been away for a few minutes: {{{{WAIT}}}}. This page tries again by itself.</p>
<a class=go href="/claim">Try again</a></div></body></html>""".replace("{{{{WAIT}}}}", "{{WAIT}}")

_ADMIN = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta http-equiv=refresh content=5>
<title>MycoWave · stations</title>{_STYLE}</head><body><div class=card><h1>Stations</h1>
<p class=sub>Visitors join at <span class=url>{{{{URL}}}}</span>. A station in use with no input for 10 minutes is reset by itself.</p>
<table><tr><th>#</th><th>port</th><th>process</th><th>state</th><th>idle</th><th>runs</th><th></th></tr>{{{{ROWS}}}}</table>
</div></body></html>""".replace("{{{{URL}}}}", "{{URL}}").replace("{{{{ROWS}}}}", "{{ROWS}}")
