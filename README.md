# Surface-Code Memory on IQM Emerald — **Qrisp track**

A proof-of-concept quantum-error-correction pipeline that runs a distance-3 rotated
surface code on **real IQM Emerald hardware** and measures its **logical error rate**.
Built on the **Qrisp** framework (the Qrisp half of the IQM *Surface Code on Emerald*
challenge — see [CHALLENGE.md](CHALLENGE.md)).

```
Stim circuit  →  Qrisp DetectorExperiment  →  IQM Emerald (native CZ/PRX, 0 SWAP, DD)
              →  detection events  →  decoder (MWPM / correlated MWPM / BP+OSD)
              →  P_L(n)  →  exponential fit  →  ε_L  (logical error rate per round)
```

**Headline result (real Emerald hardware, d=3, DD on, Z-memory):**
> **ε_L = 2.56 % ± 0.10 % logical error per round** (BP+OSD decoder),
> down from **6.8 % with no correction** — error correction lowers the error ~2.6×.

Full numbers and plain-language interpretation: **[RESULTS.md](RESULTS.md)**.

---

## The two numbers this project produces

| symbol | name | meaning |
|---|---|---|
| **P_L** | logical error *probability* | fraction of shots whose decoded logical bit is wrong **after `n` rounds**. Grows with `n`. |
| **ε_L** | logical error *rate* (the LER) | error added **per single round** — the `n`-independent quality number. Obtained by fitting P_L(n). |

Analogy: a leaky boat. **P_L** = how much water is in the boat after `n` minutes.
**ε_L** = litres leaking *per minute*. The challenge wants the leak rate (ε_L), so we
run several round counts and fit, rather than reporting one P_L.

The fit (Google Quantum AI, Nature 2021/2023):
```
2 · P_L(n) = 1 − (1 − 2·ε_L)^n
```

---

## Why the Qrisp track

`iqm.qrisp_iqm.DetectorExperiment` carries the **detectors and the logical observable
inside the experiment object**, so detection events come straight back from the
hardware run — no separate syndrome-extraction step to get wrong. Qrisp also derives
the matching Stim circuit (`.to_stim()`) and its detector error model (DEM) for us, which
**guarantees the decoder's detectors line up with the hardware data**.

Key engineering choices (see [docs/PIPELINE.md](docs/PIPELINE.md)):
- **No-reset circuit** (Emerald has no mid-circuit reset). Detectors are rewritten to
  `m_r ⊕ m_{r-2}`; this rewrite is done by `stim_to_qrisp.py` and verified in simulation.
- **Zero SWAPs.** A routing-free native pass manager (`vf2pp` exact layout + CZ/PRX
  conversion) places the code on Emerald's square grid with **0 SWAPs** — every CZ is a
  physical coupler. (The stock IQM router is bypassed because it crashes on the
  DetectorExperiment's 0-qubit `parity` ops; see [docs/PIPELINE.md](docs/PIPELINE.md).)
- **Dynamical decoupling** via IQM's server-side pulse pass (`dd=True`), which refocuses
  the idle no-reset ancillas.
- **Z and X memory.** The converter was extended to handle native `RX`/`MX` so X-basis
  experiments run too.
- **Three decoders.** MWPM, correlated MWPM, and BP+OSD (`ldpc`).

---

## Quick start

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # Windows (use .venv/bin on Linux/Mac)

# 1) FREE — no token: local simulation of the exact no-reset circuit + eps_L fit
.venv/Scripts/python benchmark_qrisp.py

# 2) HARDWARE — put your token in .env first (see .env.example)
.venv/Scripts/python smoke_test_emerald.py          # one cheap job (d=3, 2 rounds, 1000 shots)
.venv/Scripts/python run_hw_dd_sweep.py             # full Z sweep rounds 1-5 + X job, DD on

# 3) Re-make the figures/PDFs from saved data (free)
.venv/Scripts/python make_report_pdf.py
.venv/Scripts/python make_final_comparison.py       # our Qrisp vs a Qiskit solution
```

**Token:** never hard-code it. Copy `.env.example` → `.env` and paste your
`IQM_TOKEN` there (`.env` is git-ignored). Local simulation needs no token.

---

## Repository guide

### Core pipeline
| file | role |
|---|---|
| `surface_code.py` | `make_stim_circuit()` — generate the d=3 rotated surface-code Stim circuit (Z/X, no-reset, optional noise). |
| `stim_to_qrisp.py` | `stim_to_detector_experiment()` — Stim → Qrisp `DetectorExperiment`; does the no-reset detector rewrite and native `RX`/`MX`. |
| `run_on_hardware.py` | `run_qrisp()` (build → Emerald → raw detection events, with 0-SWAP layout + DD), `circuit_stats()`, and `decode_hardware_results()` (MWPM / correlated / BP+OSD + ε_L). |
| `internal_helpers.py`, `stim_to_qiskit.py`, `extract_syndromes.py`, `build_emerald_qubit_rotated.py` | challenge-scaffold helpers (Qiskit track + utilities). |

### Experiments (runnable)
| file | what it does |
|---|---|
| `raw_stim_d3_surface_code.py` | pure-Stim simulation baseline (sanity reference). |
| `benchmark_qrisp.py` | sweep rounds 1–5, local or hardware, save raw `.npz`, fit ε_L, plot. |
| `smoke_test_emerald.py` | one small hardware job to validate the end-to-end chain. |
| `run_hw_dd_sweep.py` | full hardware Z sweep (DD on) + one X-basis job. |
| `run_fair_compare.py` | fresh Emerald run decoded with all three decoders (used for the comparison). |

### Figures / reports
| file | output |
|---|---|
| `make_report_pdf.py` | `results_qrisp/qec_results_report.pdf` — our hardware results. |
| `make_final_comparison.py` | `results_qrisp/FINAL_qrisp_vs_qiskit_hardware.pdf` — Qrisp vs Qiskit, same-session hardware. |

### Data
`results_qrisp/` — raw per-shot hardware data (`*.npz`), fitted summaries (`*.json`),
and the figures/PDFs. Raw shots are saved **before** decoding, so any decoder/noise-model
choice can be revisited without spending QPU time.

---

## Results at a glance

Fresh same-session IQM Emerald run (d=3, no-reset, 0 SWAP, DD on, Z, rounds 1–5, 4000 shots):

| decoder | ε_L per round |
|---|---|
| no correction | 6.78 % ± 0.23 % |
| MWPM | 2.99 % ± 0.10 % |
| correlated MWPM | 2.65 % ± 0.10 % |
| **BP+OSD** | **2.56 % ± 0.10 %** |

See **[RESULTS.md](RESULTS.md)** for the per-round P_L tables, the Qrisp-vs-Qiskit
comparison, and a full interpretation of every number.

---

## For other AI agents reading this repo

- Entry point for the physics: `surface_code.make_stim_circuit` → `stim_to_qrisp.stim_to_detector_experiment`.
- Entry point for hardware: `run_on_hardware.run_qrisp(quantum_computer="emerald", dd=True)`; `quantum_computer=None` runs a free local Stim simulation with the same code path.
- Decoding + ε_L: `run_on_hardware.decode_hardware_results(syndromes, rounds=…, decoder="mwpm"|"correlated"|"bposd")`.
- The DEM used for decoding is always rebuilt from the **same** rewritten no-reset circuit that produced the shots, so detectors match column-for-column.
- Never read the token from source; it comes from `$IQM_TOKEN` or `.env`.

## Acknowledgements
Built on IQM's challenge scaffold ([CHALLENGE.md](CHALLENGE.md)). The Qiskit-track
numbers in the comparison come from a separate solution by a teammate and were
independently reproduced from their saved raw hardware shots.
