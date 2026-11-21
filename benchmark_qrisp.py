"""
benchmark_qrisp.py

Multi-round memory sweep + logical-error-rate fit for the Qrisp track.

For each round count we run the no-reset surface-code memory experiment
(locally or on IQM Emerald), save the raw detection events to disk, decode
with PyMatching, and fit the per-round logical error rate epsilon_L from

        2 * P_error(n) = 1 - (1 - 2 * epsilon_L) ** n_rounds

Boundary handling: the first/last rounds carry extra SPAM / time-boundary
detectors, which show up as a round-independent offset on the logical error
probability. We absorb that into a free amplitude A in the fit model
        P_error(n) = 0.5 * (1 - A * (1 - 2 eps)^n)
so epsilon_L (the decay slope) is not biased by the rounds=1 boundary point.

NOTE: basis="X" needs RX/MX support in stim_to_qrisp.py (not yet implemented),
so this script guards X and reports the gap instead of crashing the sweep.
"""

import os
import numpy as np
from scipy.optimize import curve_fit

import matplotlib
matplotlib.use("Agg")            # headless: write PNGs, never open a window
import matplotlib.pyplot as plt

from run_on_hardware import run_qrisp, decode_hardware_results
from surface_code import DEFAULT_NOISE

RESULTS_DIR = "results_qrisp"


def _model(n, A, eps):
    """P_error as a function of rounds; A absorbs boundary/SPAM offset."""
    return 0.5 * (1.0 - A * (1.0 - 2.0 * eps) ** n)


def run_sweep(
    rounds_list=(1, 2, 3, 4, 5),
    basis: str = "Z",
    distance: int = 3,
    shots: int = 5000,
    quantum_computer=None,        # None -> local simulation (free)
    no_reset: bool = True,
    noise: dict = None,           # None on hardware; a model for local sim / DEM
    token: str = None,
    dd: bool = False,             # dynamical decoupling (hardware only)
    prefix: str = "raw",          # output filename prefix
    out_dir: str = RESULTS_DIR,
):
    """Run the memory experiment for each round count and save raw data to .npz."""
    os.makedirs(out_dir, exist_ok=True)
    rounds, p_err, sig = [], [], []
    dem_noise = noise if noise is not None else DEFAULT_NOISE

    for r in rounds_list:
        synd = run_qrisp(distance=distance, rounds=r, shots=shots, token=token,
                         quantum_computer=quantum_computer, no_reset=no_reset,
                         basis=basis, noise=noise, dd=dd)
        st = synd.get("stats") or {}
        p, s = decode_hardware_results(synd, distance=distance, rounds=r,
                                       no_reset=no_reset, basis=basis,
                                       noise=dem_noise)

        # Persist raw results FIRST, before any further processing, so QPU
        # shots are never lost if we later re-tune the decoder.
        fname = os.path.join(out_dir, f"{prefix}_{basis}_d{distance}_r{r}.npz")
        np.savez_compressed(
            fname,
            det_events=synd["det_events"],
            obs_flips=synd["obs_flips"],
            distance=distance, rounds=r, basis=basis, shots=shots,
            no_reset=no_reset, p_error=p, sigma=s, dd=dd,
            backend=str(quantum_computer),
            cz_native=st.get("cz_native"), swaps=st.get("swaps"),
            depth_native=st.get("depth_native"),
            exact_embedding=st.get("exact_embedding"),
        )
        print(f"[{basis}] rounds={r}: P_error={p:.4f} +/- {s:.4f}  -> {fname}")
        rounds.append(r); p_err.append(p); sig.append(s)

    return np.array(rounds), np.array(p_err, float), np.array(sig, float)


def fit_epsilon_L(rounds, p_error, sigma, shots):
    """Fit epsilon_L (+/- 1 sigma) to the P_error vs rounds data."""
    # Floor the per-point uncertainty at half a shot so a P_error=0 point
    # does not get infinite weight in the chi-square.
    sig = np.maximum(sigma, 0.5 / shots)
    popt, pcov = curve_fit(
        _model, rounds, p_error, p0=[1.0, 0.05],
        sigma=sig, absolute_sigma=True,
        bounds=([0.0, 0.0], [2.0, 0.5]), maxfev=10000,
    )
    A, eps = popt
    eps_err = float(np.sqrt(pcov[1, 1]))
    return float(eps), eps_err, float(A)


def plot_sweep(rounds, p_error, sigma, eps, eps_err, A, basis,
               distance=3, prefix="", out_dir=RESULTS_DIR):
    xs = np.linspace(min(rounds), max(rounds), 200)
    plt.figure(figsize=(6, 4))
    plt.errorbar(rounds, p_error, yerr=sigma, fmt="o", capsize=3, label="data")
    plt.plot(xs, _model(xs, A, eps), "-",
             label=rf"fit: $\varepsilon_L$={eps:.4f}$\pm${eps_err:.4f}")
    plt.xlabel("rounds"); plt.ylabel(r"$P_\mathrm{error}$")
    plt.title(f"{basis}-memory, d={distance}")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    tag = f"{prefix}_" if prefix else ""
    path = os.path.join(out_dir, f"{tag}P_error_vs_rounds_{basis}.png")
    plt.savefig(path, dpi=130); plt.close()
    return path


def benchmark(basis="Z", rounds_list=(1, 2, 3, 4, 5), shots=5000,
              quantum_computer=None, prefix="raw", **kw):
    """Full pipeline for one basis: sweep -> save -> fit -> plot."""
    r, p, s = run_sweep(rounds_list, basis=basis, shots=shots,
                        quantum_computer=quantum_computer, prefix=prefix, **kw)
    eps, eps_err, A = fit_epsilon_L(r, p, s, shots)
    path = plot_sweep(r, p, s, eps, eps_err, A, basis, prefix=prefix)
    print(f"== {basis}-memory: epsilon_L = {eps:.5f} +/- {eps_err:.5f} "
          f"(A={A:.3f})  plot={path}")
    print(f"   per-round P_error: " +
          "  ".join(f"r{ri}={pi:.4f}+/-{si:.4f}" for ri, pi, si in zip(r, p, s)))
    return eps, eps_err


if __name__ == "__main__":
    # Local validation sweep (no IQM Resonance needed).
    for basis in ("Z", "X"):
        try:
            benchmark(basis=basis, rounds_list=[1, 2, 3, 4, 5],
                      shots=5000, quantum_computer=None, noise=DEFAULT_NOISE)
        except NotImplementedError as e:
            print(f"[{basis}] SKIPPED: converter does not support gate {e} "
                  f"(RX/MX). Extend stim_to_qrisp.py to enable X-memory.")
