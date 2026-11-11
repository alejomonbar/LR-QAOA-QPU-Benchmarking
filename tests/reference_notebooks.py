"""Circuit builders copied unchanged from the experiment notebooks (the reference the
package is tested against). Do not edit: these define what the published data used."""

import networkx as nx
import numpy as np
from qiskit import QuantumCircuit


# ---- FC-Experiments.ipynb ------------------------------------------------------------
def layer_1D_full_Graph(G, gamma):
    num_qubits = G.number_of_nodes()
    permutation = np.arange(num_qubits)
    max_weight = np.max(np.abs([G[i][j]["weight"] for i, j in G.edges()]))
    layer = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        for j in range(i % 2, num_qubits - 1, 2):
            layer.cx(j, j + 1)
            layer.rz(2 * G[permutation[j]][permutation[j + 1]]["weight"] * gamma / max_weight, j + 1)
            layer.cx(j + 1, j)
            layer.cx(j, j + 1)
            permutation[[j, j + 1]] = permutation[[j + 1, j]]
    return layer


def qaoa_swap_network(G, gammas, betas):
    num_qubits = G.number_of_nodes()
    p = len(gammas)
    circ = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        circ.h(i)
    layer = lambda gamma: layer_1D_full_Graph(G, gamma)
    for pi in range(p):
        circ.compose(layer(gammas[pi]), range(num_qubits) if not pi % 2 else reversed(range(num_qubits)),
                     inplace=True)
        circ.rx(-2 * betas[pi], range(num_qubits))
    return circ


def ladder_shape(num_nodes):
    m = (num_nodes + 1) // 2
    return m, 2 * m - num_nodes


def ladder_schedule(num_nodes):
    m, _ = ladder_shape(num_nodes)
    permutation = [q if q < num_nodes else None for q in range(2 * m)]
    rounds = []
    for t in range(m):
        rung = [(c, m + c, permutation[c], permutation[m + c]) for c in range(m)
                if permutation[c] is not None and permutation[m + c] is not None]
        rail = []
        for r, phase in ((0, 0), (1, 1)):
            for c in range((t + phase) % 2, m - 1, 2):
                a, b = r * m + c, r * m + c + 1
                rail.append((a, b, permutation[a], permutation[b]))
                permutation[a], permutation[b] = permutation[b], permutation[a]
        rounds.append((rung, rail))
    return rounds, permutation


def layer_ladder_full_Graph(G, gamma):
    num_nodes = G.number_of_nodes()
    m, _ = ladder_shape(num_nodes)
    layer = QuantumCircuit(2 * m)
    max_weight = np.max(np.abs([G[i][j]["weight"] for i, j in G.edges()]))

    def angle(i, j):
        return 2 * G[i][j]["weight"] * gamma / max_weight

    for rung, rail in ladder_schedule(num_nodes)[0]:
        for a, b, i, j in rung:
            layer.cx(a, b)
            layer.rz(angle(i, j), b)
            layer.cx(a, b)
        for a, b, i, j in rail:
            if i is None or j is None:
                dummy, live = (a, b) if i is None else (b, a)
                layer.cx(live, dummy)
                layer.cx(dummy, live)
                continue
            layer.cx(a, b)
            layer.rz(angle(i, j), b)
            layer.cx(b, a)
            layer.cx(a, b)
    return layer


def qaoa_swap_network_ladder(G, gammas, betas):
    num_nodes = G.number_of_nodes()
    m, _ = ladder_shape(num_nodes)
    p = len(gammas)
    permutation = [q if q < num_nodes else None for q in range(2 * m)]
    circ = QuantumCircuit(2 * m)
    circ.h([pos for pos, q in enumerate(permutation) if q is not None])
    forward = list(range(2 * m))
    reverse = list(range(m - 1, -1, -1)) + list(range(2 * m - 1, m - 1, -1))
    for pi in range(p):
        circ.compose(layer_ladder_full_Graph(G, gammas[pi]), forward if not pi % 2 else reverse, inplace=True)
        permutation = [permutation[reverse[pos]] for pos in range(2 * m)]
        circ.rx(-2 * betas[pi], [pos for pos, q in enumerate(permutation) if q is not None])
    return circ, permutation


def ladder_measurement_map(permutation, ladders, nq):
    reps = len(ladders)
    qubits, clbits = [], []
    for sec, ladder in enumerate(ladders):
        for pos, node in enumerate(permutation):
            if node is None:
                continue
            qubits.append(ladder[pos])
            clbits.append(reps * nq - 1 - (sec * nq + node))
    return qubits, clbits


def qaoa_maxcut(G, gammas, betas):  # all-to-all (Quantinuum / IonQ / AQT)
    nodes = len(G.nodes())
    edges = [(i, j) for i, j in G.edges()]
    max_w = np.max(np.abs([G[i][j]["weight"] for i, j in G.edges()]))
    layers = len(gammas)
    qc = QuantumCircuit(nodes)
    qc.h(range(nodes))
    for p in range(layers):
        permutations = np.arange(nodes)
        for jj in range(nodes):
            for k in range(jj % 2, nodes - 1, 2):
                qubit_pair = (permutations[k], permutations[k + 1])
                if qubit_pair in edges or reversed(qubit_pair) in edges:
                    qc.rzz(2 * gammas[p] * G[qubit_pair[0]][qubit_pair[1]]["weight"] / max_w, *qubit_pair)
                permutations[[k, k + 1]] = permutations[[k + 1, k]]
        qc.rx(-2 * betas[p], range(nodes))
    return qc


# ---- 1D-Chain-Experiments.ipynb -------------------------------------------------------
def maxcut_qaoa_ibm_bound(GT, betas, gammas, max_nq, qubits_in_line, fractional_gates=True):
    layers = len(betas)
    max_weight = np.max(np.abs([GT[i][j]["weight"] for i, j in GT.edges()]))
    pairs_1 = {frozenset((qubits_in_line[i], qubits_in_line[i + 1])) for i in range(0, len(qubits_in_line) - 1, 2)}
    pairs_2 = {frozenset((qubits_in_line[i], qubits_in_line[i + 1])) for i in range(1, len(qubits_in_line) - 1, 2)}
    edges_1, edges_2 = [], []
    for i, j in GT.edges():
        w = GT[i][j]["weight"] / max_weight
        if abs(w) <= 1e-6:
            continue
        if frozenset((i, j)) in pairs_1:
            edges_1.append((i, j, w))
        elif frozenset((i, j)) in pairs_2:
            edges_2.append((i, j, w))
    ordered_edges = edges_1 + edges_2
    nodes = GT.number_of_nodes()
    nodes_list = list(GT.nodes)
    qc = QuantumCircuit(max_nq, nodes)
    qc.h(nodes_list)
    for p in range(layers):
        two_gamma = 2 * float(gammas[p])
        for i, j, w in ordered_edges:
            if fractional_gates:
                qc.rzz(two_gamma * w, i, j)
            else:
                qc.cx(i, j)
                qc.rz(two_gamma * w, j)
                qc.cx(i, j)
        qc.rx(-2 * float(betas[p]), nodes_list)
    qc.measure(nodes_list, range(nodes))
    return qc


def repeat_subgraph(G, qubits_line):
    n_qubits = G.number_of_nodes()
    n_reps = len(qubits_line) // n_qubits
    GT = nx.Graph()
    GT.add_nodes_from(qubits_line[:n_reps * n_qubits])
    for rep in range(n_reps):
        for i, j in G.edges:
            w = G[i][j]["weight"]
            GT.add_weighted_edges_from([[qubits_line[i + rep * n_qubits], qubits_line[j + rep * n_qubits], w]])
    return GT


# ---- NL-Experiments.ipynb -------------------------------------------------------------
def distribute_edges(graph):
    max_degree = max(dict(graph.degree()).values())
    layers = [[] for _ in range(max_degree)]
    edges_label = {n: edge for n, edge in enumerate(graph.edges())}
    n_edges = len(edges_label.keys())
    edges_graph = nx.Graph()
    edges_graph.add_nodes_from(edges_label.keys())
    for i in range(n_edges):
        for j in range(i + 1, n_edges):
            if edges_label[i][0] in edges_label[j] or edges_label[i][1] in edges_label[j]:
                edges_graph.add_edges_from([[i, j]])
    colors = nx.greedy_color(edges_graph, strategy="connected_sequential_bfs")
    for node, color in colors.items():
        layers[color].append(list(sorted(edges_label[node])))
    return layers


def full_qaoa_ibm(G, betas, gammas, sorted_gates, fractional_gates=False):
    """As in the notebook but with numeric angles (the notebook binds a ParameterVector)."""
    layers = len(betas)
    nodes = G.number_of_nodes()
    weights = {(i, j): G[i][j]["weight"] for i, j in G.edges} if nx.is_weighted(G) else {(i, j): 1 for i, j in G.edges}
    qc = QuantumCircuit(nodes)
    qc.h(range(nodes))
    for p in range(layers):
        for edge_group in sorted_gates:
            for i, j in G.edges():
                qbits = [i, j]
                if list(reversed(qbits)) in edge_group or qbits in edge_group:
                    if fractional_gates:
                        qc.rzz(2 * gammas[p] * round(weights[i, j], 4), *qbits)
                    else:
                        qc.cx(*qbits)
                        qc.rz(2 * gammas[p] * round(weights[i, j], 4), j)
                        qc.cx(*qbits)
        qc.rx(-2 * betas[p], range(nodes))
    qc.measure_all()
    return qc
