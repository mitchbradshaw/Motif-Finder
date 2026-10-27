# Z — environment series on the overlay: the MJu26 sensor log

**From:** the cross-channel workshop, 2026-10-27, Q14 (`docs/prompts/changes/cross-channel-explorer-decisions.md`,
D13). **Not in the build.** S9 of `cross-channel-explorer.md` makes the overlay able to hold a series from another
recording, with its own offset and its own unit (°C, %RH, kg). This stub is the registration of the environment logs
themselves, and their first use.

## The researcher's words

> attached is the sensor data for MJu26 — the only dataset of the 7 with sensor data. This has temperature, pressure,
> particle meter (from 2.5 - 10 microns) etc.
>
> … the idea of the cross-channel page I think I want to evolve into exploring not only propagation, but spatial and
> environment relationships too.

## The file (read 2026-10-27, not copied into the repo)

**Where it is.**
- `C:\Users\mmebr\Downloads\Sensor data[09C00,09C05,09C0F,0D697,0D699,0D6A0,0D6A3,0195C,01960,01966,019A0,09C09]
  (2026-07-01-2026-07-28).csv`: 30.8 MB, 402,191 rows × 44 columns.
- When registered it belongs under `DATA/raw/` (gitignored), never in git.

**Its shape.**
- `Time` is local wall-clock with **no time zone**, from `2026-07-01 00:00:03` to `2026-07-28 14:03:03`, strictly
  increasing (≈ 662 h).
- Every device writes on its **own timestamps**, so the table is sparse: each row fills only one device's columns.

**The devices.** Each reads about once a minute (median 60 s; the PM meters 62–64 s; p95 ≤ 65 s; no gap over 0.1 h).

| Devices | Columns | Range seen | Note |
|---|---|---|---|
| 4 × Aranet4: 09C00, 09C05, 09C09, 09C0F | temperature °C, humidity %, pressure hPa, CO₂ ppm, battery V | 19.6–24.0 °C; humidity 33–70 (09C00), **74–99 (09C05)**, 41–73 (09C0F); 1015–1029 hPa; CO₂ 397–834 ppm | **09C09 is listed but empty.** 09C05's high humidity suggests it sits inside a humid enclosure |
| 4 × PM meter: 0D697, 0D699, 0D6A0, 0D6A3 | PM1, PM2.5, PM10 µg/m³, battery V | 0D697: 0–15; the other three reach **1024**, which looks like the sensor's ceiling (clipped readings, perhaps mist from a humidifier) | Treat 1024 as clipped; never average it as a reading |
| 4 × scale: 0195C, 01960, 01966, 019A0 | weight kg, battery V | about −0.26…−0.19, 0.19…0.20, −0.22…−0.14, −0.04…0.005 | Tared offsets with gram-level drift. Four scales and four packs: possibly **one scale per pack** (water loss or growth) |

## What registering it needs

1. **Which device sits with which pack** of MJu26a (16 channels; packs to be set in Settings › Channels & events).
   Ask the researcher; a photo would settle it.
2. **MJu26a's start time and time zone** (Settings › Datasets has the fields). Without them the log's wall clock
   cannot be aligned with the recording's elapsed seconds. MJu26a is 635.9 h (26.5 d) and the log 662 h, so the
   recording sits inside the log, with the offset unknown.
   - Check whether the raw `MJu26a.mat` time vector carries an absolute start.
   - If nothing does, align by hand on the overlay (S9's offset handle), and **say so wherever a result uses it**, as
     B10 does for M101_t.
3. **A covariate-series registration path** (the thesis's future-work item "covariate series in registration").
   - Store each series as a channel-like array on disk, resampled onto a uniform 60 s grid by linear interpolation,
     never across a gap over 5 min.
   - Attach it to the recording with a unit and a device id. Do not store it as a recording of signals: it must not
     enter detector sweeps, the Library or Discovery.
4. **Overlay use:** add a series from "+ channel › environment…". It draws on its own unit's gain and is never
   correlated with a channel for lag (no shared electrode clock). An event-rate-against-covariate view is its own
   question (B10's shape: hourly rates, circular-shift null).

## Questions it opens

- Do drop rates or the census's shared-driver co-occurrences rise with humidity steps, CO₂ or temperature? A
  circular-shift null, reported across the plausible clock offsets until the start time is known.
- Do weight changes (water loss or growth) track a pack's activity?
- PM spikes at 1024 could be humidifier bursts. If so, they are a ready-made **stimulus log** for shared-driver events
  across packs.
