import os
from pathlib import Path

from surface_code import *
from stim_to_qiskit import stim_to_qiskit
from build_emerald_qubit_rotated import *
from extract_syndromes import *
from qiskit import transpile

SERVER_URL = "https://resonance.iqm.tech"


def _load_token() -> str:
    """IQM Resonance token from $IQM_TOKEN or a git-ignored .env file.

    The token is a SECRET - it is never hard-coded here so this repo is safe to
    share publicly. Put `IQM_TOKEN=...` in a local .env (see .env.example), or
    export it in your shell, before any hardware run.
    """
    if os.environ.get("IQM_TOKEN"):
        return os.environ["IQM_TOKEN"]
    env = Path(__file__).resolve().parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("IQM_TOKEN="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return ""   # local simulation (quantum_computer=None) needs no token


TOKEN = _load_token()


# ─────────────────────────────────────────────────────────────────────────────
#  5.  HARDWARE EXECUTION ON IQM RESONANCE
#
#  Two equal tracks. Pick ONE. Both return the same syndromes dict
#  (at least "det_events" and "obs_flips"), so decode_hardware_results()
#  works for either.
#
#  NOTE: Emerald does not support mid-circuit reset -> use the no-reset circuit.
# ─────────────────────────────────────────────────────────────────────────────

def run_qiskit(
    distance: int    = 3,
    rounds: int      = 1,
    shots: int       = 5_000,
    token: str       = None,
    quantum_computer: str = "emerald",
    no_reset: bool   = True,
) -> dict:
    """
    Build in qiskit. Runs the surface code on IQM Emerald via IQM Resonance.

        Stim circuit → Qiskit circuit → transpile → run → counts
        → raw measurements → extract_syndromes()

    Parameters
    ----------
    distance         : code distance (use 3 for emerald)
    rounds           : measurement rounds
    shots            : number of circuit executions
    token            : IQM Resonance API token (falls back to TOKEN)
    quantum_computer : e.g. "emerald"
    no_reset         : build the no-reset circuit (required on Emerald)

    Returns
    -------
    syndromes : dict  output of extract_syndromes()
                "det_events" (shots, num_detectors), "obs_flips" (shots, num_observables), ...
    """
    from iqm.qiskit_iqm import IQMProvider

    # Build circuits, exchange for make_qiskit_circuit() if desired
    stim_circ  = make_stim_circuit(distance, rounds, no_reset=no_reset, noise=None)

    #CREATE A CIRCUIT TO BE EXECUTED ON HARDWARE
    qc = []
    #qc, stim_to_dense, meas_order = stim_to_qiskit(stim_circ)
    #qc = make_qiskit_circuit(args)


    # OPTIONAL: IF YOU WANT TO ASSIGN QUBIT MAP BY HAND
    # Map abstract Qiskit qubits to emerald physical qubits
    qubit_map  = build_emerald_qubit_map(stim_circ)

    # HIGHLY RECOMMEND PRINTING THIS, if you are using it.
    # print(qubit_map)
    # initial_layout: Qiskit needs a list where position i = physical qubit for logical i
    n_qubits   = qc.num_qubits
    layout     = [qubit_map.get(i, i) for i in range(n_qubits)]

    # Connect to IQM Resonance
    provider   = IQMProvider(
        SERVER_URL,
        quantum_computer=quantum_computer,
        token=token or TOKEN
    )
    backend    = provider.get_backend()

    # Transpile: Qiskit transpilerwill insert SWAPs for diagonal CX pairs automatically
    # think about whether this is necessary
    qc_t       = transpile(
    # arguments
    )
    print(f"Transpiled circuit depth: {qc_t.depth()}  "
          f"(ideal: {qc.depth()}, extra depth from SWAPs)")

    # Run
    job        = backend.run(qc_t, shots=shots)
    counts     = job.result().get_counts()

    # Convert counts dict → (shots, num_measurements) numpy array
    raw_meas   = counts_to_measurement_array(counts, stim_circ.num_measurements,
                                               shots)
    # m2d converter must come from the circuit that actually ran
    return extract_syndromes(raw_meas, stim_circ)



def _iqm_native_pass_manager(connectivity):
    """
    Routing-free IQM pass manager: vf2pp exact layout (0 SWAPs) + native-gate
    conversion (CZ/PRX).

    We cannot use create_iqm_pass_manager here: its plasma router calls
    instr.qubits[0] and crashes on the DetectorExperiment's 0-qubit `parity`
    post-processing ops. vf2pp tolerates those ops, and because the rotated
    surface-code patch embeds exactly on Emerald's square grid, no routing /
    SWAP insertion is needed — so we keep only layout + the conversion passes
    (pulled from create_iqm_pass_manager's own namespace).
    """
    from iqm.qrisp_iqm.passes import create_iqm_pass_manager, vf2pp_layout
    g = create_iqm_pass_manager.__globals__
    pm = g["PassManager"]()
    pm += vf2pp_layout(list(connectivity))     # exact embedding -> 0 SWAPs
    pm += g["decompose"]()
    pm += g["convert_to_cz"]()
    pm += g["combine_single_qubit_gates"]
    pm += g["cancel_zero_controls"]
    pm += g["commute_phases"](False)
    pm += g["convert_to_prx"]
    return pm


def circuit_stats(experiment, connectivity=None) -> dict:
    """
    Report comparison stats vs. the Qiskit track:
      - logical 2-qubit gate count and depth (pre-compilation),
      - exact_embedding: whether vf2pp finds a zero-SWAP layout on Emerald,
      - the NATIVE compiled circuit (CZ/PRX) actually run: CZ count, SWAP
        count (0 confirms the surface-code patch aligns to Emerald's grid),
        and native depth.
    """
    qc = experiment.to_qc()
    stats = {
        "two_qubit_gates": int(qc.cnot_count()),
        "depth": int(qc.depth()),
        "exact_embedding": None,
        "cz_native": None,
        "swaps": None,
        "depth_native": None,
    }
    if connectivity is not None:
        from iqm.qrisp_iqm import vf2pp_layout
        conn = list(connectivity)
        # (1) Exact-embedding check: vf2pp finds a 0-SWAP layout or raises.
        try:
            vf2pp_layout(conn)(qc)
            stats["exact_embedding"] = True
        except Exception:
            stats["exact_embedding"] = False
        # (2) Native compilation (CZ/PRX) with the SAME pass manager used for
        #     the run, so these stats describe the circuit that actually runs.
        try:
            native = _iqm_native_pass_manager(conn).run(qc)
            ops = {k.lower(): v for k, v in native.count_ops().items()}
            stats["cz_native"] = int(ops.get("cz", 0))
            stats["swaps"] = int(ops.get("swap", 0) + ops.get("move", 0))
            stats["depth_native"] = int(native.depth())
        except Exception as e:
            stats["note"] = f"native transpile failed: {e}"
    return stats


def run_qrisp(
    distance: int    = 3,
    rounds: int      = 1,
    shots: int       = 5_000,
    token: str       = None,
    quantum_computer: str = "emerald",
    no_reset: bool   = True,
    basis: str       = "Z",
    noise: dict      = None,
    dd: bool         = False,
    pin_qubits: list = None,
) -> dict:
    """
    Build in qrisp. Runs the surface code on IQM Emerald via IQM Resonance.

        Stim circuit → Qrisp DetectorExperiment → IQMBackend → run
        → detection events + observable flips

    The DetectorExperiment stores the info the detectors and observables itself, so
    counts_to_measurement_array() and extract_syndromes() are not needed here.

    Parameters
    ----------
    distance         : code distance (use 3 for emerald)
    rounds           : measurement rounds
    shots            : number of circuit executions
    token            : IQM Resonance API token 
    quantum_computer : e.g. "emerald"
    no_reset         : build the no-reset circuit (required on Emerald)

    Returns
    -------
    syndromes : dict  same keys as extract_syndromes() from qiskit function
                "det_events" (shots, num_detectors), "obs_flips" (shots, num_observables)
    """
    import os
    import numpy as np
    from stim_to_qrisp import stim_to_detector_experiment

    # Build the Stim circuit. We keep the MR gates: stim_to_detector_experiment
    # applies the no-reset rewrite itself. noise=None on hardware (real noise
    # comes from the QPU); pass a noise model for a meaningful local simulation.
    stim_circ  = make_stim_circuit(distance, rounds, basis=basis,
                                   no_reset=no_reset, noise=noise)
    experiment = stim_to_detector_experiment(stim_circ, no_reset=no_reset)

    # Rewritten no-reset Stim circuit; its detectors are already in the
    # m'_j XOR m'_prev form, so det_events/obs_flips sampled from it line up
    # with the DEM built from the same circuit in decode_hardware_results().
    exp_stim   = experiment.to_stim()

    stats = None
    if quantum_computer is None:
        # ── Local simulation (free, no IQM Resonance) ───────────────────────
        det_events, obs_flips = exp_stim.compile_detector_sampler().sample(
            shots, separate_observables=True)
    else:
        # ── Hardware execution on IQM Resonance ─────────────────────────────
        from iqm.qrisp_iqm import IQMBackend
        os.environ["IQM_TOKEN"] = token or TOKEN

        # Connect once to read the device coupling map, then build a routing-free
        # native pass manager (vf2pp exact layout + CZ/PRX conversion). See
        # _iqm_native_pass_manager for why the stock router is avoided.
        probe   = IQMBackend(server_url=SERVER_URL,
                             device_instance=quantum_computer)
        conn    = list(probe.connectivity)
        # Same-qubit pinning: restrict the coupler graph to a given set of
        # physical qubit indices so vf2pp can only embed the code there (used to
        # run on the exact qubits another pipeline's layout chose, for a fair
        # same-patch comparison). vf2pp still guarantees 0 SWAPs or fails.
        if pin_qubits is not None:
            pinset = set(int(q) for q in pin_qubits)
            conn = [e for e in conn if e[0] in pinset and e[1] in pinset]
            print(f"[pin] restricted connectivity to {len(pinset)} qubits, "
                  f"{len(conn)} couplers")
        pm      = _iqm_native_pass_manager(conn)

        # Dynamical decoupling is a SERVER-SIDE pulse-level option applied
        # during circuit->pulse compilation (it refocuses idle qubits, e.g.
        # the "live" no-reset ancillas). _sample_via_backend calls
        # backend.run(qc, shots) without compilation_options, so we set it on
        # the backend instance; run() falls back to self.compilation_options.
        comp_opts = None
        if dd:
            from iqm.iqm_client import CircuitCompilationOptions, DDMode
            comp_opts = CircuitCompilationOptions(dd_mode=DDMode.ENABLED)

        backend = IQMBackend(server_url=SERVER_URL,
                             device_instance=quantum_computer,
                             pass_manager=pm,
                             compilation_options=comp_opts)

        # Log circuit stats for the Qiskit-track comparison (swaps should be 0).
        stats = circuit_stats(experiment, conn)
        stats["dd"] = bool(dd)
        print(f"[circuit_stats] 2q={stats['two_qubit_gates']}  "
              f"depth={stats['depth']}  exact_embedding={stats['exact_embedding']}  "
              f"cz_native={stats['cz_native']}  swaps={stats['swaps']}  "
              f"depth_native={stats['depth_native']}  dd={stats['dd']}")

        # _sample_via_backend runs the traced circuit and applies the
        # DetectorExperiment post-processing to return detection events +
        # observable flips directly.
        det_events, obs_flips = experiment._sample_via_backend(
            shots=shots, backend=backend)

    det_events = np.asarray(det_events, dtype=bool)
    obs_flips  = np.asarray(obs_flips,  dtype=bool)
    if obs_flips.ndim == 1:
        obs_flips = obs_flips.reshape(-1, 1)

    return {"det_events": det_events, "obs_flips": obs_flips, "stats": stats}



def decode_hardware_results(
    syndromes: dict,
    distance: int = 3,
    rounds: int   = 1,
    no_reset: bool = True,
    basis: str    = "Z",
    noise: dict   = None,
    decoder: str  = "mwpm",
) -> tuple[float, float]:
    """
    Decodes the output of run_qiskit() or run_qrisp() via the chosen decoder.

    decoder : "mwpm"       - PyMatching minimum-weight perfect matching (default)
              "correlated" - PyMatching with correlated (X/Y-aware) matching
              "bposd"      - belief propagation + ordered-statistics decoding on
                             the full hyperedge model (needs `ldpc`+`beliefmatching`)
              "none"       - no correction: raw logical flip rate (baseline)

    The DEM is built from the SAME rewritten no-reset circuit that produced
    det_events (with `noise` so it has weighted edges); detectors match the
    syndromes column-for-column.

    Returns
    -------
    p_error : float   logical error probability after `rounds` rounds
    err     : float   1-sigma binomial (shot-noise) uncertainty on p_error
    """
    import numpy as np
    import pymatching
    from stim_to_qrisp import stim_to_detector_experiment

    dem_noise  = noise if noise is not None else DEFAULT_NOISE
    stim_circ  = make_stim_circuit(distance, rounds, basis=basis,
                                   no_reset=no_reset, noise=dem_noise)
    experiment = stim_to_detector_experiment(stim_circ, no_reset=no_reset)
    dem_circ   = experiment.to_stim()
    dem        = dem_circ.detector_error_model(decompose_errors=True)

    det = np.asarray(syndromes["det_events"], dtype=bool)
    obs = np.asarray(syndromes["obs_flips"],  dtype=bool)
    if obs.ndim == 1:
        obs = obs.reshape(-1, 1)

    if decoder == "none":
        pred = np.zeros_like(obs)
    elif decoder == "bposd":
        pred = _decode_bposd(det, dem_circ)
    else:  # "mwpm" or "correlated"
        correlated = (decoder == "correlated")
        matcher = pymatching.Matching.from_detector_error_model(
            dem, enable_correlations=correlated)
        pred = matcher.decode_batch(det, enable_correlations=correlated)

    errors = np.any(pred != obs, axis=1)
    shots  = int(errors.shape[0])
    p_error = float(np.mean(errors)) if shots else 0.0
    err     = float(np.sqrt(p_error * (1.0 - p_error) / shots)) if shots else 0.0
    return p_error, err


def _decode_bposd(det_events, noisy_circuit):
    """BP+OSD on the full hyperedge error model (ldpc + beliefmatching)."""
    import numpy as np
    import ldpc
    from beliefmatching import detector_error_model_to_check_matrices

    dem  = noisy_circuit.detector_error_model(decompose_errors=True)
    mats = detector_error_model_to_check_matrices(dem, allow_undecomposed_hyperedges=True)
    dec  = ldpc.BpOsdDecoder(mats.check_matrix, error_channel=list(mats.priors),
                             max_iter=30, bp_method="product_sum",
                             osd_method="osd_cs", osd_order=7)
    L = mats.observables_matrix.tocsr()
    out = np.zeros((len(det_events), L.shape[0]), dtype=bool)
    for k, syndrome in enumerate(np.asarray(det_events, dtype=np.uint8)):
        out[k] = (L @ dec.decode(syndrome)) % 2
    return out