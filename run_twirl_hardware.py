"""Hardware twirling study on IQM Emerald (same session).

For each round count: a no-twirl run and a Pauli-twirled run (K randomized
instances pooled). Both DD on, Z-memory. Decoded with the SI1000 prior
(MWPM + BP+OSD) and fit for eps_L. Results go to results_qrisp/cmp_twirl_summary.json.
"""
import json
import os
import numpy as np
from scipy.optimize import curve_fit

from run_on_hardware import run_qrisp, decode_hardware_results
from surface_code import SI1000_NOISE

OUT = "results_qrisp"
os.makedirs(OUT, exist_ok=True)
ROUNDS = [1, 2, 3, 4, 5]
K = 5                 # twirl instances to pool
SHOTS_NT = 2000       # no-twirl shots/round
SHOTS_TW = 400        # per twirl instance (pool -> 2000)
DECODERS = ["mwpm", "bposd"]


def _model(n, A, eps):
    return 0.5 * (1 - A * (1 - 2 * eps) ** n)

def wfit(r, p, shots):
    r = np.asarray(r, float); p = np.asarray(p, float)
    s = np.maximum(np.sqrt(p * (1 - p) / shots), 0.5 / shots)
    (A, eps), cov = curve_fit(_model, r, p, p0=[1, 0.05], sigma=s,
                              absolute_sigma=True, bounds=([0, 0], [2, 0.5]), maxfev=10000)
    return eps, float(np.sqrt(cov[1, 1]))


pl = {"notwirl": {d: [] for d in DECODERS}, "twirl": {d: [] for d in DECODERS}}

for r in ROUNDS:
    # --- no twirl ---
    s0 = run_qrisp(distance=3, rounds=r, shots=SHOTS_NT, quantum_computer="emerald",
                   no_reset=True, basis="Z", noise=None, dd=True)
    np.savez_compressed(os.path.join(OUT, f"tw_notwirl_Z_r{r}.npz"),
                        det_events=s0["det_events"], obs_flips=s0["obs_flips"],
                        rounds=r, shots=SHOTS_NT)
    line = f"[r={r}] no-twirl saved"
    for d in DECODERS:
        p, _ = decode_hardware_results(s0, distance=3, rounds=r, basis="Z",
                                       noise=SI1000_NOISE, decoder=d)
        pl["notwirl"][d].append(p); line += f"  nt-{d}={p:.4f}"

    # --- twirl: K instances pooled ---
    dets, obs = [], []
    for seed in range(K):
        s = run_qrisp(distance=3, rounds=r, shots=SHOTS_TW, quantum_computer="emerald",
                      no_reset=True, basis="Z", noise=None, dd=True, twirl_seed=seed)
        dets.append(s["det_events"]); obs.append(s["obs_flips"])
    pooled = {"det_events": np.vstack(dets), "obs_flips": np.vstack(obs)}
    np.savez_compressed(os.path.join(OUT, f"tw_twirl_Z_r{r}.npz"),
                        det_events=pooled["det_events"], obs_flips=pooled["obs_flips"],
                        rounds=r, shots=K * SHOTS_TW, K=K)
    for d in DECODERS:
        p, _ = decode_hardware_results(pooled, distance=3, rounds=r, basis="Z",
                                       noise=SI1000_NOISE, decoder=d)
        pl["twirl"][d].append(p); line += f"  tw-{d}={p:.4f}"
    print(line, flush=True)

# --- fit + summary ---
summary = {}
print("\n=== eps_L (SI1000 prior) ===")
for d in DECODERS:
    e_nt, s_nt = wfit(ROUNDS, pl["notwirl"][d], SHOTS_NT)
    e_tw, s_tw = wfit(ROUNDS, pl["twirl"][d], K * SHOTS_TW)
    summary[d] = {"notwirl_eps": 100*e_nt, "notwirl_err": 100*s_nt,
                  "twirl_eps": 100*e_tw, "twirl_err": 100*s_tw,
                  "notwirl_pl": pl["notwirl"][d], "twirl_pl": pl["twirl"][d]}
    print(f"  {d:>6}: no-twirl {100*e_nt:.2f}±{100*s_nt:.2f}%   "
          f"twirl {100*e_tw:.2f}±{100*s_tw:.2f}%")
summary["rounds"] = ROUNDS
json.dump(summary, open(os.path.join(OUT, "cmp_twirl_summary.json"), "w"), indent=1, default=float)
print("saved results_qrisp/cmp_twirl_summary.json")
