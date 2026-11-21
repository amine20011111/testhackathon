# Pipeline internals

How a logical error rate is produced, stage by stage. Useful for reviewers and for AI
agents extending the code.

```
make_stim_circuit ─► stim_to_detector_experiment ─► run_qrisp ─► decode_hardware_results ─► fit ε_L
   (surface_code)        (stim_to_qrisp)              (run_on_hardware)   (run_on_hardware)   (benchmark_qrisp / curve_fit)
```

## 1. Circuit — `surface_code.make_stim_circuit(distance, rounds, basis, no_reset, noise)`
Generates the rotated surface-code memory experiment with Stim
(`stim.Circuit.generated("surface_code:rotated_memory_{z,x}", …)`). It **keeps the `MR`
gates**: the Qrisp converter needs them to perform the no-reset rewrite. `noise=None`
for the hardware circuit; a noise dict (e.g. `DEFAULT_NOISE`, uniform ~0.3 %) for
simulation and for the decoder's DEM.

## 2. Stim → Qrisp — `stim_to_qrisp.stim_to_detector_experiment(circ, no_reset=True)`
Builds an `iqm.qrisp_iqm.DetectorExperiment` from the Stim circuit.
- **No-reset rewrite.** Emerald has no mid-circuit reset. Without reset an ancilla's raw
  outcome accumulates: `m_r = s_r ⊕ m_{r-1}`, so the detector comparing rounds `r` and
  `r-1` becomes `m_r ⊕ m_{r-2}` (with `m_0 = 0`), and the final data-vs-ancilla detector
  uses `s_R = m_R ⊕ m_{R-1}`. The converter rewrites every detector accordingly.
- **Native RX/MX.** Extended so X-basis preparation (`RX`) and readout (`MX`) are handled
  (`RX` = reset-if-live + H; `MX` = H + Z-measure), enabling X-memory experiments.
- `.to_stim()` returns the rewritten no-reset Stim circuit — the single source of truth
  for both the detection-event ordering and the decoder's DEM.

## 3. Hardware — `run_on_hardware.run_qrisp(..., quantum_computer="emerald", dd=True)`
- `quantum_computer=None` → free local Stim sampling of `.to_stim()` (same code path, for
  validation). Otherwise connects to IQM Resonance.
- **Zero-SWAP native layout.** `_iqm_native_pass_manager(connectivity)` = `vf2pp_layout`
  (exact embedding, 0 SWAPs or it fails) **+** the IQM gate-conversion passes
  (`convert_to_cz`, `convert_to_prx`, …). We deliberately **do not** use
  `create_iqm_pass_manager`: its plasma router calls `instr.qubits[0]` and crashes on the
  DetectorExperiment's 0-qubit `parity` post-processing ops. vf2pp tolerates those ops,
  and because the d=3 patch embeds exactly on Emerald's grid no routing is needed.
- **Dynamical decoupling** (`dd=True`): a server-side pulse option
  (`CircuitCompilationOptions(dd_mode=ENABLED)`) set on the backend instance, because
  `_sample_via_backend` calls `backend.run(qc, shots)` without compilation options.
- Returns `{"det_events", "obs_flips", "stats"}`. `circuit_stats()` reports native CZ
  count, depth, and SWAP count (0) for the record.

## 4. Decode + fit — `run_on_hardware.decode_hardware_results(..., decoder=…)`
Rebuilds the **same** rewritten no-reset circuit *with* a noise model so the DEM has
weighted edges (detectors still match the data column-for-column), then decodes:
- `"mwpm"` / `"correlated"` — PyMatching (correlated enables X/Y-aware matching).
- `"bposd"` — `ldpc.BpOsdDecoder` on the full hyperedge model (via `beliefmatching`'s
  DEM→check-matrix helper).
- `"none"` — no correction (baseline).

Returns `(P_L, 1σ)` for that round count. `benchmark_qrisp.fit_epsilon_L` fits
`2·P_L(n) = 1 − A(1−2ε_L)^n` across round counts (free amplitude `A` absorbs
SPAM/boundary offset) to report ε_L ± 1σ.

## Gotchas
- The DEM must come from the circuit that actually ran; always rebuild it from
  `stim_to_detector_experiment(...).to_stim()` for the same `distance/rounds/basis/no_reset`.
- `ldpc==2.4.1` requires `numpy<=2.2.6`; installing it downgrades numpy. qrisp/iqm still
  work at numpy 2.2.6 (verified), but keep this in mind when upgrading.
- Same-qubit pinning across frameworks is not supported by this `vf2pp_layout` (it indexes
  against the full topology and errors on a restricted subgraph).
