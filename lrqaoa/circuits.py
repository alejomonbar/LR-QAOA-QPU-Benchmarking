"""LR-QAOA circuits for the three benchmark graphs, ported from the experiment notebooks.

Every builder returns a `Program` whose circuit measures node `node` of parallel section
`sec` into classical bit `sec * n + node` (register "c"). Angles may be floats or qiskit
Parameters, so a circuit can be transpiled once per p and bound for each delta.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from .layouts import ladder_shape


@dataclass
class Program:
    circuit: QuantumCircuit
    sections: int
    qubits: list[int]                      # physical qubits holding the problem
    zz_per_layer: int                      # logical two-qubit interactions per layer and section
    schedule: list[tuple[int, int, float]] = field(default_factory=list)  # (i, j, w) order, all-to-all only


def _device_circuit(width: int, n_clbits: int) -> QuantumCircuit:
    return QuantumCircuit(QuantumRegister(width, "q"), ClassicalRegister(n_clbits, "c"))


def _max_weight(G: nx.Graph) -> float:
    return float(np.max(np.abs([G[i][j]["weight"] for i, j in G.edges()])))


# --------------------------------------------------------------------- fully connected: 1D SWAP network
def fc_swap_network(G: nx.Graph, betas, gammas, line: list[int], width: int,
                    max_sections: int | None = None) -> Program:
    """FC problem on a chain of qubits: odd-even transposition SWAP network (RZZ+SWAP = 3 CX).

    One cost layer reverses the chain, so odd layers run on the reversed order (as in the
    notebooks). Copies of the problem run in parallel on consecutive pieces of `line`.
    """
    n, p = G.number_of_nodes(), len(gammas)
    max_w = _max_weight(G)
    holder = list(range(n))  # holder[q] = node currently on logical qubit q
    logical = QuantumCircuit(n)
    logical.h(range(n))
    for layer in range(p):
        order = list(range(n)) if layer % 2 == 0 else list(range(n - 1, -1, -1))
        for i in range(n):
            for j in range(i % 2, n - 1, 2):
                a, b = order[j], order[j + 1]
                u, v = holder[a], holder[b]
                logical.cx(a, b)
                logical.rz(2 * G[u][v]["weight"] * gammas[layer] / max_w, b)
                logical.cx(b, a)
                logical.cx(a, b)
                holder[a], holder[b] = v, u
        logical.rx(-2 * betas[layer], range(n))

    sections = max(1, len(line) // n)
    if max_sections:
        sections = min(sections, max_sections)
    circ = _device_circuit(width, sections * n)
    used = []
    for sec in range(sections):
        phys = line[sec * n:(sec + 1) * n]
        circ.compose(logical, phys, inplace=True)
        circ.measure(phys, [sec * n + holder[q] for q in range(n)])
        used += phys
    return Program(circ, sections, used, n * (n - 1) // 2)


# --------------------------------------------------------------------- fully connected: 2 x m ladder
def _ladder_schedule(num_nodes: int):
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


def _ladder_layer(G: nx.Graph, gamma) -> QuantumCircuit:
    n = G.number_of_nodes()
    m, _ = ladder_shape(n)
    layer = QuantumCircuit(2 * m)
    max_w = _max_weight(G)
    for rung, rail in _ladder_schedule(n)[0]:
        for a, b, i, j in rung:  # RZZ across rungs, no routing
            layer.cx(a, b)
            layer.rz(2 * G[i][j]["weight"] * gamma / max_w, b)
            layer.cx(a, b)
        for a, b, i, j in rail:  # RZZ + SWAP along the rows
            if i is None or j is None:
                dummy, live = (a, b) if i is None else (b, a)
                layer.cx(live, dummy)
                layer.cx(dummy, live)
                continue
            layer.cx(a, b)
            layer.rz(2 * G[i][j]["weight"] * gamma / max_w, b)
            layer.cx(b, a)
            layer.cx(a, b)
    return layer


def fc_ladder(G: nx.Graph, betas, gammas, ladders: list[list[int]], width: int,
              max_sections: int | None = None) -> Program:
    """FC problem on 2 x m ladders of a square-lattice device (~17% shallower than the chain)."""
    n, p = G.number_of_nodes(), len(gammas)
    m, _ = ladder_shape(n)
    permutation = [q if q < n else None for q in range(2 * m)]
    logical = QuantumCircuit(2 * m)
    logical.h([pos for pos, q in enumerate(permutation) if q is not None])
    forward = list(range(2 * m))
    reverse = list(range(m - 1, -1, -1)) + list(range(2 * m - 1, m - 1, -1))
    for layer in range(p):
        logical.compose(_ladder_layer(G, gammas[layer]), forward if layer % 2 == 0 else reverse, inplace=True)
        permutation = [permutation[reverse[pos]] for pos in range(2 * m)]
        logical.rx(-2 * betas[layer], [pos for pos, q in enumerate(permutation) if q is not None])

    ladders = ladders[:max_sections] if max_sections else ladders
    circ = _device_circuit(width, len(ladders) * n)
    used = []
    for sec, ladder in enumerate(ladders):
        circ.compose(logical, ladder, inplace=True)
        qubits = [ladder[pos] for pos, node in enumerate(permutation) if node is not None]
        clbits = [sec * n + node for node in permutation if node is not None]
        circ.measure(qubits, clbits)
        used += qubits
    return Program(circ, len(ladders), used, n * (n - 1) // 2)


# --------------------------------------------------------------------- fully connected: all-to-all devices
def fc_all_to_all(G: nx.Graph, betas, gammas, qubits: list[int] | None = None,
                  width: int | None = None) -> Program:
    """FC problem with direct RZZ gates (trapped ions), in SWAP-network pair order, no SWAPs."""
    n, p = G.number_of_nodes(), len(gammas)
    qubits = list(qubits) if qubits is not None else list(range(n))
    max_w = _max_weight(G)
    order = []
    perm = list(range(n))
    for jj in range(n):
        for k in range(jj % 2, n - 1, 2):
            u, v = perm[k], perm[k + 1]
            if G.has_edge(u, v):
                order.append((u, v, G[u][v]["weight"] / max_w))
            perm[k], perm[k + 1] = perm[k + 1], perm[k]
    circ = _device_circuit(width or max(qubits) + 1, n)
    circ.h([qubits[i] for i in range(n)])
    for layer in range(p):
        for u, v, w in order:
            circ.rzz(2 * gammas[layer] * w, qubits[u], qubits[v])
        circ.rx(-2 * betas[layer], [qubits[i] for i in range(n)])
    circ.measure([qubits[i] for i in range(n)], list(range(n)))
    return Program(circ, 1, qubits[:n], len(order), schedule=order)


# --------------------------------------------------------------------- 1D chain
def repeat_subgraph(G: nx.Graph, line: list[int]) -> nx.Graph:
    """Copies of the chain problem G (nodes 0..n-1) laid along `line`."""
    n = G.number_of_nodes()
    reps = len(line) // n
    GT = nx.Graph()
    GT.add_nodes_from(line[:reps * n])
    for rep in range(reps):
        for i, j in G.edges:
            GT.add_edge(line[i + rep * n], line[j + rep * n], weight=G[i][j]["weight"])
    return GT


def chain(G: nx.Graph, betas, gammas, line: list[int], width: int, two_qubit: str = "rzz",
          max_sections: int | None = None) -> Program:
    """1D-chain problem, repeated along `line`; ZZ terms in two parallel layers (even/odd bonds)."""
    n, p = G.number_of_nodes(), len(gammas)
    sections = max(1, len(line) // n)
    if max_sections:
        sections = min(sections, max_sections)
    GT = repeat_subgraph(G, line[:sections * n])
    max_w = _max_weight(G)
    pairs_1 = {frozenset((line[i], line[i + 1])) for i in range(0, len(line) - 1, 2)}
    pairs_2 = {frozenset((line[i], line[i + 1])) for i in range(1, len(line) - 1, 2)}
    edges = [(i, j, GT[i][j]["weight"] / max_w) for i, j in GT.edges() if abs(GT[i][j]["weight"]) > 1e-6]
    ordered = ([e for e in edges if frozenset(e[:2]) in pairs_1]
               + [e for e in edges if frozenset(e[:2]) in pairs_2])
    nodes = list(GT.nodes)
    circ = _device_circuit(width, len(nodes))
    circ.h(nodes)
    for layer in range(p):
        for i, j, w in ordered:
            if two_qubit == "rzz":
                circ.rzz(2 * gammas[layer] * w, i, j)
            else:
                circ.cx(i, j)
                circ.rz(2 * gammas[layer] * w, j)
                circ.cx(i, j)
        circ.rx(-2 * betas[layer], nodes)
    circ.measure(nodes, list(range(len(nodes))))
    return Program(circ, sections, nodes, n - 1)


# --------------------------------------------------------------------- native layout
def distribute_edges(G: nx.Graph) -> list[list[list[int]]]:
    """Edge colouring: groups of edges with no shared node (one parallel gate layer each)."""
    max_degree = max(dict(G.degree()).values())
    labels = dict(enumerate(G.edges()))
    conflict = nx.Graph()
    conflict.add_nodes_from(labels)
    for a in range(len(labels)):
        for b in range(a + 1, len(labels)):
            if labels[a][0] in labels[b] or labels[a][1] in labels[b]:
                conflict.add_edge(a, b)
    colors = nx.greedy_color(conflict, strategy="connected_sequential_bfs")
    layers = [[] for _ in range(max(max_degree, max(colors.values(), default=0) + 1))]
    for e, c in colors.items():
        layers[c].append(sorted(labels[e]))
    return [layer for layer in layers if layer]


def native_layout(G: nx.Graph, betas, gammas, two_qubit: str = "rzz", width: int | None = None) -> Program:
    """Problem graph = device coupling graph (node i on physical qubit i); no routing needed."""
    n, p = G.number_of_nodes(), len(gammas)
    weights = {(i, j): round(G[i][j].get("weight", 1), 4) for i, j in G.edges}
    groups = [set(map(tuple, g)) for g in distribute_edges(G)]
    ordered = []
    for g in groups:
        for i, j in G.edges():
            if (i, j) in g or (j, i) in g:
                ordered.append((i, j, weights[i, j]))
    nodes = list(G.nodes)
    circ = _device_circuit(width or max(nodes) + 1, n)
    circ.h(nodes)
    for layer in range(p):
        for i, j, w in ordered:
            if two_qubit == "rzz":
                circ.rzz(2 * gammas[layer] * w, i, j)
            else:
                circ.cx(i, j)
                circ.rz(2 * gammas[layer] * w, j)
                circ.cx(i, j)
        circ.rx(-2 * betas[layer], nodes)
    circ.measure(nodes, nodes)
    return Program(circ, 1, nodes, G.number_of_edges())
