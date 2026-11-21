# Results & Interpretation

All results are from **real IQM Emerald hardware** (not simulation). The code is a
distance-3 rotated surface code, 9 data + 8 ancilla = 17 qubits, **no mid-circuit
reset**, written in native H/PRX + CZ, **0 SWAPs** (every CZ is a physical coupler),
with IQM's server-side **dynamical decoupling (DD)** on. Each round count is a separate
job of 4000 shots. Uncertainties are 1σ binomial (per point) / fit error (for ε_L).

**Definitions.**
*P_L* = fraction of shots whose final decoded logical value differs from the prepared one.
*ε_L* = logical error **per round**, from fitting `2·P_L(n) = 1 − (1 − 2·ε_L)^n` over n = 1…5.
*No correction* = the raw parity of the logical row of data qubits (decoder disabled).

---

## 1. Headline — our Qrisp pipeline (Emerald, DD on, Z-memory)

| decoder | ε_L per round | what it is |
|---|---|---|
| no correction | **6.78 % ± 0.23 %** | baseline: read the logical qubit raw, no decoding |
| MWPM | **2.99 % ± 0.10 %** | standard minimum-weight perfect matching |
| correlated MWPM | **2.65 % ± 0.10 %** | MWPM that also uses X/Y error correlations |
| **BP+OSD** | **2.56 % ± 0.10 %** | belief-propagation + ordered-statistics (strongest) |

**Reading these numbers:**
- The decoded rows (2.5–3.0 %) are **~2.6× lower** than "no correction" (6.78 %) —
  error correction is clearly working on this patch.
- Better decoders help: MWPM → BP+OSD drops ε_L by ~0.4 pp on the same shots.
- `± 0.10 %` is the shot-noise error bar from 4000 shots; differences smaller than
  ~0.2 % are not statistically meaningful.

### Per-round logical error probability P_L (the data behind the fit)

| rounds n | no correction | MWPM | correlated | BP+OSD |
|---|---|---|---|---|
| 1 | 0.056 | 0.0050 | 0.0050 | 0.0050 |
| 2 | 0.128 | 0.0362 | 0.0333 | 0.0343 |
| 3 | 0.176 | 0.0698 | 0.0597 | 0.0620 |
| 4 | 0.219 | 0.0872 | 0.0785 | 0.0740 |
| 5 | 0.241 | 0.108  | 0.0993 | 0.0948 |

P_L **rises with rounds** (more time → more chances to fail) and would approach 50 %
(a coin flip) for many rounds. That is why a single P_L is not a fair score — we fit the
whole curve to extract the per-round ε_L. Figure: `results_qrisp/qec_results_report.pdf`.

### Dynamical decoupling helped
At rounds = 2, turning DD on lowered P_L from **0.056 → 0.030** (≈1.9×) with no change to
the gate-level circuit (DD is a server-side pulse pass that refocuses the idle, "live"
no-reset ancillas). Earlier smoke test (DD off) gave ε_L ≈ 3.0 %+; DD on reaches 2.56 %.

### Circuit quality (verified on hardware)
0 SWAPs at every round; native 2-qubit gates (CZ) scale 19 → 43 → 67 → 91 → 115 across
rounds 1→5; `exact_embedding = True` (the code fits Emerald's grid exactly). No routing
overhead at all.

---

## 2. Comparison — our Qrisp vs a Qiskit solution (same Emerald session)

Both pipelines were run **fresh, back-to-back, in the same calibration window**, with
**identical parameters** (d=3, no-reset, native CZ, 0 SWAP, DD on, Z, rounds 1–5,
4000 shots), then decoded with the **same decoder algorithms**.

| decoder | **Ours (Qrisp)** | **Friend's (Qiskit)** |
|---|---|---|
| no correction | 6.78 % ± 0.23 % | 8.90 % ± 0.15 % |
| MWPM | 2.99 % ± 0.10 % | 3.21 % ± 0.08 % |
| correlated MWPM | 2.65 % ± 0.10 % | 3.00 % ± 0.08 % |
| BP+OSD (best) | **2.56 % ± 0.10 %** | 2.74 % ± 0.07 % |

Figure: `results_qrisp/FINAL_qrisp_vs_qiskit_hardware.pdf`.

### What this shows
On matched parameters the two pipelines land in the **same 2.5–3.2 % band**. On this
run ours came out slightly lower on every decoder — but that is **within patch/
calibration variation**, not a "Qrisp beats Qiskit" effect (see §3). The important
takeaway is that **two correct implementations converge**, and the decoder upgrade
(MWPM → BP+OSD, ~0.4 pp) helps both the same way.

---

## 3. Why the two solutions are **not identical** (but should be close)

They land close (all decoded values 2.5–3.2 %) but differ run to run. Reasons, largest
first:

1. **Different physical qubits.** Each pipeline picks its own 17-qubit patch (ours via
   auto `vf2pp`, the friend's via a calibration-scored VF2 scan). Qubits differ in gate,
   readout and idle error — the friend's own data shows ε_L moving 2.65 %→3.87 % *just by
   changing the patch*. This single factor can explain the whole gap. (We tried to force
   identical qubits, but this `vf2pp_layout` cannot embed onto a restricted subgraph.)
2. **Different decoder prior (DEM).** Our decoder weights its graph with a **uniform**
   0.3 % noise model; the friend's uses **SI1000** (1 %) / calibrated. Same shots, slightly
   different weighting → slightly different decoding.
3. **Shot noise.** 4000 shots → ±0.08–0.10 % error bars. Part of the gap is pure
   statistics; re-running reshuffles the numbers by about that much.
4. **Calibration drift.** Even "same session" spans minutes, and Emerald's qubit
   parameters drift continuously.
5. **Tiny circuit differences.** Our Qrisp→native pass cancels a few boundary CZ
   (19 vs 24 at round 1) and may schedule gates slightly differently.
6. **Decoder config details.** Same algorithms, but small differences (BP iterations,
   OSD order, how correlated matching is enabled).

**The key point:** reasons 1–4 are **hardware and statistics, not the framework.**
Qrisp vs Qiskit is only the language the circuit is written in — Emerald executes the
same physics either way, so the logical error rate is set by the chip, not the SDK.
Two correct implementations are therefore *expected* to agree to within patch + shot
noise. A large, reproducible difference would instead signal a **bug** in one pipeline.
Being tied is the healthy, correct outcome.

---

## 4. Simulation cross-check (free, Stim)

The identical no-reset native circuit, decoded in simulation at uniform p = 0.3 %, gives
ε_L ≈ 0.33–0.35 % — far below hardware, as expected (the simulator omits Emerald's real
readout, idle/|1⟩-decay and correlated noise). This only confirms the pipeline is wired
correctly end to end; it is **not** a hardware prediction.

---

## 5. Limitations (honest scope)
- d = 3 only: Emerald has no 0-SWAP embedding for d = 5, so no distance-scaling (Λ) is shown.
- Our decoder prior is uniform; a calibration/SI1000 prior (as the friend uses) is a
  straightforward next improvement.
- Same-qubit pinning across the two frameworks was not possible, so the cross-pipeline
  comparison shares the session/calibration but not the exact patch.
- X-memory was validated (rounds 2, DD on) but not swept 1–5 on hardware.
