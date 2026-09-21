"""
channels.py
===========
What a channel is called, in one place.

The M2-style electrode names (`CH4_A2` — channel number plus its electrode
pair) are what a researcher uses to name a channel, and both the core and the
bridge need them: Discovery's scope, its fan-out targets and its scoreboard
rows all carry a channel *name*, while the database keys channels by integer.
The table used to live only in ``webui/server/corpus.py``; a second copy in
the core drifted from it within an hour of being written, which is why it is
here, imported by both, rather than restated.

The fallback is ``CH<n+1>`` — one-based, like the electrode names — for any
recording that is not a sixteen-channel M2-style file.
"""

#: The sixteen M2-style electrode names, in channel order.
M2_STYLE_NAMES = ("CH1_A1", "CH2_A1", "CH3_A2", "CH4_A2", "CH5_B1", "CH6_B1", "CH7_B2", "CH8_B2",
                  "CH9_C1", "CH10_C1", "CH11_C2", "CH12_C2", "CH13_D1", "CH14_D1", "CH15_D2", "CH16_D2")

M2_STYLE_PREFIXES = ("M2_aug", "M4_aug")


def channel_name(source_file, channel, n_channels):
    """The display name for one channel of one recording file."""
    channel = int(channel)
    if str(source_file).startswith(M2_STYLE_PREFIXES) and int(n_channels) == 16 and 0 <= channel < 16:
        return M2_STYLE_NAMES[channel]
    return f"CH{channel + 1}"
