"""Full Emerald run with Dynamical Decoupling ON.

Step 2: Z-basis sweep rounds=1..5, shots=4000  -> fit epsilon_L + plot.
Step 3: one X-basis job rounds=2, shots=2000    -> verify RX/MX on hardware.
"""
import os
import numpy as np
from benchmark_qrisp import benchmark
from run_on_hardware import run_qrisp, decode_hardware_results

OUT = "results_qrisp"
os.makedirs(OUT, exist_ok=True)

# ── Step 2: Z sweep on Emerald, DD ON ───────────────────────────────────────
print("### Z-basis sweep on Emerald (DD ON), rounds=1..5, shots=4000 ###")
eps, eps_err = benchmark(
    basis="Z", rounds_list=[1, 2, 3, 4, 5], shots=4000,
    quantum_computer="emerald", noise=None, dd=True, prefix="hw_dd",
)

# ── Step 3: single X-basis job on Emerald, DD ON ────────────────────────────
print("\n### X-basis verification on Emerald (DD ON), rounds=2, shots=2000 ###")
synd = run_qrisp(distance=3, rounds=2, shots=2000, quantum_computer="emerald",
                 no_reset=True, basis="X", noise=None, dd=True)
st = synd.get("stats") or {}
fx = os.path.join(OUT, "hw_dd_X_d3_r2.npz")
np.savez_compressed(
    fx, det_events=synd["det_events"], obs_flips=synd["obs_flips"],
    distance=3, rounds=2, basis="X", shots=2000, no_reset=True, dd=True,
    backend="emerald", cz_native=st.get("cz_native"), swaps=st.get("swaps"),
    depth_native=st.get("depth_native"), exact_embedding=st.get("exact_embedding"),
)
px, sx = decode_hardware_results(synd, distance=3, rounds=2, no_reset=True, basis="X")
print(f"Saved -> {fx}")
print(f"X-memory rounds=2: P_error={px:.4f} +/- {sx:.4f}  "
      f"cz_native={st.get('cz_native')} swaps={st.get('swaps')} "
      f"depth_native={st.get('depth_native')}")
