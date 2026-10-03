"""Fixup W Part 1 -- synthetic: what Explore's computation vs the Library's
computation return for (a) the same shape at a +5-sample offset on two channels
and (b) the same shape an hour (3600 samples at fs=1) apart. Read-only; no DB."""
import sys
sys.path.insert(0, r"C:\Users\mmebr\Documents\CNN")
import numpy as np
from Working.cross_channel import classify_waveforms

FS = 1.0
N = 20000
rng = np.random.default_rng(0)


def shape(L=60):
    t = np.arange(L) - L / 2
    return -t / 8 * np.exp(-(t / 8) ** 2)  # biphasic, ~60 samples


def channel(event_starts, noise):
    x = rng.normal(0, noise, N)
    s = shape()
    for e in event_starts:
        x[e:e + s.size] += s
    return x


def explore(x_ref, y, s0, s1, max_samples=200_000):
    # webui/server/explore_routes.py get_cross_channel: same absolute window, strided
    ref = np.asarray(x_ref[s0:s1], float)
    stride = max(1, int(np.ceil(len(ref) / max_samples)))
    ref = ref[::stride]
    yy = np.asarray(y[s0:s1], float)[::stride]
    n = min(len(ref), len(yy))
    return classify_waveforms(ref[:n], yy[:n])


def library(x_a, span_a, x_b, span_b):
    # Working/library/matching.py classify_cross_channel_edges: each member's own span
    return classify_waveforms(np.array(x_a[span_a[0]:span_a[1]]), np.array(x_b[span_b[0]:span_b[1]]))


def fmt(t):
    return f"lag={t[0]:+d}  r={t[1]:+.4f}  bin={t[2]}"


for noise in (0.0, 0.02, 0.1):
    print(f"\n=== noise sd {noise} (shape peak ~0.43) ===")
    E = 5000
    # (a) +5 sample offset
    A = channel([E], noise); B = channel([E + 5], noise)
    print("(a) +5-sample offset")
    print("  Explore  window [E-100,E+200) both ch  :", fmt(explore(A, B, E - 100, E + 200)))
    print("  Explore  window [E-1000,E+1000)         :", fmt(explore(A, B, E - 1000, E + 1000)))
    print("  Library  members cut at each event      :", fmt(library(A, (E - 10, E + 70), B, (E + 5 - 10, E + 5 + 70))))
    print("  Library  members same abs span          :", fmt(library(A, (E - 10, E + 70), B, (E - 10, E + 70))))
    print("  Library  B cut 3 samples late vs event  :", fmt(library(A, (E - 10, E + 70), B, (E + 5 - 7, E + 5 + 73))))
    # (b) one hour apart (3600 samples at fs=1)
    H = int(3600 * FS)
    A = channel([E], noise); B = channel([E + H], noise)
    print("(b) +1 h (3600 samples)")
    print("  Explore  window [E-100,E+200) both ch  :", fmt(explore(A, B, E - 100, E + 200)))
    print("  Explore  window [E-100,E+H+200) both ch:", fmt(explore(A, B, E - 100, E + H + 200)))
    print("  Library  members cut at each event      :", fmt(library(A, (E - 10, E + 70), B, (E + H - 10, E + H + 70))))
    print("  Library  B cut 3 samples late vs event  :", fmt(library(A, (E - 10, E + 70), B, (E + H - 7, E + H + 73))))
    print("  Library  B member 120 samples long      :", fmt(library(A, (E - 10, E + 70), B, (E + H - 30, E + H + 90))))
