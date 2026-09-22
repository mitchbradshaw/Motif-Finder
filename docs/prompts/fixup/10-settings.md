# Fixup 10 — Settings: the sixteen pages

**Status: skeleton.** Symptoms only. The prompt body is written after `QUESTIONS.md` Q-S1…Q-S3.

Settings is the most complete workspace in the app: all 17 reads are live, fourteen project pages read
and write the `settings` table, every save is audited, and the held-out unlock is refused server-side
without the typed name. What is below is mostly *settings that exist and are inert*.

## Symptoms

| # | Symptom | Evidence |
|---|---|---|
| S1 | **Datasets need better names and more information.** Settings › Datasets is where a dataset's identity is authored, so it is where X4 is fixed: species, organism, duration, channel count, fs and provenance are in `recordings` and its sidecar manifests but the display name is the source file. | user; `00-cross-cutting.md` X4 |
| S2 | **Settings › Nulls offers a method the block does not implement** — *circular shift of the channel*. The block implements `phase_randomize` and `block_shuffle`; `resolve_null` refuses the third out loud. Wiring's recommendation: change the chip, not the block. | wiring `reports/04-discovery.md` questions table |
| S3 | **Nulls' `alpha` and multiple-comparison correction are inert** — the seeded search does not read them and computes at a hard-coded α = 0.01 with no correction. | wiring `reports/04-discovery.md` Left |
| S4 | **Settings › Library groupings has no row for the default cut** (0.60, measured), which lives in `scripts/populate_library.py`; and no per-unit default for the `≥ N members` filter, which is why the sequences atlas shows 1 of 26 families. | wiring `reports/03-library.md` §8.3, §8.10 |
| S5 | **Blocks on/off in the settings table** was filed by Prompt 02 to Prompt 01 and not done; **block version and null declarations need an adapter-contract field** before the Blocks page can be honest about either. | wiring `reports/02-settings-import.md` §"Requests written", chat summary |
| S6 | **F2B is unregistered** because its fs is not in the file and there is no time vector or overlapping recording to infer one from. One Import click away once the rate is known. | wiring `reports/02-settings-import.md` Q8 |
| S7 | **Three of thirteen matrix profiles were refused for length**, honestly. | wiring `reports/02-settings-import.md` |
| S8 | **The Display theme does not repaint** (pre-existing). Display and Keyboard are the two personal pages and persist in `localStorage` only. | wiring `reports/02-settings-import.md` Left |
| S9 | **Backups on a schedule are a setting only** — nothing runs while the bridge is down, and restore is a by-hand copy with the bridge stopped. Deliberate; worth a sentence on the page. | wiring `reports/02-settings-import.md` Q5 |
| S10 | **"Code your own algorithm" would most plausibly live here**, and Settings is also where the `EXCERPT_MAX_SAMPLES` and onset-coefficient style constants (`0.25 × duration`, `EXCERPT_MAX_SAMPLES = 200,000`) would be exposed if they should be. | user; `00-cross-cutting.md` X5; wiring `reports/02-settings-import.md` Q6; `reports/03-library.md` §8.4 |

## Goal · Work · Testing and critique · Report

*(written after the questions)*
