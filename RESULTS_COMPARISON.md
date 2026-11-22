# Full comparison — Qrisp (ours) vs Qiskit (friend), + Pauli twirling

All numbers below are from **real IQM Emerald hardware** (no simulation), distance-3 rotated surface code, no-reset, native CZ, **0 SWAP**, dynamical decoupling on, Z-memory, rounds 1–5. **ε_L** is the logical error rate per round (lower = better); **P_L** is the logical error probability after n rounds. Both pipelines were run in the same calibration session.

## 1. Decoder & noise-model prior (same real shots)

The DEM *prior* (the noise model that sets the decoder's edge weights) is a pure decoding choice — these rows re-decode the **same** hardware shots. SI1000 is readout-dominant (readout = 5× gate error), unlike the uniform baseline where every error is equal.

| decoder | mine (uniform) | mine (SI1000) | friend (SI1000) |
|---|---|---|---|
| no correction | 6.78% | **6.78%** | 8.90% |
| MWPM | 2.99% | **2.83%** | 3.21% |
| correlated MWPM | 2.65% | **2.42%** | 3.00% |
| BP+OSD | 2.56% | **2.28%** | 2.74% |

**Best decoded ε_L (SI1000): mine 2.28% vs friend 2.74%.** Switching our prior uniform→SI1000 improved ε_L on every decoder. The decoder *algorithm* (MWPM→BP+OSD) still matters more than the prior on this clean d=3 patch.

## 2. Pauli twirling (randomized compiling)

Twirling wraps every two-qubit gate with random Pauli gates that cancel logically, so the circuit is unchanged but **coherent** hardware errors are averaged into **stochastic** ones — which the decoder's error model actually assumes. It has *no* effect in a stabilizer simulator (verified: untwirled and twirled decode identically there), so its value can only be measured on hardware. We pool K randomized instances per round and decode with the SI1000 prior.

Same-session IQM Emerald, no-twirl vs twirl (pooled randomized instances):

| decoder | ε_L no-twirl | ε_L twirl | change |
|---|---|---|---|
| MWPM | 2.55 ± 0.16% | 3.23 ± 0.19% | +0.69pp ↑ worse |
| BP+OSD | 2.14 ± 0.15% | 2.68 ± 0.18% | +0.54pp ↑ worse |

_Interpretation:_ **twirling slightly *worsened* ε_L here (~0.5–0.7pp, several σ), it did not help.** Two effects compete: (1) twirling converts *coherent* errors into stochastic ones the decoder prefers — a benefit — but (2) the random Pauli gates it inserts add real gate overhead (native depth rose ~38→47 at 5 rounds, with more single-qubit PRX gates). On this patch the benefit is near zero because **dynamical decoupling has already removed the coherent idle dephasing**, so there is little coherent error left to twirl away — while the extra-gate cost is non-zero. Net: twirling costs more than it saves. This is a genuine, useful result: with DD on, our error budget is **readout/stochastic-limited, not coherence-limited**, so randomized compiling is the wrong lever (readout mitigation or better qubits would help instead). Twirling would pay off on a patch *without* DD, where coherent errors dominate.

## 3. Takeaways

- **Qrisp vs Qiskit:** on matched parameters and prior, the two pipelines land in the same band; ours is competitive (best ε_L ≈ 2.3% with BP+OSD + SI1000). They agree because both run identical physics on the same chip — the framework is just the pen.

- **Biggest lever:** the decoder (MWPM→BP+OSD) and the qubit patch, not the SDK.

- **Prior:** SI1000 (readout-dominant) beats the uniform baseline, matching the Qiskit solution's setup.

- **Twirling:** implemented and verified correct, but on this DD-protected patch it slightly *worsened* ε_L (its gate overhead outweighs the near-zero coherent-error benefit) — telling us the remaining error is readout/stochastic-limited, not coherence-limited.
