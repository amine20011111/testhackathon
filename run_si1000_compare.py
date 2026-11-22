"""Re-decode our fresh Qrisp hardware shots with the SI1000 prior and redo the
full comparison against the Qiskit solution (also SI1000) — now the DEM prior
matches on both sides, removing the last confound.

No new QPU: we reuse results_qrisp/cmp_mine_Z_r*.npz (real Emerald shots).
"""
import json
import os
import numpy as np
from scipy.optimize import curve_fit

from run_on_hardware import decode_hardware_results
from surface_code import DEFAULT_NOISE, SI1000_NOISE

OUT = "results_qrisp"
ROUNDS = [1, 2, 3, 4, 5]
SHOTS = 4000
DECODERS = ["none", "mwpm", "correlated", "bposd"]
FRIEND_JSON = (r"C:\Users\amoun\AppData\Local\Temp\claude\02fbd0915ffd2ee4"
               r"\84b99e58-147f-409d-bece-816c09036196\scratchpad\friend_repo"
               r"\results\figures\decoder_comparison.json")


def _model(n, A, eps):
    return 0.5 * (1 - A * (1 - 2 * eps) ** n)


def wfit(r, p, shots):
    r = np.asarray(r, float); p = np.asarray(p, float)
    s = np.maximum(np.sqrt(p * (1 - p) / shots), 0.5 / shots)
    (A, eps), cov = curve_fit(_model, r, p, p0=[1, 0.05], sigma=s,
                              absolute_sigma=True, bounds=([0, 0], [2, 0.5]), maxfev=10000)
    return eps, float(np.sqrt(cov[1, 1]))


def decode_mine(prior):
    out = {d: [] for d in DECODERS}
    for r in ROUNDS:
        d = np.load(os.path.join(OUT, f"cmp_mine_Z_r{r}.npz"), allow_pickle=True)
        synd = {"det_events": d["det_events"], "obs_flips": d["obs_flips"]}
        for dec in DECODERS:
            p, _ = decode_hardware_results(synd, distance=3, rounds=r, no_reset=True,
                                           basis="Z", noise=prior, decoder=dec)
            out[dec].append(p)
    return out


# ── decode our shots with both priors ───────────────────────────────────────
mine_uniform = decode_mine(DEFAULT_NOISE)
mine_si1000 = decode_mine(SI1000_NOISE)

# ── friend's SI1000 numbers (verified-reproduced earlier) ───────────────────
fr = {r["decoder"]: r for r in json.load(open(FRIEND_JSON)) if r["prior"] in ("-", "si1000")}

print(f"{'decoder':>12} | {'mine uniform':>13} | {'mine SI1000':>12} | {'friend SI1000':>14}")
print("-" * 62)
summary = {}
for dec in DECODERS:
    eu, _ = wfit(ROUNDS, mine_uniform[dec], SHOTS)
    es, _ = wfit(ROUNDS, mine_si1000[dec], SHOTS)
    ff = 100 * fr[dec]["eps"]
    print(f"{dec:>12} | {100*eu:11.2f} % | {100*es:10.2f} % | {ff:12.2f} %")
    summary[dec] = {"mine_uniform": 100*eu, "mine_si1000": 100*es, "friend_si1000": ff}
json.dump(summary, open(os.path.join(OUT, "cmp_si1000_summary.json"), "w"), indent=1)
print("\nsaved results_qrisp/cmp_si1000_summary.json")

# ── store per-round P_L for the plotting script ─────────────────────────────
json.dump({"rounds": ROUNDS, "mine_si1000": mine_si1000, "mine_uniform": mine_uniform},
          open(os.path.join(OUT, "cmp_mine_si1000_perround.json"), "w"), indent=1)
