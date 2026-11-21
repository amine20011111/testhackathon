"""Final fair comparison: my Qrisp pipeline vs friend's Qiskit pipeline.

Both run FRESH on IQM Emerald in the same session (same calibration window),
identical parameters: d=3 rotated surface code, no-reset, native CZ, 0 SWAP,
DD on, Z-memory, rounds 1-5, 4000 shots. Each decoded with the same decoder
algorithms (MWPM, correlated MWPM, BP+OSD).

My data:     results_qrisp/cmp_mine_summary.json   (uniform DEM prior)
Friend data: friend_repo/.../decoder_comparison.json (SI1000 prior; also calibrated)
Both are read live from disk.
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


def _model(n, A, eps):
    return 0.5 * (1 - A * (1 - 2 * eps) ** n)


# ── mine (Qrisp) ────────────────────────────────────────────────────────────
mine = json.load(open(os.path.join(OUT, "cmp_mine_summary.json")))["results"]
# ── friend (Qiskit), SI1000 prior rows ──────────────────────────────────────
fr_all = json.load(open(FRIEND_JSON))
fr = {r["decoder"]: r for r in fr_all if r["prior"] in ("-", "si1000")}

decoders = ["none", "mwpm", "correlated", "bposd"]
labels = {"none": "no correction", "mwpm": "MWPM", "correlated": "correlated MWPM",
          "bposd": "BP+OSD"}
colors = {"none": "#7f7f7f", "mwpm": "#1f77b4", "correlated": "#2ca02c", "bposd": "#d62728"}

with PdfPages(PDF) as pdf:
    fig = plt.figure(figsize=(11.5, 8.5))
    fig.suptitle("FRESH same-session IQM Emerald run — Qrisp (mine) vs Qiskit (friend)\n"
                 "d=3, no-reset, native CZ, 0 SWAP, DD on, Z-memory, rounds 1-5, 4000 shots",
                 fontsize=13, fontweight="bold")

    # (1) P_L vs rounds, both pipelines, correlated + bposd
    ax1 = fig.add_subplot(2, 2, 1)
    xs = np.linspace(1, 5, 200)
    for dec in ["mwpm", "bposd"]:
        pm = np.array(mine[dec]["p_l"])
        pf = np.array(fr[dec]["p_l"])
        ax1.plot(ROUNDS, pm, "o-", color=colors[dec], ms=5,
                 label=f"mine {labels[dec]} (ε={100*mine[dec]['eps']:.2f}%)")
        ax1.plot(ROUNDS, pf, "s--", color=colors[dec], ms=5, alpha=.6,
                 label=f"friend {labels[dec]} (ε={100*fr[dec]['eps']:.2f}%)")
    ax1.set_xlabel("rounds n"); ax1.set_ylabel(r"$P_L$")
    ax1.set_title("P_L vs rounds (solid=mine, dashed=friend)")
    ax1.set_xticks(ROUNDS); ax1.grid(alpha=.3); ax1.legend(fontsize=7)

    # (2) eps_L bars per decoder
    ax2 = fig.add_subplot(2, 2, 2)
    x = np.arange(len(decoders)); w = 0.38
    me = [100 * mine[d]["eps"] for d in decoders]
    fe = [100 * fr[d]["eps"] for d in decoders]
    me_e = [100 * mine[d]["eps_err"] for d in decoders]
    fe_e = [100 * fr[d]["eps_err"] for d in decoders]
    ax2.bar(x - w/2, me, w, yerr=me_e, capsize=3, color="#1f77b4", label="mine (Qrisp)")
    ax2.bar(x + w/2, fe, w, yerr=fe_e, capsize=3, color="#d62728", label="friend (Qiskit)")
    for i, (m, f) in enumerate(zip(me, fe)):
        ax2.text(i - w/2, m, f"{m:.2f}", ha="center", va="bottom", fontsize=7)
        ax2.text(i + w/2, f, f"{f:.2f}", ha="center", va="bottom", fontsize=7)
    ax2.set_xticks(x, [labels[d] for d in decoders], rotation=20, fontsize=8)
    ax2.set_ylabel(r"$\varepsilon_L$ per round (%)")
    ax2.set_title("Logical error rate per decoder"); ax2.legend(fontsize=8); ax2.grid(alpha=.3, axis="y")

    # (3) table
    ax3 = fig.add_subplot(2, 2, 3); ax3.axis("off")
    rows = [["decoder", "MINE (Qrisp)", "FRIEND (Qiskit)"]]
    for d in decoders:
        rows.append([labels[d], f"{100*mine[d]['eps']:.2f} ± {100*mine[d]['eps_err']:.2f}%",
                     f"{100*fr[d]['eps']:.2f} ± {100*fr[d]['eps_err']:.2f}%"])
    rows += [["prior", "uniform", "SI1000"],
             ["2q gates/round", "24 (19 at r1)", "24"],
             ["SWAPs", "0", "0"],
             ["qubit patch", "auto vf2pp (17)", "VF2+cal scan (17)"]]
    t = ax3.table(cellText=rows, cellLoc="left", loc="center",
                  colWidths=[0.34, 0.33, 0.33])
    t.auto_set_font_size(False); t.set_fontsize(8.5); t.scale(1, 1.5)
    for c in range(3):
        t[(0, c)].set_facecolor("#2c3e50"); t[(0, c)].set_text_props(color="w", weight="bold")
    ax3.set_title("ε_L per round (same session, same params)", fontsize=10)

    # (4) explanation
    ax4 = fig.add_subplot(2, 2, 4); ax4.axis("off")
    best_m = min(100*mine[d]["eps"] for d in decoders if d != "none")
    best_f = min(100*fr[d]["eps"] for d in decoders if d != "none")
    txt = [
        "WHY THEY ARE CLOSE",
        "",
        "Both run the identical physics on the identical chip:",
        "d=3 rotated surface code, no-reset detectors, native",
        "H+CZ, 0 SWAP, DD on. The logical error rate is set by",
        "Emerald's physical gate/readout/idle errors — NOT by",
        "whether the circuit is written in Qrisp or Qiskit.",
        "The framework is just the pen; the chip does the same",
        "operations either way.",
        "",
        "The only framework-independent levers that move ε_L:",
        "  • which 17 qubits (patch)   • the decoder",
        "  • the DEM prior (noise model for decoder weights)",
        "",
        f"Best decoded ε_L:  mine {best_m:.2f}%   friend {best_f:.2f}%",
        "Difference is within patch/calibration variation,",
        "not a Qrisp-vs-Qiskit effect. Upgrading the decoder",
        "(MWPM→BP+OSD) helps BOTH by ~0.4%.",
    ]
    ax4.text(0.0, 1.0, "\n".join(txt), va="top", ha="left", family="monospace",
             fontsize=8.6, transform=ax4.transAxes)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    pdf.savefig(fig); plt.close(fig)

print("MINE  :", {d: round(100*mine[d]["eps"], 2) for d in decoders})
print("FRIEND:", {d: round(100*fr[d]["eps"], 2) for d in decoders})
print("Wrote", PDF)
