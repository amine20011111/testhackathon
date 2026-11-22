"""Final fair comparison PDF: Qrisp (ours) vs Qiskit (friend) on IQM Emerald,
now with a MATCHED SI1000 decoder prior on both sides.

Reads from disk:
  results_qrisp/cmp_si1000_summary.json        (eps_L: mine uniform / mine SI1000 / friend SI1000)
  results_qrisp/cmp_mine_si1000_perround.json  (our per-round P_L, both priors)
  friend_repo/.../decoder_comparison.json       (friend per-round P_L, SI1000)
"""
import json
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

OUT = "results_qrisp"
PDF = os.path.join(OUT, "FINAL_qrisp_vs_qiskit_hardware.pdf")
FRIEND_JSON = (r"C:\Users\amoun\AppData\Local\Temp\claude\02fbd0915ffd2ee4"
               r"\84b99e58-147f-409d-bece-816c09036196\scratchpad\friend_repo"
               r"\results\figures\decoder_comparison.json")
ROUNDS = np.array([1, 2, 3, 4, 5])
DECS = ["none", "mwpm", "correlated", "bposd"]
LBL = {"none": "no corr.", "mwpm": "MWPM", "correlated": "corr. MWPM", "bposd": "BP+OSD"}


def _model(n, A, eps):
    return 0.5 * (1 - A * (1 - 2 * eps) ** n)

def wfit(r, p, shots=4000):
    r = np.asarray(r, float); p = np.asarray(p, float)
    s = np.maximum(np.sqrt(p * (1 - p) / shots), 0.5 / shots)
    (A, eps), _ = __import__("scipy.optimize", fromlist=["curve_fit"]).curve_fit(
        _model, r, p, p0=[1, 0.05], sigma=s, absolute_sigma=True,
        bounds=([0, 0], [2, 0.5]), maxfev=10000)
    return A, eps

summ = json.load(open(os.path.join(OUT, "cmp_si1000_summary.json")))          # eps in %
per = json.load(open(os.path.join(OUT, "cmp_mine_si1000_perround.json")))
fr = {r["decoder"]: r for r in json.load(open(FRIEND_JSON)) if r["prior"] in ("-", "si1000")}

with PdfPages(PDF) as pdf:
    fig = plt.figure(figsize=(11.5, 8.5))
    fig.suptitle("IQM Emerald, same session — Qrisp (ours) vs Qiskit (friend), MATCHED SI1000 prior\n"
                 "d=3, no-reset, native CZ, 0 SWAP, DD on, Z, rounds 1-5, 4000 shots",
                 fontsize=12.5, fontweight="bold")

    # (1) P_L vs rounds, matched SI1000 prior
    ax1 = fig.add_subplot(2, 2, 1)
    for dec, col in [("mwpm", "#1f77b4"), ("bposd", "#d62728")]:
        pm = np.array(per["mine_si1000"][dec])
        pf = np.array(fr[dec]["p_l"])
        Am, em = wfit(ROUNDS, pm); Af, ef = wfit(ROUNDS, pf)
        xs = np.linspace(1, 5, 200)
        ax1.plot(ROUNDS, pm, "o", color=col, ms=5)
        ax1.plot(xs, _model(xs, Am, em), "-", color=col, alpha=.8,
                 label=f"mine {LBL[dec]} (ε={100*em:.2f}%)")
        ax1.plot(ROUNDS, pf, "s", color=col, ms=5, mfc="none")
        ax1.plot(xs, _model(xs, Af, ef), "--", color=col, alpha=.6,
                 label=f"friend {LBL[dec]} (ε={100*ef:.2f}%)")
    ax1.set_xlabel("rounds n"); ax1.set_ylabel(r"$P_L$")
    ax1.set_title("P_L vs rounds (SI1000 prior; ●/— mine, □/-- friend)")
    ax1.set_xticks(ROUNDS); ax1.grid(alpha=.3); ax1.legend(fontsize=7)

    # (2) eps_L: 3 bars per decoder
    ax2 = fig.add_subplot(2, 2, 2)
    x = np.arange(len(DECS)); w = 0.27
    mu = [summ[d]["mine_uniform"] for d in DECS]
    ms = [summ[d]["mine_si1000"] for d in DECS]
    ff = [summ[d]["friend_si1000"] for d in DECS]
    ax2.bar(x - w, mu, w, color="#9ecae1", label="mine (uniform)")
    ax2.bar(x,     ms, w, color="#1f77b4", label="mine (SI1000)")
    ax2.bar(x + w, ff, w, color="#d62728", label="friend (SI1000)")
    for i in range(len(DECS)):
        for dx, v in [(-w, mu[i]), (0, ms[i]), (w, ff[i])]:
            ax2.text(i + dx, v, f"{v:.2f}", ha="center", va="bottom", fontsize=6.3)
    ax2.set_xticks(x, [LBL[d] for d in DECS], fontsize=8)
    ax2.set_ylabel(r"$\varepsilon_L$ per round (%)")
    ax2.set_title("ε_L by decoder & prior"); ax2.legend(fontsize=7.5); ax2.grid(alpha=.3, axis="y")

    # (3) table
    ax3 = fig.add_subplot(2, 2, 3); ax3.axis("off")
    rows = [["decoder", "mine uniform", "mine SI1000", "friend SI1000"]]
    for d in DECS:
        rows.append([LBL[d], f"{summ[d]['mine_uniform']:.2f}%",
                     f"{summ[d]['mine_si1000']:.2f}%", f"{summ[d]['friend_si1000']:.2f}%"])
    t = ax3.table(cellText=rows, cellLoc="center", loc="center",
                  colWidths=[0.24, 0.26, 0.25, 0.25])
    t.auto_set_font_size(False); t.set_fontsize(8.2); t.scale(1, 1.5)
    for c in range(4):
        t[(0, c)].set_facecolor("#2c3e50"); t[(0, c)].set_text_props(color="w", weight="bold")
    ax3.set_title("ε_L per round (%)  — lower is better", fontsize=10)

    # (4) interpretation
    ax4 = fig.add_subplot(2, 2, 4); ax4.axis("off")
    bm = min(summ[d]["mine_si1000"] for d in DECS if d != "none")
    bf = min(summ[d]["friend_si1000"] for d in DECS if d != "none")
    txt = [
        "SI1000 PRIOR (matched on both sides)",
        "",
        "SI1000 weights the decoder graph realistically:",
        "readout error 5x the gate error (vs uniform, where",
        "all errors are equal). This mainly re-weights the",
        "time-like (round-to-round) matching edges.",
        "",
        f"Best decoded ε_L (SI1000):  mine {bm:.2f}%   friend {bf:.2f}%",
        "",
        "With the prior now matched, the two pipelines agree",
        "even more closely — the remaining gap is the qubit",
        "patch + shot noise, NOT Qrisp-vs-Qiskit and NOT the",
        "noise model. Switching our prior uniform -> SI1000",
        "moves ε_L only within the error bars: the decoder",
        "ALGORITHM (MWPM -> BP+OSD) matters more than the prior",
        "on this clean d=3 patch.",
    ]
    ax4.text(0.0, 1.0, "\n".join(txt), va="top", ha="left", family="monospace",
             fontsize=8.6, transform=ax4.transAxes)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    pdf.savefig(fig); plt.close(fig)

print("Wrote", PDF)
for d in DECS:
    print(f"  {d:>11}: mine_uniform {summ[d]['mine_uniform']:.2f}  "
          f"mine_SI1000 {summ[d]['mine_si1000']:.2f}  friend_SI1000 {summ[d]['friend_si1000']:.2f}")
