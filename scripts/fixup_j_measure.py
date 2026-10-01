"""Read-only, in-memory measurements for fixup-J's grilling round. Writes nothing."""
import sys
import numpy as np
from numpy.fft import fft, ifft, fftfreq

sys.path.insert(0, ".")
from Working.Detection.analysis import dehshibi_detection_analysis as D
from Adapters.preprocessing_wavelet_transform import transform_span
from Adapters.detection_summation_threshold import spans_from_omega
from scipy.signal import find_peaks

x_all = np.load("DATA/derived/channels/M2_aug_concat_fs1/CH0.npy", mmap_mode="r")
H = 3600


def chunk_accounting(x, label):
    n = len(x)
    lo, hi = D.estimate_state_levels(x)
    mid = (lo + hi) / 2
    chunks = D.slice_signal(x)
    lens = np.array([b - a + 1 for a, b in chunks])
    covered = np.zeros(n, bool)
    analysed = np.zeros(n, bool)
    for (a, b), L in zip(chunks, lens):
        covered[a:b + 1] = True
        if L >= 120:
            analysed[a:b + 1] = True
    print(f"[{label}] n={n} low={lo:.5f} high={hi:.5f} mid={mid:.5f} range={np.ptp(x)*1e3:.2f} mV")
    print(f"   chunks={len(chunks)}  >=120: {(lens >= 120).sum()}  median len={np.median(lens):.0f}  max={lens.max()}")
    print(f"   never in any chunk: {100*(~covered).mean():.1f}%   in a too-short chunk: {100*(covered & ~analysed).mean():.1f}%"
          f"   analysed: {100*analysed.mean():.1f}%")
    return chunks


def omega_complex(chunk, fs=1.0):
    """Same scales and Eq. 3 as the repo, but the analytic (complex) transform's modulus."""
    N = len(chunk)
    w0 = D._morse_peak_frequency()
    f_lo, f_hi = max(1e-3, fs / N), 0.4 * fs
    scales = np.geomspace(w0 * fs / (2 * np.pi * f_hi), w0 * fs / (2 * np.pi * f_lo), 64)
    om = 2 * np.pi * fftfreq(N, d=1 / fs)
    F = fft(chunk)
    phi = np.zeros((64, N), complex)
    for k, s in enumerate(scales):
        psi = D.morse_wavelet_spectrum(np.where(om > 0, s * om / fs, 0.0))
        phi[k] = ifft(psi * F)
    return D.normalise_wavelet_coefficients(phi)


def funnel(x, label, slice_by_state):
    g, chunks, skipped = transform_span(x, 1.0, slice_by_state=slice_by_state)
    om = g.sum(axis=0)
    spikes, pseudo, info = spans_from_omega(x, om, slice_by_state=slice_by_state)
    mono = D.detect_spikes(x, fs=1.0) if slice_by_state else None
    R = np.vstack([r for r in info["R"] if r.shape[0]]) if any(r.shape[0] for r in info["R"]) else np.empty((0, 3))
    inverted = int((R[:, 0] >= R[:, 1]).sum())
    B = info["B"]
    short_B = sum(1 for a, b in B if b - a <= 30)
    dup = len(spikes) - len(set(spikes))
    print(f"[{label}] slice_by_state={slice_by_state} nan cols={100*np.isnan(om).mean():.1f}%  "
          f"B={len(B)} (<=30 samples: {short_B})  C={len(info['C'])} D={len(info['D'])}  "
          f"R={len(R)} (start>=end: {inverted})  F_s={len(spikes)} (dupes {dup})  F_p={len(pseudo)}")
    if mono is not None:
        same = (mono[0] == spikes) and (mono[1] == pseudo)
        print(f"   monolith: F_s={len(mono[0])} F_p={len(mono[1])}  identical to template: {same}")
    return spikes, pseudo, info


print("=== 1. chunk accounting, CH0 ===")
x4 = np.asarray(x_all[:4 * H], float)
chunk_accounting(x4, "0-4 h")
for h0 in (50, 200, 400, 600):
    chunk_accounting(np.asarray(x_all[h0 * H:(h0 + 4) * H], float), f"{h0}-{h0+4} h")
chunk_accounting(np.asarray(x_all[:18 * H], float), "0-18 h")

print("\n=== 2. template vs monolith; funnel ===")
funnel(x4, "0-4 h", True)
funnel(x4, "0-4 h", False)
for h0 in (50, 200, 400, 600):
    xs = np.asarray(x_all[h0 * H:(h0 + 4) * H], float)
    funnel(xs, f"{h0}-{h0+4} h", True)
    funnel(xs, f"{h0}-{h0+4} h", False)

print("\n=== 3. paper-scale 3000 s windows, no slicing ===")
for s0 in (0, 3000, 6000, 9000, 200 * H, 400 * H):
    xs = np.asarray(x_all[s0:s0 + 3000], float)
    sp, ps, info = funnel(xs, f"{s0}+3000", False)
    print("     spikes:", sp[:8], " pseudo:", ps[:6])

print("\n=== 4. real part vs modulus (one 3000 s window) ===")
for s0 in (0, 200 * H):
    xs = np.asarray(x_all[s0:s0 + 3000], float)
    phi, _ = D.compute_morse_wavelet_transform(xs)
    print(f"  [{s0}] phi imag max abs = {np.abs(phi.imag).max():.3g}  (0 => only the real part is kept)")
    g_r, om_r = D.normalise_wavelet_coefficients(phi)
    g_c, om_c = omega_complex(xs)
    for name, om in (("repo |Re|", om_r), ("modulus", om_c)):
        eps = 0.05 * np.ptp(om)
        nmax = len(find_peaks(om, prominence=eps)[0]); nmin = len(find_peaks(-om, prominence=eps)[0])
        allmax = len(find_peaks(om)[0])
        B = D.algorithm1_detect_candidate_regions(om)
        print(f"     {name:10s} Omega range {om.min():.0f}..{om.max():.0f}  raw local maxima {allmax}  "
              f"eps-extrema {nmax}+{nmin}  B={len(B)}  B>30: {sum(1 for a,b in B if b-a>30)}")
    print(f"     corr(Omega_repo, Omega_modulus) = {np.corrcoef(om_r, om_c)[0,1]:.3f}")
