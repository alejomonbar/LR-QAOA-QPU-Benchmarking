"""The package circuits must give exactly the same node-bitstring distribution as the
notebook circuits, each read with its own pipeline's bit-ordering convention."""

import networkx as nx
import numpy as np
import pytest
from qiskit import ClassicalRegister, QuantumCircuit
from qiskit.quantum_info import Statevector

from lrqaoa import circuits
from lrqaoa.layouts import ladder_qubits, ladder_shape
from lrqaoa.schedule import linear_ramp

import reference_notebooks as ref


def clbit_distribution(circ: QuantumCircuit) -> dict[str, float]:
    """Exact distribution over classical-bit strings, character c = clbit c."""
    meas = {}
    for inst in circ.data:
        if inst.operation.name == "measure":
            meas[circ.find_bit(inst.clbits[0]).index] = circ.find_bit(inst.qubits[0]).index
    probs = Statevector(circ.remove_final_measurements(inplace=False)).probabilities_dict()
    out: dict[str, float] = {}
    for key, pr in probs.items():
        qbits = key[::-1]  # qubit q at index q
        s = "".join(qbits[meas[c]] for c in range(len(meas)))
        out[s] = out.get(s, 0) + pr
    return out


def assert_same(a: dict, b: dict):
    keys = set(a) | set(b)
    assert max(abs(a.get(k, 0) - b.get(k, 0)) for k in keys) < 1e-9


def random_graph(n, complete=True, seed=0):
    rng = np.random.default_rng(seed)
    G = nx.complete_graph(n) if complete else nx.path_graph(n)
    for i, j in G.edges:
        G[i][j]["weight"] = float(rng.choice([0.1, 0.2, 0.5, 2.0]))
    return G


@pytest.mark.parametrize("n,p", [(4, 1), (5, 2), (5, 3), (6, 2)])
def test_fc_swap_network_matches_notebook(n, p):
    G = random_graph(n)
    betas, gammas = linear_ramp(p, 0.63)
    line = list(range(n))
    new = circuits.fc_swap_network(G, betas, gammas, line, width=n)
    old = QuantumCircuit(n)
    old.add_register(ClassicalRegister(n))
    old.compose(ref.qaoa_swap_network(G, gammas, betas), line, inplace=True)
    old.measure(line, list(reversed(range(n))) if not p % 2 else list(range(n)))
    # notebook pipeline used the qiskit key as-is (clbit n-1 first)
    old_dist = {k[::-1]: v for k, v in clbit_distribution(old).items()}
    assert_same(clbit_distribution(new.circuit), old_dist)


@pytest.mark.parametrize("n,p", [(4, 2), (5, 1), (6, 3)])
def test_fc_ladder_matches_notebook(n, p):
    G = random_graph(n)
    betas, gammas = linear_ramp(p, 0.3)
    m, _ = ladder_shape(n)
    ladders = ladder_qubits(m, n_rows=4, n_cols=2)[:1]
    width = 8
    new = circuits.fc_ladder(G, betas, gammas, ladders, width)
    qc, perm = ref.qaoa_swap_network_ladder(G, gammas, betas)
    old = QuantumCircuit(width)
    old.add_register(ClassicalRegister(n))
    old.compose(qc, ladders[0], inplace=True)
    old.measure(*ref.ladder_measurement_map(perm, ladders, n))
    old_dist = {k[::-1]: v for k, v in clbit_distribution(old).items()}
    assert_same(clbit_distribution(new.circuit), old_dist)


@pytest.mark.parametrize("n,p", [(4, 2), (5, 3)])
def test_fc_all_to_all_matches_notebook(n, p):
    G = random_graph(n)
    betas, gammas = linear_ramp(p, 0.2)
    new = circuits.fc_all_to_all(G, betas, gammas)
    old = QuantumCircuit(n, n)
    old.compose(ref.qaoa_maxcut(G, gammas, betas), range(n), inplace=True)
    old.measure(range(n), range(n))
    # pytket / nexus counts are ordered by bit, i.e. character c = clbit c
    assert_same(clbit_distribution(new.circuit), clbit_distribution(old))


@pytest.mark.parametrize("two_qubit", ["rzz", "cx"])
def test_chain_matches_notebook(two_qubit):
    n, p = 4, 3
    G = random_graph(n, complete=False)
    betas, gammas = linear_ramp(p, 1.0)
    line = [3, 2, 1, 0, 4, 5, 6, 7, 8]  # 2 sections + 1 spare qubit
    new = circuits.chain(G, betas, gammas, line, width=9, two_qubit=two_qubit)
    GT = ref.repeat_subgraph(G, line)
    old = ref.maxcut_qaoa_ibm_bound(GT, betas, gammas, 9, line, fractional_gates=two_qubit == "rzz")
    assert new.sections == 2
    # the 1D pipeline reversed the qiskit key, i.e. character c = clbit c
    assert_same(clbit_distribution(new.circuit), clbit_distribution(old))


def test_native_layout_matches_notebook():
    G = nx.grid_2d_graph(2, 3)
    G = nx.convert_node_labels_to_integers(G)
    rng = np.random.default_rng(3)
    for i, j in G.edges:
        G[i][j]["weight"] = float(rng.choice([0.1, 0.2, 0.3, 0.5, 1.0]))
    betas, gammas = linear_ramp(3, 0.75, decimals=4)
    new = circuits.native_layout(G, betas, gammas, two_qubit="rzz")
    old = ref.full_qaoa_ibm(G, betas, gammas, ref.distribute_edges(G), fractional_gates=True)
    assert_same(clbit_distribution(new.circuit), clbit_distribution(old))
