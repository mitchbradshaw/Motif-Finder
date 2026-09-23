"""
units.py
========
The unit a recording's samples are stored in, and the one factor from it to
millivolts (fixup-b, docs/prompts/fixup/B-units-and-amplitude.md).

The derived channels are not all in one unit — the M2 exports and
Mushroom_260720 are volts, L_LM_Jul_26_J is millivolts — and for two years
nothing on the data said which. The web UI labelled every one "mV" and never
converted, so every amplitude it printed for a volts file was 1000x too small.
The unit now lives on the data (`recordings.units`, the manifest's `units`
key), and this module is its vocabulary:

    parse_units(text)  -> 'V' | 'mV' | 'uV' | None     what a manifest's text means
    to_mv_factor(unit) -> 1000.0 | 1.0 | 0.001 | None  None: undeclared, never assumed

The core does not convert: detection code (`detect5`, `store`) expects volts
and multiplies by 1000 itself. The factor is for drawing, at the bridge's one
display seam (`webui/server/corpus.py::display_channel`).

`RECORDING_UNITS_EVIDENCE` is what was measured for each registered source
file on 2026-09-23. `init_db()` backfills it onto rows that carry no unit and
no note, so a unit a person later declares is never overwritten. A file whose
unit could not be verified is recorded as undeclared WITH the reason: a wrong
unit asserted confidently is a research claim, an honest `None` is not.
"""
from __future__ import annotations

import re

UNITS = ("V", "mV", "uV")

UNITS_TO_MV = {"V": 1000.0, "mV": 1.0, "uV": 0.001}

_SPELLINGS = {
    "v": "V", "volt": "V", "volts": "V",
    "mv": "mV", "millivolt": "mV", "millivolts": "mV",
    "uv": "uV", "µv": "uV", "μv": "uV", "microvolt": "uV", "microvolts": "uV",
}


def parse_units(text) -> str | None:
    """The canonical unit a piece of text names, or None.

    Reads the first word only, so the free text a manifest may carry
    ("millivolts as stored (everything else on disk is volts; …)") is read as
    the unit it opens with. Anything it does not recognise is None — the
    caller decides whether that is "undeclared" or "unreadable".
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    first = re.split(r"[\s(,;:]+", s, maxsplit=1)[0]
    return _SPELLINGS.get(first.lower())


def to_mv_factor(units: str | None) -> float | None:
    """Multiply a stored sample by this to get millivolts. None when the unit
    is undeclared: an undeclared unit is never assumed to be 1."""
    if units is None:
        return None
    return UNITS_TO_MV.get(units)


def describe(units: str | None) -> str:
    """How a page names the unit it draws in."""
    return "mV" if to_mv_factor(units) is not None else "unit undeclared"


# The measurements behind each registered source file's unit, 2026-09-23. The
# full table with numbers is docs/prompts/fixup/reports/B-units-and-amplitude.md
# §2. `None` means undeclared, and its note says why.
_VERIFIED = "verified 2026-09-23 (fixup-b): "
_UNDECLARED = "undeclared (fixup-b, 2026-09-23): "
_DECLARE = " Declare it in Settings › Datasets once it is known."
RECORDING_UNITS_EVIDENCE: dict[str, tuple[str | None, str]] = {
    "M2_aug_concat_fs1.mat": ("V", _VERIFIED + (
        "the drop-motif seed store's __raw_mv snippets equal these samples x 1000 bit-exactly "
        "(410 events, max |ratio - 1000| 1.1e-13); motif depths then run 1.2-98 mV, median 9.1 mV, "
        "and sample-to-sample noise is 0.025 mV (MAD) — the band and the 0.1 mV floor the researcher states for M2.")),
    "M2_aug_concat_fs2.mat": ("V", _VERIFIED + (
        "the same M2_aug experiment at 2 Hz: its baselines and noise match the verified fs1 file "
        "(CH0 median -0.437 vs -0.430, MAD 0.030 vs 0.025); read as mV they would sit 1000x from it.")),
    "M2_concat_fs1.mat": ("V", _VERIFIED + (
        "the M2 export family by scale only — baselines -0.11 to -0.63, noise MAD 0.010-0.013 mV if volts, "
        "the verified M2_aug range; no store snippet covers this file.")),
    "Mushroom_260720_0509_4hrs_CH14_fs1.mat": ("V", _VERIFIED + (
        "the seed store's __raw_mv snippets equal these samples x 1000 (24 events); and L_LM_Jul_26_J CH2, "
        "block-meaned 10:1 at sample 15,777,590, equals 998.2 x these samples + 298 (r = 0.9995).")),
    "L_LM_Jul_26_J_raw.mat": ("mV", _VERIFIED + (
        "its CH2 block-meaned 10:1 is 998.2 x the Mushroom_260720 excerpt, a volts file — the x1000 of a "
        "millivolt recording (Pipelines/drop_motifs/lionsmane12.py found the same); noise MAD 0.03-0.25 mV.")),
    "M4_aug_concat_fs1.mat": (None, _UNDECLARED + (
        "held out (spec §0 D6) and not opened for this check; its unit is not asserted by analogy." + _DECLARE)),
    "Fig2A_dt0p1.csv": (None, _UNDECLARED + (
        "the CSV carries no unit and is a synthetic fixture; every detector run assumed volts, which was "
        "never confirmed (Plots/drop_motifs8_fig2a/PROVENANCE.md §5)." + _DECLARE)),
    "M1.mat": (None, _UNDECLARED + (
        "another source; no snippet, catalogue depth or instrument record to check it against. Read as volts "
        "its baseline is -0.10 V and its noise 0.046 mV (MAD) — plausible, not verified." + _DECLARE)),
    "M100.mat": (None, _UNDECLARED + (
        "another source, and a high-passed M1 (first differences correlate 0.986, gain 0.977): the same unit "
        "as M1, whichever that is." + _DECLARE)),
    "M101_t.mat": (None, _UNDECLARED + (
        "another source; same quantisation and scale as M100, so the same unit as M1, whichever that is." + _DECLARE)),
    "MJu26a.mat": (None, _UNDECLARED + (
        "another source; samples are quantised in exact 1e-6 steps (1 µV if volts, 1 nV if millivolts) — "
        "suggestive of volts, not verified." + _DECLARE)),
}
