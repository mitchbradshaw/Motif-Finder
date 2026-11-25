# MycoWave at NeurIPS: the booth demo

## In plain words

This is a small, fast copy of MycoWave built for strangers at a booth. Think of it as a museum exhibit rather than
the workshop.

- It holds three mushrooms (lion's mane, oyster, split gill), one day of four electrodes each.
- Every answer a visitor can ask for was worked out in advance, overnight, so every click answers at once.
- Each visitor's device gets its own private copy (a "station"). What one person builds never appears on another's
  screen.
- Visitors join by scanning a QR code on the booth laptop's screen. Their laptop or tablet then talks to the booth
  laptop over the laptop's own Wi-Fi hotspot. Nothing needs the internet.

The choices behind it are in [DECISIONS.md](DECISIONS.md).

## Starting it at the booth

1. **Turn on the hotspot.**
   - Windows Settings › Network & internet › Mobile hotspot › On.
   - Note its network name and password: visitors need them before the QR code can work.
   - The laptop's address on its own hotspot is normally `192.168.137.1`.
2. **Start the demo** from a terminal in the demo checkout:

       cd C:\Users\mmebr\Documents\CNN-neurips
       ..\CNN\webui\.venv\Scripts\python.exe webui\server\demo_launch.py --stations 6 --port 8900 --public-url http://192.168.137.1:8900/

   It prints the addresses and the operator page's link. Leave the terminal open; Ctrl+C stops everything.
3. **Open `http://127.0.0.1:8900/`** in a browser on the laptop and put it full screen. That page is the front door:
   it carries the QR code and a big "Start the demo" button for whoever uses the laptop itself.
4. **First time on a new network only:** Windows Firewall asks whether Python may accept connections. Allow it on
   private networks; without that, the QR code works for nobody but the laptop. To do it by hand, as administrator:

       New-NetFirewallRule -DisplayName "MycoWave demo" -Direction Inbound -Protocol TCP -LocalPort 8900-8906 -Action Allow -Profile Private

   (Claude did not change the firewall. It is a security setting, so it is yours to change.)

## During the day

| What | How |
|---|---|
| See which stations are in use | `http://127.0.0.1:8900/admin?key=<key>`: the launcher prints the key, or pass `--admin-key` |
| Free a station by hand | the Reset button on the operator page |
| A visitor walks away | their station resets itself after 10 minutes with no clicks |
| A visitor wants a clean slate | "Start over", bottom left of every page |
| All six stations in use | the next visitor sees "busy"; that page retries by itself every 10 s |
| A station crashes | the launcher starts it again within seconds; its visitor keeps their copy |
| The guided tour | starts from the welcome page ("Take the 3-minute tour"), or "? Tour" in the rail |

The laptop has 14 GB of memory. Close Opera, Chrome and other heavy programs before the session: the six stations
plus the seed worker need about 1.5 GB.

## What a visitor can do

The eight stops, in the rail on the left:

1. **Explore** one electrode's 24 hours. Auto-detect draws every drop it finds (the 24 Nov drop pool, v4). Drag to
   mark a stretch.
2. **Analyse** the stretch: the thesis drop detector, step by step (raw → cleaned → events → their shapes).
3. **Build** your own detector: three slots with notched knobs, 108 settings in all, each one pre-computed.
4. **Discovery:** your detector on all 12 electrodes, against chance (10 noise copies of each), beside three
   detectors you prepared.
5. **Judge five** of the detections. Each counts as yes, no or not sure, and is compared with your verdicts where you
   judged the same stretch.
6. **Library:** your accepted drops in these recordings, in shape families, and the trains they form.
7. **Seed search:** a shelf of seeds searched in advance, plus any stretch a visitor marks (five minutes or less),
   searched live.
8. **Spike statistics:** the three species side by side. Rate, gaps (CV, LV), depth against width, every event at
   its own size, the steepest-slope rose.

## Rebuilding the data (only if the choices change)

Run everything from the demo checkout, in order. The scripts read the real `DATA/` read only and write only under
`DATA/neurips_demo/`:

    "/c/ProgramData/anaconda3/python.exe" scripts/neurips_demo/build_slices.py
    "/c/ProgramData/anaconda3/python.exe" scripts/neurips_demo/precompute_chains.py --workers 3
    "/c/ProgramData/anaconda3/python.exe" scripts/neurips_demo/precompute_extras.py
    ../CNN/webui/.venv/Scripts/python.exe scripts/neurips_demo/precompute_summaries.py
    cd webui/client && npm run build:neurips

What to change, and where:

- The datasets, windows and builder menu are in `scripts/neurips_demo/demo_config.py`.
- The chain grid takes about 1.5 hours on three workers; the other stages take minutes.
- Check the result by walking it:

      "/c/ProgramData/anaconda3/python.exe" scripts/neurips_demo/walk.py --visitors 6

  Use `--tour` to follow the guided tour instead. It fails on any console error, red card or failed request.

## Moving it to another laptop

Copy the whole `CNN-neurips` folder. It has no junctions, so a plain copy works. The other laptop then needs Python
with the packages of `webui/.venv` (fastapi, uvicorn, httpx, numpy, stumpy) and the built `webui/client/dist-neurips`.
It does not need the real `DATA/`: everything the demo reads is in `DATA/neurips_demo/`.

| Folder | Size |
|---|---|
| `DATA/neurips_demo/store` | ~110 MB |
| `DATA/neurips_demo/slices` | 11 MB |
