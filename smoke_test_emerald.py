"""One cheap Emerald smoke test: d=3, rounds=2, Z-memory, 1000 shots.

Submits a single real job to IQM Resonance, saves raw data immediately,
decodes, and reports P_error +/- 1 sigma plus circuit stats.
"""
import os
import numpy as np
from run_on_hardware import run_qrisp, decode_hardware_results

OUT = "results_qrisp"
os.makedirs(OUT, exist_ok=True)

DIST, RNDS, SHOTS, BASIS = 3, 2, 1000, "Z"

print("Submitting Emerald job (d=3, rounds=2, Z, 1000 shots)...")
synd = run_qrisp(distance=DIST, rounds=RNDS, shots=SHOTS,
                 quantum_computer="emerald", no_reset=True,
                 basis=BASIS, noise=None)

# Save raw hardware data FIRST — before decoding — so QPU shots are never lost.
stats = synd.get("stats") or {}
fname = os.path.join(OUT, f"hw_{BASIS}_d{DIST}_r{RNDS}_smoke.npz")
np.savez_compressed(
    fname,
    det_events=synd["det_events"], obs_flips=synd["obs_flips"],
    distance=DIST, rounds=RNDS, basis=BASIS, shots=SHOTS, backend="emerald",
    two_qubit_gates=stats.get("two_qubit_gates"), depth=stats.get("depth"),
    exact_embedding=stats.get("exact_embedding"), cz_native=stats.get("cz_native"),
    swaps=stats.get("swaps"), depth_native=stats.get("depth_native"),
)
print(f"Saved raw data -> {fname}  shapes: det={synd['det_events'].shape} "
      f"obs={synd['obs_flips'].shape}")

p, s = decode_hardware_results(synd, distance=DIST, rounds=RNDS,
                               no_reset=True, basis=BASIS)
print(f"\n=== EMERALD SMOKE TEST ===")
print(f"circuit: 2q={stats.get('two_qubit_gates')}  depth={stats.get('depth')}  "
      f"exact_embedding={stats.get('exact_embedding')}  "
      f"cz_native={stats.get('cz_native')}  swaps={stats.get('swaps')} "
      f"(0 => grid-aligned patch)  depth_native={stats.get('depth_native')}")
print(f"P_error(rounds=2) = {p:.4f} +/- {s:.4f}  (n={SHOTS})")
