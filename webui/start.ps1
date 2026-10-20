# One-command start for the web UI (React + TypeScript + FastAPI bridge).
#   .\start.ps1            -> builds the client if needed, serves http://127.0.0.1:8765 in SANDBOX mode
#   .\start.ps1 -Dev       -> FastAPI on 8765 + Vite dev server on 5173 (proxy /api)
#   .\start.ps1 -Project   -> PROJECT mode: the REAL DATA/db/annotations.sqlite opened in place (WAL)
#                             after a timestamped backup to DATA/db/backups/; nothing redirected
#   -NoOpen                -> do not open the browser
# The browser opens BY ITSELF once the bridge answers (2026-10-20). The bridge runs in the foreground of this terminal,
# and a second command typed or run into the same terminal while it starts -- the old "then open the site" step --
# reaches it as Ctrl+C: the bridge and its map worker died with a KeyboardInterrupt ~7 s after a start (the
# "first try always cancels" report). Run nothing else in this terminal; Ctrl+C here is how you stop the bridge.
param([switch]$Dev, [switch]$Project, [switch]$NoOpen, [int]$Port = 8765)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $here ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "creating project-local venv (system-site-packages) and installing fastapi/uvicorn"
  & "C:\ProgramData\anaconda3\python.exe" -m venv --system-site-packages (Join-Path $here ".venv")
  & $py -m pip install --quiet fastapi "uvicorn[standard]"
}
$client = Join-Path $here "client"
if (-not (Test-Path (Join-Path $client "node_modules"))) { Push-Location $client; npm install --no-audit --no-fund; Pop-Location }
$modeArg = if ($Project) { "--project" } else { "--sandbox" }
if (-not $NoOpen) {
  # a hidden PowerShell in its OWN console waits for the bridge's health route, then opens the page; it never shares
  # this console, so it can neither receive nor send this terminal's Ctrl+C
  $health = "http://127.0.0.1:$Port/api/health"
  $page = if ($Dev) { "http://127.0.0.1:5173" } else { "http://127.0.0.1:$Port" }
  $probe = "for (`$i = 0; `$i -lt 240; `$i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '$health' | Out-Null; Start-Sleep -Seconds 1; Start-Process '$page'; break } catch { Start-Sleep -Seconds 1 } }"
  Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', $probe | Out-Null
  Write-Host "the browser opens at $page when the bridge answers (up to 4 min); stop the bridge with Ctrl+C in THIS terminal"
}
if ($Dev) {
  Start-Process -NoNewWindow -FilePath $py -ArgumentList "`"$here\run_server.py`" --port $Port $modeArg"
  Push-Location $client; npm run dev; Pop-Location
} else {
  if (-not (Test-Path (Join-Path $client "dist\index.html"))) { Push-Location $client; npm run build; Pop-Location }
  & $py (Join-Path $here "run_server.py") --port $Port $modeArg
}
