"""
preprocessing_surrogate.py
===========================
Surrogate generation block (ticket 43). A signal-to-signal adapter that
produces a null — a surrogate version of the input signal — reproducibly
from its recipe. See PRD "Surrogates": phase randomisation and block
shuffling offered as a choice parameter, with an explicit RNG seed among
the parameters so the recipe hash reproduces the surrogate exactly.

Phase randomisation (a Fourier surrogate) preserves the original's power
spectrum by construction: each positive-frequency bin is multiplied by a
unit-magnitude complex exponential, so magnitudes are unchanged and the
inverse FFT is a real signal with the same spectrum. Block shuffling
destroys temporal structure while keeping local amplitude statistics.

AAFT (w3-a fix round 1): Theiler et al. 1992's amplitude-adjusted Fourier
transform keeps the input's exact values (the output is a permutation of
them) and approximately its spectrum. It is the null for a measure that reads
the value distribution — multiscale entropy with a MAD-based r: against plain
phase randomisation (which makes the surrogate Gaussian) a non-Gaussian linear
process "beat" its surrogates 20 / 20 on its distribution alone. Moved here
from `Pipelines/drop_motifs/nulls1.py`, which imports it back unchanged.
"""

import numpy as np

from Adapters.base import AdapterSpec, AdapterResult, ParamSpec
from Adapters.registry import register
from Working.types import Signal


def _phase_randomise(x, rng):
    """Fourier surrogate: randomise the phases of the original spectrum,
    preserving its magnitudes (and therefore its power spectrum).

    `rfft`/`irfft` keep the signal real by construction; the DC bin and —
    for even-length signals — the Nyquist bin must stay real for the inverse
    transform to be real, so their phases are pinned to zero.
    """
    n = len(x)
    X = np.fft.rfft(x)
    angles = rng.uniform(0.0, 2.0 * np.pi, size=X.shape)
    angles[0] = 0.0            # DC must remain real
    if n % 2 == 0:
        angles[-1] = 0.0       # Nyquist must remain real
    X_rand = X * np.exp(1j * angles)
    return np.fft.irfft(X_rand, n=n)


def aaft_surrogate(x, rng):
    """Amplitude-adjusted Fourier transform surrogate (Theiler 1992).

    Three steps, and the middle one is this module's:

      1. rank-map `x` onto Gaussian deviates, so the phase step operates
         on something whose spectrum is meaningful under a Gaussian
         assumption rather than on a heavily skewed marginal;
      2. `_phase_randomise` that Gaussian version;
      3. rank-map the result back onto `x`'s own sorted values.

    Step 3 is what makes this AAFT rather than plain phase randomisation:
    these channels are strongly non-Gaussian (long one-sided excursions), and
    a surrogate that Gaussianised them would be nulling the marginal
    distribution instead of the phase structure. The output is a permutation
    of the input's exact sample values.

    The cost, stated because it is real: step 3 distorts the spectrum
    slightly, so AAFT preserves the periodogram approximately rather than
    exactly (IAAFT iterates to fix that; not offered).

    `rng` is a `numpy.random.Generator` or a `RandomState` (both have
    `standard_normal` and `uniform`). Moved verbatim from
    `Pipelines/drop_motifs/nulls1.py` (w3-a fix round 1): bit-identical there.
    """
    x = np.asarray(x, dtype=float).ravel()
    ranks = np.argsort(np.argsort(x))
    gaussian = np.sort(rng.standard_normal(len(x)))[ranks]
    randomised = _phase_randomise(gaussian, rng)
    return np.sort(x)[np.argsort(np.argsort(randomised))]


def _block_shuffle(x, rng, block_s, fs):
    """Shuffle the order of contiguous blocks of length `block_s` seconds.

    The trailing partial block (if any) is left in place so the output has
    exactly the same length as the input. A signal too short to contain two
    full blocks is returned unchanged.

    A block under two samples is refused (Q-Null-1). The old default of 1.0 s
    is ONE sample at 1 Hz: a sample shuffle, which destroys the spectrum and
    every shape and is therefore neither of the two nulls on offer. Block
    shuffle keeps any motif shorter than a block intact — it tests timing and
    order, not shape — so the block has to be longer than the motif under test,
    and only the caller knows that length: twice the longest motif is the
    default every caller in `Working/` supplies.
    """
    n = len(x)
    if not block_s or block_s <= 0:
        raise ValueError(
            "block_shuffle needs a block length (block_s): twice the longest motif under test. "
            "None was given, and there is no length that is right for every chain.")
    if block_s * fs < 2:
        raise ValueError(
            f"block_shuffle refuses block_s = {block_s:g} s at {fs:g} Hz: that is "
            f"{block_s * fs:g} samples, and a block under 2 samples is a sample shuffle — "
            f"neither a timing null nor a shape null. Use twice the longest motif under test.")
    block_len = max(1, int(round(block_s * fs)))
    n_blocks = n // block_len
    if n_blocks <= 1:
        return np.array(x, dtype=float, copy=True)
    perm = rng.permutation(n_blocks)
    blocks = x[: n_blocks * block_len].reshape(n_blocks, block_len)
    shuffled = blocks[perm].reshape(-1)
    remainder = x[n_blocks * block_len:]
    return np.concatenate([shuffled, remainder])


def _run(x, t, fs, method="phase_randomize", seed=0, block_s=0.0):
    rng = np.random.RandomState(seed)
    if method == "phase_randomize":
        x_surrogate = _phase_randomise(x, rng)
    elif method == "block_shuffle":
        x_surrogate = _block_shuffle(x, rng, block_s, fs)
    elif method == "aaft":
        x_surrogate = aaft_surrogate(x, rng)
    else:
        raise ValueError(
            f"Unknown surrogate method {method!r}; expected one of "
            f"('phase_randomize', 'block_shuffle', 'aaft')"
        )
    return AdapterResult(
        output_kind="signal",
        value=Signal(x=x_surrogate, fs=fs),
    )


SPEC = register(AdapterSpec(
    name="preprocessing.surrogate",
    display_name="Surrogate generation",
    stage="preprocessing",
    category="control",
    page_name="Surrogate generator",
    params=[
        ParamSpec(
            "method", str, "phase_randomize",
            "Surrogate method: phase randomisation preserves the power "
            "spectrum and scrambles every local shape (the null for a "
            "detection chain); block shuffling keeps any motif shorter than a "
            "block intact, so it tests timing and order, not shape; aaft "
            "(amplitude-adjusted) keeps the signal's exact values and about "
            "its spectrum — the null for a measure that reads the value "
            "distribution, such as multiscale entropy",
            choices=["phase_randomize", "block_shuffle", "aaft"],
        ),
        ParamSpec(
            "seed", int, 0,
            "Random seed — the recipe hash reproduces the surrogate exactly",
            min=0,
        ),
        ParamSpec(
            "block_s", float, 0.0,
            "Block length in seconds for block shuffling: twice the longest "
            "motif under test. 0 = not set, which block shuffling refuses, as "
            "it refuses any block under 2 samples", min=0.0,
        ),
    ],
    run=_run,
    input_kind="signal",
    output_kind="signal",
    description=(
        "Produces a surrogate (null) version of the signal for surrogate "
        "testing. Phase randomisation keeps the power spectrum but destroys "
        "temporal phase structure; block shuffling reorders contiguous "
        "blocks; AAFT keeps the exact values and about the spectrum. An explicit seed makes the surrogate reproducible from the "
        "recipe hash."
    ),
))
