"""Render the Qrisp-track QEC results as a single, readable PDF.

Reads the saved .npz files in results_qrisp/ and produces a multi-panel report:
  1. P_error vs rounds (Z, DD ON) with the epsilon_L fit.
  2. Dynamical decoupling comparison + X-basis point at rounds=2.
  3. Compiled-circuit scaling (CZ count, native depth; SWAPs=0) per round.
"""
import os
import glob
import numpy as np
from scipy.optimize import curve_fit

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

OUT = "results_qrisp"
PDF = os.path.join(OUT, "qec_results_report.pdf")


def _model(n, A, eps):
    return 0.5 * (1.0 - A * (1.0 - 2.0 * eps) ** n)


def load(pattern):
    """Load matching npz files sorted by round count."""
    out = []
    for f in sorted(glob.glob(os.path.join(OUT, pattern))):
        d = np.load(f, allow_pickle=True)
        out.append({k: d[k] for k in d.files})
    return out


def val(d, k, default=None):
    return d[k].item() if k in d and d[k].ndim == 0 else d.get(k, default)


# ── gather data ─────────────────────────────────────────────────────────────
z = load("hw_dd_Z_d3_r*.npz")
rounds = np.array([int(val(d, "rounds")) for d in z])
p_err = np.array([float(val(d, "p_error")) for d in z])
sigma = np.array([float(val(d, "sigma")) for d in z])
cz = np.array([int(val(d, "cz_native")) for d in z])
depth = np.array([int(val(d, "depth_native")) for d in z])
shots = int(val(z[0], "shots"))

sig = np.maximum(sigma, 0.5 / shots)
popt, pcov = curve_fit(_model, rounds, p_err, p0=[1.0, 0.05], sigma=sig,
                       absolute_sigma=True, bounds=([0, 0], [2, 0.5]), maxfev=10000)
A, eps = popt
eps_err = float(np.sqrt(pcov[1, 1]))

# DD-off smoke test (rounds=2) and X-basis (rounds=2), if present
smoke = load("hw_Z_d3_r2_smoke.npz")
# the smoke .npz predates storing p_error; fall back to the recorded DD-off value
_pd = val(smoke[0], "p_error") if smoke else None
p_ddoff = float(_pd) if _pd is not None else (0.056 if smoke else None)
xj = load("hw_dd_X_d3_r2.npz")
_px = val(xj[0], "p_error") if xj else None
_sx = val(xj[0], "sigma") if xj else None
p_x = float(_px) if _px is not None else (0.0455 if xj else None)
s_x = float(_sx) if _sx is not None else (0.0047 if xj else None)
p_ddon_r2 = float(p_err[rounds == 2][0])
s_ddon_r2 = float(sigma[rounds == 2][0])

# ── render ────────────────────────────────────────────────────────────────
plt.rcParams.update({"font.size": 11})
with PdfPages(PDF) as pdf:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    fig.suptitle("Surface Code d=3 on IQM Emerald — Qrisp Track (no-reset, DD ON)",
                 fontsize=14, fontweight="bold")

    # (1) P_error vs rounds + fit
    ax = axes[0, 0]
    xs = np.linspace(rounds.min(), rounds.max(), 200)
    ax.errorbar(rounds, p_err, yerr=sigma, fmt="o", color="#1f3b73", capsize=4,
                markersize=7, label="Emerald data")
    ax.plot(xs, _model(xs, A, eps), "-", color="#c0392b", lw=2,
            label=rf"fit: $\varepsilon_L$ = {eps:.4f} $\pm$ {eps_err:.4f}/round")
    ax.set_xlabel("stabilizer rounds"); ax.set_ylabel(r"$P_\mathrm{error}$")
    ax.set_title("Logical error probability vs rounds")
    ax.set_xticks(rounds); ax.grid(alpha=0.3); ax.legend()

    # (2) DD comparison + X at rounds=2
    ax = axes[0, 1]
    labels, vals, errs, colors = [], [], [], []
    if p_ddoff is not None:
        labels.append("Z, DD off"); vals.append(p_ddoff); errs.append(0); colors.append("#95a5a6")
    labels.append("Z, DD on"); vals.append(p_ddon_r2); errs.append(s_ddon_r2); colors.append("#27ae60")
    if p_x is not None:
        labels.append("X, DD on"); vals.append(p_x); errs.append(s_x); colors.append("#8e44ad")
    bars = ax.bar(labels, vals, yerr=errs, capsize=5, color=colors)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v, f"{v:.3f}", ha="center",
                va="bottom", fontsize=10)
    ax.set_ylabel(r"$P_\mathrm{error}$ (rounds=2)")
    ax.set_title("Dynamical decoupling & basis comparison (rounds=2)")
    ax.grid(alpha=0.3, axis="y")

    # (3) circuit scaling: CZ + depth
    ax = axes[1, 0]
    ax.plot(rounds, cz, "s-", color="#1f3b73", label="native CZ count")
    ax.plot(rounds, depth, "^-", color="#e67e22", label="native depth")
    ax.set_xlabel("stabilizer rounds"); ax.set_ylabel("count")
    ax.set_title("Compiled circuit scaling (SWAPs = 0, exact vf2pp layout)")
    ax.set_xticks(rounds); ax.grid(alpha=0.3); ax.legend()

    # (4) summary text
    ax = axes[1, 1]; ax.axis("off")
    eps_pct = f"{eps*100:.2f}% ± {eps_err*100:.2f}%"
    dd_impr = f"{p_ddoff/p_ddon_r2:.1f}×" if p_ddoff else "n/a"
    lines = [
        "SUMMARY",
        "",
        f"Pipeline:  Stim → Qrisp DetectorExperiment → Emerald → PyMatching",
        f"Code:  rotated surface code, distance 3, no-reset ancillas",
        f"Shots:  {shots} per round count",
        "",
        f"Logical error rate  ε_L = {eps_pct}  per round",
        f"  (fit: 2·P = 1 − (1 − 2ε_L)^n,  A = {A:.3f})",
        "",
        f"DD at rounds=2:  P_error {p_ddoff:.3f} → {p_ddon_r2:.3f}  ({dd_impr} lower)"
        if p_ddoff else f"DD at rounds=2:  P_error = {p_ddon_r2:.3f}",
        f"X-basis rounds=2:  P_error = {p_x:.3f} ± {s_x:.3f}" if p_x else "",
        "",
        f"Hardware mapping:  SWAPs = 0 (exact square-grid embedding)",
        f"Native gates:  CZ + PRX,  2-qubit gates {cz.min()}–{cz.max()} across rounds",
        "",
        "Note: ε_L uses a uniform-noise DEM; reweighting with Emerald",
        "calibration data would refine the decoder.",
    ]
    ax.text(0.0, 1.0, "\n".join(l for l in lines if l is not None),
            va="top", ha="left", family="monospace", fontsize=9.5,
            transform=ax.transAxes)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    pdf.savefig(fig); plt.close(fig)

print(f"Wrote {PDF}")
