"""Pauli twirling (randomized compiling) for the surface-code circuit.

Each two-qubit gate (CX) is wrapped with random single-qubit Pauli gates:

    ──P_c──●──P_c'──          with  P' = CX (P_c ⊗ P_t) CX
    ──P_t──X──P_t'──

so the *logical* circuit is unchanged (the Paulis cancel through the CX), but a
*coherent* CX error is averaged over the Pauli group and becomes an effective
stochastic (Pauli) channel — which the decoder's error model actually assumes.

Twirling has NO effect in a stabilizer simulator (Stim noise is already
stochastic); its benefit only shows on real hardware. In simulation we use it to
check correctness: a twirled circuit must decode to the same logical error rate.

The twirled circuit keeps every measurement, reset and detector in place (only
1-qubit Paulis are inserted, so measurement-record indices are unchanged), and
`stim_to_detector_experiment` recomputes the detector reference from it, so the
whole downstream pipeline works unchanged.
"""
from __future__ import annotations

import numpy as np
import stim

# Pauli as (x, z) bits:  (0,0)=I  (1,0)=X  (0,1)=Z  (1,1)=Y
_GATE = {(1, 0): "X", (0, 1): "Z", (1, 1): "Y"}


def _conj_through_cx(ac, zc, at, zt):
    """Conjugate P_c⊗P_t by CX(control=c, target=t): returns (c',t') bits.

    CX rules:  X_c→X_cX_t,  Z_c→Z_c,  X_t→X_t,  Z_t→Z_cZ_t.
    """
    c_after = (ac, (zc ^ zt))
    t_after = ((ac ^ at), zt)
    return c_after, t_after


def twirl_circuit(circuit: stim.Circuit, seed: int) -> stim.Circuit:
    """Return a randomized-compiled copy of `circuit` (CX gates Pauli-twirled)."""
    rng = np.random.default_rng(seed)
    flat = circuit.flattened()
    out = stim.Circuit()

    def emit_pauli(q, bits):
        g = _GATE.get(bits)
        if g is not None:
            out.append(g, [q])

    for inst in flat:
        if inst.name != "CX":
            out.append(inst)
            continue
        targets = [t.value for t in inst.targets_copy()]
        pairs = list(zip(targets[::2], targets[1::2]))
        before, after = {}, {}
        for c, t in pairs:
            ac, zc = int(rng.integers(2)), int(rng.integers(2))
            at, zt = int(rng.integers(2)), int(rng.integers(2))
            before[c] = (ac, zc)
            before[t] = (at, zt)
            (cac, czc), (tat, tzt) = _conj_through_cx(ac, zc, at, zt)
            after[c] = (cac, czc)
            after[t] = (tat, tzt)
        for q, bits in before.items():
            emit_pauli(q, bits)
        out.append("CX", targets)          # the CX layer, unchanged
        for q, bits in after.items():
            emit_pauli(q, bits)
    return out
