"""Side-by-side comparison: our Qrisp track vs friend's Qiskit track.

Our data is read live from results_qrisp/hw_dd_Z_d3_r*.npz (this repo's runs).
The friend's numbers are their published RESULTS.md values, independently
reproduced from their saved raw shots through their own code (analyze.py /
decoder_comparison.py), so they are verified, not copied blindly.
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
PDF = os.path.join(OUT, "qrisp_vs_qiskit_comparison.pdf")


def _model(n, A, eps):
    return 0.5 * (1.0 - A * (1.0 - 2.0 * eps) ** n)


# ── OURS (Qrisp): read live from disk ───────────────────────────────────────
def load_ours():
    rounds, p = [], []
    for f in sorted(glob.glob(os.path.join(OUT, "hw_dd_Z_d3_r*.npz"))):
        d = np.load(f, allow_pickle=True)
        rounds.append(int(d["rounds"])); p.append(float(d["p_error"]))
    return np.array(rounds), np.array(p)

def wfit(r, p, shots):
    """Sigma-weighted fit, identical method to benchmark_qrisp.fit_epsilon_L."""
    s = np.maximum(np.sqrt(p * (1 - p) / shots), 0.5 / shots)
    (A, eps), _ = curve_fit(_model, r, p, p0=[1, 0.05], sigma=s,
                            absolute_sigma=True, bounds=([0, 0], [2, 0.5]),
                            maxfev=10000)
    return A, eps

r_ours, p_ours = load_ours()
shots_ours = 4000
s_ours = np.sqrt(p_ours * (1 - p_ours) / shots_ours)
A_o, eps_o = wfit(r_ours, p_ours, shots_ours)

# ── FRIEND (Qiskit): verified-reproduced per-round P_L, Emerald Z, DD on ─────
r_fr = np.array([1, 2, 3, 4, 5])
p_fr_corr = np.array([0.030, 0.052, 0.081, 0.106, 0.123])   # correlated MWPM
p_fr_none = np.array([0.110, 0.169, 0.211, 0.240, 0.296])   # no correction
s_fr = np.sqrt(p_fr_corr * (1 - p_fr_corr) / 4000)
A_f, eps_f = wfit(r_fr, p_fr_corr, 4000)

with PdfPages(PDF) as pdf:
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 5))
    fig.suptitle("Surface code d=3 on IQM Emerald — Qrisp (ours) vs Qiskit (friend)\n"
                 "no-reset, 0 SWAPs, native CZ, DD on, 4000 shots/round, Z-memory",
                 fontsize=12, fontweight="bold")

    xs = np.linspace(1, 5, 200)
    ax[0].errorbar(r_ours, p_ours, yerr=s_ours, fmt="o", color="#1f77b4", capsize=4,
                   ms=7, label=f"OURS (Qrisp, MWPM): ε_L={eps_o*100:.2f}%")
    ax[0].plot(xs, _model(xs, A_o, eps_o), "-", color="#1f77b4", alpha=.7)
    ax[0].errorbar(r_fr, p_fr_corr, yerr=s_fr, fmt="s", color="#d62728", capsize=4,
                   ms=7, label=f"FRIEND (Qiskit, corr-MWPM): ε_L={eps_f*100:.2f}%")
    ax[0].plot(xs, _model(xs, A_f, eps_f), "-", color="#d62728", alpha=.7)
    ax[0].plot(r_fr, p_fr_none, "^--", color="#7f7f7f", ms=6, alpha=.7,
               label="FRIEND, no correction (8.6%)")
    ax[0].set_xlabel("rounds n"); ax[0].set_ylabel(r"$P_L$")
    ax[0].set_title("Logical error probability vs rounds")
    ax[0].set_xticks(r_fr); ax[0].grid(alpha=.3); ax[0].legend(fontsize=8)

    # ε_L ladder (decoder comparison), both solutions
    ax[1].axis("off")
    rows = [
        ("", "OURS", "FRIEND"),
        ("Framework", "Qrisp", "Qiskit"),
        ("ε_L, no correction", "—", "8.59%"),
        ("ε_L, MWPM (uniform)", f"{eps_o*100:.2f}%", "2.95%"),
        ("ε_L, MWPM (SI1000)", "—", "3.01%"),
        ("ε_L, correlated MWPM", "—", "2.82%"),
        ("ε_L, BP+OSD (best)", "—", "2.65%"),
        ("decoders implemented", "MWPM", "6 (UF/MWPM/corr/BM/BPOSD)"),
        ("noise model / DEM", "uniform", "uniform+SI1000+calibrated+char."),
        ("SWAPs", "0", "0"),
        ("qubit selection", "transpiler/vf2pp", "VF2 scan, bad-qubit exclusion"),
        ("X-memory", "yes", "yes"),
        ("DD", "on", "on/off ablation"),
    ]
    tbl = ax[1].table(cellText=rows, cellLoc="left", loc="center",
                      colWidths=[0.42, 0.22, 0.36])
    tbl.auto_set_font_size(False); tbl.set_fontsize(8.2); tbl.scale(1, 1.45)
    for c in range(3):
        tbl[(0, c)].set_facecolor("#2c3e50"); tbl[(0, c)].set_text_props(color="w", weight="bold")
        tbl[(1, c)].set_text_props(weight="bold")
    ax[1].set_title("ε_L per round & feature comparison (Emerald Z, DD on)", fontsize=10)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    pdf.savefig(fig); plt.close(fig)

print(f"OURS  ε_L (MWPM, uniform)      = {eps_o*100:.2f}%")
print(f"FRIEND ε_L (corr-MWPM)         = {eps_f*100:.2f}%  (plain MWPM 3.01%, BP+OSD 2.65%)")
print(f"Wrote {PDF}")
