"""Scratch experiment: what does the pipeline say once the four divergences are removed?
In memory, read-only. Not repo code."""
import sys
import numpy as np
from numpy.fft import fft, ifft, fftfreq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

sys.path.insert(0, ".")
from Working.Detection.analysis import dehshibi_detection_analysis as D

OUT = sys.argv[1]
x_all = np.load("DATA/derived/channels/M2_aug_concat_fs1/CH0.npy", mmap_mode="r")


def omega_fixed(chunk, fs=1.0, pad=True, n_scales=64):
    N = len(chunk)
    xp = np.concatenate([chunk[::-1], chunk, chunk[::-1]]) if pad else chunk
    M = len(xp)
    w0 = D._morse_peak_frequency()
    f_lo, f_hi = max(1e-3, fs / N), 0.4 * fs
    scales = np.geomspace(w0 * fs / (2 * np.pi * f_hi), w0 * fs / (2 * np.pi * f_lo), n_scales)
    om = 2 * np.pi * fftfreq(M, d=1 / fs)
    F = fft(xp - xp.mean())
    phi = np.zeros((n_scales, N), complex)
    for k, s in enumerate(scales):
        psi = D.morse_wavelet_spectrum(np.where(om > 0, s * om / fs, 0.0))
        full = ifft(psi * F)
        phi[k] = full[N:2 * N] if pad else full
    g, osum = D.normalise_wavelet_coefficients(phi)
    return g, osum


def alg3_fixed(xi_M, n_p=60):
    mn, _ = find_peaks(-xi_M, distance=n_p)
    mx, _ = find_peaks(xi_M, distance=n_p)
    rows = []
    for i in mn:
        later = mx[mx > i]
        if len(later) == 0:
            break
        j = later[0]
        rows.append([i, j, xi_M[j] - xi_M[i]])
    R = np.array(rows, float).reshape(-1, 3)
    if len(R) > 1:
        rho = R[:, 2].mean() - R[:, 2].std()
        R = R[R[:, 2] >= rho]
    return R


def run(x, fixed):
    if fixed:
        g, om = omega_fixed(x)
    else:
        phi, _ = D.compute_morse_wavelet_transform(x)
        g, om = D.normalise_wavelet_coefficients(phi)
    B = D.algorithm1_detect_candidate_regions(om)
    C, Dd = D.algorithm2_exclude_pseudospike_regions(B, x)
    xm, xu, xl = D.compute_signal_envelope(x)
    R = alg3_fixed(xm) if fixed else D.algorithm3_detect_envelope_regions(xm, xu, xl)
    Fs, Fp = D.algorithm4_extract_spike_events(C, Dd, R)
    return dict(g=g, om=om, B=B, C=C, D=Dd, R=R, Fs=Fs, Fp=Fp)


def shade(ax, regs, color, y0, y1, alpha=0.35):
    for a, b in regs:
        a, b = sorted((int(a), int(b)))
        ax.axvspan(a, b, ymin=y0, ymax=y1, color=color, alpha=alpha, lw=0)


for s0 in (3000, 6000, 720000, 180000):
    x = np.asarray(x_all[s0:s0 + 3000], float)
    fig, axes = plt.subplots(4, 2, figsize=(18, 11), sharex=True)
    for col, fixed in enumerate((False, True)):
        r = run(x, fixed)
        t = np.arange(len(x))
        a0, a1, a2, a3 = axes[:, col]
        a0.imshow(r["g"], aspect="auto", origin="lower", extent=[0, len(x), 0, 64], cmap="viridis")
        a0.set_title(("repo as-is" if not fixed else "modulus + reflect padding + index pairing")
                     + f" | B={len(r['B'])} C={len(r['C'])} D={len(r['D'])} R={len(r['R'])} "
                       f"Fs={len(r['Fs'])} Fp={len(r['Fp'])}")
        a1.plot(t, r["om"], "k", lw=0.8); a1.set_ylabel("Omega")
        for a, b in r["B"]:
            a1.axvline(a, color="g", lw=0.6); a1.axvline(b, color="m", lw=0.6)
        a2.plot(t, x * 1e3, "k", lw=0.7); a2.set_ylabel("mV  (C green / D grey / R orange)")
        shade(a2, r["C"], "green", 0.5, 1.0); shade(a2, r["D"], "grey", 0.5, 1.0)
        shade(a2, [(a, b) for a, b, _ in r["R"]], "orange", 0.0, 0.5)
        a3.plot(t, x * 1e3, "k", lw=0.7); a3.set_ylabel("mV  (F_s red / F_p blue)")
        for k, (a, b) in enumerate(r["Fs"]):
            lo = 0.5 + 0.5 * k / max(1, len(r["Fs"]))
            a3.axvspan(a, b, ymin=lo, ymax=lo + 0.5 / max(1, len(r["Fs"])), color="red", alpha=0.6, lw=0)
        shade(a3, r["Fp"], "blue", 0.0, 0.45)
        print(s0, "fixed" if fixed else "as-is", "B", r["B"], "\n    Fs", r["Fs"], "\n    Fp", r["Fp"],
              "\n    R inverted:", int((r["R"][:, 0] >= r["R"][:, 1]).sum()), "of", len(r["R"]))
    fig.tight_layout()
    fig.savefig(f"{OUT}/trial_{s0}.png", dpi=70)
    plt.close(fig)
