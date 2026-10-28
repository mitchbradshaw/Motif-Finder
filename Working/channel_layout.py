"""
channel_layout.py
=================
ONE definition of a channel's PACK and POSITION (cross-channel explorer S0; decisions D2, D9, D10 in
`docs/prompts/changes/cross-channel-explorer-decisions.md`). The census (S1), the pack chips (S2) and
Settings › Channels & events (S3) all read it here; nothing else may guess a pack.

In plain words: a recording's electrodes sit on separate mushroom packs, and a signal can only travel
through mycelium between electrodes of the same pack. M2's channel names carry their pack in the letter
(`CH3_A2` is on pack A). Every other dataset is one *unassigned* pack until the researcher sets packs in
Settings › Channels & events, which also holds each electrode's position in millimetres.

Keys, on settings page `channels-events`, with exactly the `<rec>` and `<ch>` that page already uses for
`ground.<rec>.<ch>`: `<rec>` is the registry's directory stem (`list_registered(conn, "recording")`'s
`name`) and `<ch>` the channel's display name (`Working.discovery.channels.channel_name`).

    pack.<rec>.<ch>     a pack label (short text; "" or absent = no pack from Settings)
    x_mm.<rec>.<ch>     the electrode's x position, mm
    y_mm.<rec>.<ch>     its y position, mm

Where a channel's pack comes from (`pack_from`), first match wins: `settings`, then `name` (the letter of
an M2-style name in `M2_STYLE_NAMES`), then `unassigned`. A Settings label is stripped and upper-cased
(so "b" is M2's pack B), and the word "unassigned" is reserved: setting it raises ValueError (leave the
pack blank instead). Every unplaced channel is in the one `unassigned` pack (D10): two unassigned channels
count as the same pack, which keeps propagation allowed on an unknown layout, and the layout says "packs
not set — layout unknown".

`same_pack` is three-valued (critic, 2026-10-28): True for one pack, False for two known packs, and
**None** when exactly one of the two channels is unassigned. On a partly set layout that pair's relation
is unknown; a quiet False would turn real propagation into a shared driver (D9), so the caller must
count it apart.

Loud failure: a position that is set but cannot be read as a number (or is a boolean) raises ValueError
naming its key, and a key saved under a channel name the recording does not have is listed in
`orphan_keys`, never silently dropped. The held-out recording raises PermissionError while its lock is
on, the same predicate as every Explore read.

No UI library (CLAUDE.md rule 1).
"""

from __future__ import annotations

import math
import re

from Working.discovery.channels import M2_STYLE_NAMES, channel_name

#: The settings page the keys live on (Settings › Channels & events).
PAGE = "channels-events"
#: The pack of every channel nobody has placed (D10).
UNASSIGNED = "unassigned"
#: What a layout says while any channel has no pack from Settings or its name.
LAYOUT_UNKNOWN = "packs not set — layout unknown"

_M2_LETTER = re.compile(r"^CH\d+_([A-Z])\d+$")


def pack_key(rec: str, ch: str) -> str:
    """`pack.<rec>.<ch>`, the format of the page's `ground.<rec>.<ch>`."""
    return f"pack.{rec}.{ch}"


def x_key(rec: str, ch: str) -> str:
    return f"x_mm.{rec}.{ch}"


def y_key(rec: str, ch: str) -> str:
    return f"y_mm.{rec}.{ch}"


def _name_pack(name: str) -> str | None:
    """The pack letter of an M2-style electrode name (`CH3_A2` -> `A`), else None."""
    if name not in M2_STYLE_NAMES:
        return None
    m = _M2_LETTER.match(name)
    return m.group(1) if m else None


def _label(values: dict, key: str) -> str | None:
    """A Settings pack label, stripped and upper-cased; None when absent or blank."""
    v = values.get(key)
    if v is None:
        return None
    label = str(v).strip().upper()
    if not label:
        return None
    if label == UNASSIGNED.upper():
        raise ValueError(f"{key} = {v!r} in Settings › Channels & events: {UNASSIGNED!r} is reserved for channels "
                         "with no pack; leave the pack blank instead")
    return label


def _mm(values: dict, key: str) -> float | None:
    v = values.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise ValueError(f"{key} = {v!r} in Settings › Channels & events is not a number of millimetres")
    try:
        out = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{key} = {v!r} in Settings › Channels & events is not a number of millimetres") from None
    if not math.isfinite(out):
        raise ValueError(f"{key} = {v!r} in Settings › Channels & events is not a finite number of millimetres")
    return out


def channel_layout(conn, source_file: str, registered=None) -> dict:
    """Every active channel of `source_file`: its pack and position.

    Returns `{source_file, rec, channels: {recording_id: {name, channel, pack, pack_from, x_mm, y_mm}},
    packs, layout_known, positions_known, note, orphan_keys, settings_updated_at}`. `layout_known` is true
    when every channel's pack comes from Settings or its name; `positions_known` when every channel has both
    x and y; `note` is `LAYOUT_UNKNOWN` whenever the layout is not known; `orphan_keys` lists this
    recording's keys whose channel name it does not have; `settings_updated_at` is the channels-events
    page's last save (a census hashes it, so a pack change marks it stale).

    `registered` is `list_registered(conn, "recording")` when the caller reads several files, so the
    registry is read once. Raises LookupError for a file with no active registered channel, and
    PermissionError for the held-out recording while its lock is on."""
    from Working.registration.core import list_registered
    from Working.registration.settings import HELD_OUT_FILE, get_settings, held_out_locked, settings_meta

    if source_file == HELD_OUT_FILE and held_out_locked(conn):
        raise PermissionError(f"{source_file} is held out and locked; its layout is not read")
    entries = registered if registered is not None else list_registered(conn, "recording")
    entry = next((r for r in entries if r["source_file"] == source_file), None)
    if entry is None:
        raise LookupError(f"no registered recording {source_file!r}")
    rec, n = entry["name"], int(entry["n_channels"])
    values = get_settings(conn, PAGE)
    channels = {}
    for c in entry["channels"]:
        name = channel_name(source_file, c["channel"], n)
        set_pack = _label(values, pack_key(rec, name))
        letter = _name_pack(name)
        if set_pack:
            pack, pack_from = set_pack, "settings"
        elif letter:
            pack, pack_from = letter, "name"
        else:
            pack, pack_from = UNASSIGNED, "unassigned"
        channels[int(c["id"])] = {"name": name, "channel": int(c["channel"]), "pack": pack, "pack_from": pack_from,
                                  "x_mm": _mm(values, x_key(rec, name)), "y_mm": _mm(values, y_key(rec, name))}
    layout_known = all(row["pack_from"] != "unassigned" for row in channels.values())
    positions_known = all(row["x_mm"] is not None and row["y_mm"] is not None for row in channels.values())
    names = {row["name"] for row in channels.values()}
    prefixes = [f"{field}.{rec}." for field in ("pack", "x_mm", "y_mm")]
    orphan_keys = sorted(k for k in values for p in prefixes if k.startswith(p) and k[len(p):] not in names)
    return {"source_file": source_file, "rec": rec, "channels": channels,
            "packs": sorted({row["pack"] for row in channels.values()}),
            "layout_known": layout_known, "positions_known": positions_known,
            "note": None if layout_known else LAYOUT_UNKNOWN, "orphan_keys": orphan_keys,
            "settings_updated_at": settings_meta(conn, PAGE)["updated_at"]}


def _row(layout: dict, recording_id) -> dict:
    """A channel's row by recording id, whether the layout's keys are ints (fresh) or strings (after JSON)."""
    chans = layout["channels"]
    for key in (recording_id, str(recording_id)):
        if key in chans:
            return chans[key]
    try:
        return chans[int(recording_id)]
    except (KeyError, ValueError, TypeError):
        raise KeyError(f"recording {recording_id!r} is not a channel of {layout.get('source_file')}") from None


def same_pack(layout: dict, a, b) -> bool | None:
    """Are recordings `a` and `b` on one pack? True or False when both packs are known, or both channels are
    unassigned (one pack, D10: propagation between them stays allowed). None when exactly one of the two is
    unassigned: on a partly set layout their relation is unknown, and the caller counts it apart."""
    ra, rb = _row(layout, a), _row(layout, b)
    if (ra["pack_from"] == "unassigned") != (rb["pack_from"] == "unassigned"):
        return None
    return ra["pack"] == rb["pack"]
