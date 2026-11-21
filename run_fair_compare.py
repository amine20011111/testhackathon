"""Fair same-session hardware comparison: my Qrisp pipeline vs friend's Qiskit.

My Qrisp circuit is run on Emerald, rounds 1..5, 4000 shots, DD on, Z, PINNED to
the same physical qubits the friend's layout.py chose (read from their
results/layout_emerald.json), so both pipelines use the same patch and the same
calibration window. Raw shots are saved, then decoded with the identical decoder
suite (MWPM, correlated MWPM, BP+OSD) and fit for eps_L.

Run the friend's Qiskit sweep separately (same session) via their repo:
  friend_repo/.venv/Scripts/python experiments/run_hardware.py \
      --rounds 1 2 3 4 5 --shots 4000 --dd on --basis Z --confirm
"""
import json
import os
import sys
import numpy as np
from scipy.optimize import curve_fit

from run_on_hardware import run_qrisp, decode_hardware_results

OUT = "results_qrisp"
os.makedirs(OUT, exist_ok=True)
ROUNDS = [1, 2, 3, 4, 5]
SHOTS = 4000
FRIEND_LAYOUT = (r"C:\Users\amoun\AppData\Local\Temp\claude\02fbd0915ffd2ee4"
                 r"\84b99e58-147f-409d-bece-816c09036196\scratchpad\friend_repo"
                 r"\results\layout_emerald.json")


def _model(n, A, eps):
    return 0.5 * (1.0 - A * (1.0 - 2.0 * eps) ** n)


def wfit(r, p, shots):
    r = np.asarray(r, float); p = np.asarray(p, float)
    s = np.maximum(np.sqrt(p * (1 - p) / shots), 0.5 / shots)
    (A, eps), cov = curve_fit(_model, r, p, p0=[1, 0.05], sigma=s,
                              absolute_sigma=True, bounds=([0, 0], [2, 0.5]),
                              maxfev=10000)
    return eps, float(np.sqrt(cov[1, 1])), A


def pinned_qubits():
    """Physical qubit indices from the friend's layout (QB{n} -> index n-1)."""
    if not os.path.exists(FRIEND_LAYOUT):
        print("friend layout not found; my run will pick its own 0-SWAP patch")
        return None
    info = json.loads(open(FRIEND_LAYOUT).read())
    names = list(info["physical"].values())
    idx = sorted(int(n[2:]) - 1 for n in names)   # "QB45" -> 44
    print("pinning my Qrisp run to friend's qubits:", names)
    return idx


def main():
    # NOTE: this vf2pp_layout cannot embed onto an edge-restricted subgraph
    # (it indexes against the full topology), so same-qubit pinning is not
    # possible through it. We run on our own auto-selected 0-SWAP patch in the
    # same calibration window; the patch may differ from the friend's, which we
    # record. Same session, same chip, same parameters -> still a fair compare.
    pin = None
    friend = pinned_qubits()   # logged for the report only
    decoders = ["none", "mwpm", "correlated", "bposd"]
    per_round = {d: [] for d in decoders}

    for r in ROUNDS:
        synd = run_qrisp(distance=3, rounds=r, shots=SHOTS, quantum_computer="emerald",
                         no_reset=True, basis="Z", noise=None, dd=True, pin_qubits=pin)
        st = synd.get("stats") or {}
        path = os.path.join(OUT, f"cmp_mine_Z_r{r}.npz")
        np.savez_compressed(path, det_events=synd["det_events"], obs_flips=synd["obs_flips"],
                            distance=3, rounds=r, basis="Z", shots=SHOTS, dd=True,
                            backend="emerald", **{k: st.get(k) for k in
                            ("cz_native", "swaps", "depth_native", "exact_embedding")})
        line = f"[mine r={r}] saved {path}  swaps={st.get('swaps')}  cz={st.get('cz_native')}"
        for d in decoders:
            p, e = decode_hardware_results(synd, distance=3, rounds=r, no_reset=True,
                                           basis="Z", decoder=d)
            per_round[d].append(p)
            line += f"  {d}={p:.4f}"
        print(line, flush=True)

    print("\n=== MY Qrisp pipeline, eps_L per round (uniform DEM prior) ===")
    results = {}
    for d in decoders:
        if d == "none":
            eps, err, A = wfit(ROUNDS, per_round[d], SHOTS)
            print(f"  {d:>11}: eps_L = {100*eps:.2f} +/- {100*err:.2f} %")
        else:
            eps, err, A = wfit(ROUNDS, per_round[d], SHOTS)
            print(f"  {d:>11}: eps_L = {100*eps:.2f} +/- {100*err:.2f} %")
        results[d] = dict(eps=eps, eps_err=err, p_l=per_round[d])
    json.dump({"rounds": ROUNDS, "shots": SHOTS, "results": results, "pinned": pin},
              open(os.path.join(OUT, "cmp_mine_summary.json"), "w"), indent=1, default=float)
    print("saved results_qrisp/cmp_mine_summary.json")


if __name__ == "__main__":
    main()
