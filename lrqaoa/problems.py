"""Weighted MaxCut problem banks used by the benchmark, and how to grow them.

Banks (in Data/):
  FC  WMC_FC.npy             {nq: {"G", "sol", ...}}           complete graphs
  1D  problems_1DChain.npy   {"G": {nq: G}, "sol": {nq: [sol, ...]}}  paths
  NL  NL-problems.npy        {key: {"G", "sol"}}               device coupling graphs
Reusing the same instance on every device is what makes results comparable, so new
instances are only added for sizes or devices that have none.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import numpy as np

from .layouts import NL_BANK_KEY, family

BANKS = {"FC": "WMC_FC.npy", "1D": "problems_1DChain.npy", "NL": "NL-problems.npy"}


def _load(path: Path) -> dict:
    return np.load(path, allow_pickle=True).item() if path.exists() else {}


def nl_key(backend: str, fam: str | None = None) -> str:
    fam = fam or family(backend)
    return NL_BANK_KEY.get(fam, fam)


def family_from_coupling(edges, data_dir: Path) -> str | None:
    """Family whose stored native-layout graph has exactly this coupling map, if any."""
    target = {frozenset(e) for e in edges}
    to_family = {v: k for k, v in NL_BANK_KEY.items()}
    for key, entry in _load(Path(data_dir) / BANKS["NL"]).items():
        if {frozenset(e) for e in entry["G"].edges()} == target:
            return to_family.get(key, key)
    return None


def load_problem(topology: str, data_dir: Path, nq: int | None = None,
                 backend: str | None = None, family: str | None = None) -> tuple[nx.Graph, str]:
    """(G, optimal bitstring) for an experiment, or KeyError with a hint."""
    bank = _load(Path(data_dir) / BANKS[topology])
    if topology == "FC":
        if nq not in bank:
            raise KeyError(f"No FC problem with {nq} nodes in {BANKS['FC']}. "
                           f"Create one: python -m lrqaoa new-problem FC --nq {nq}")
        return bank[nq]["G"], bank[nq]["sol"]
    if topology == "1D":
        if nq not in bank.get("G", {}):
            raise KeyError(f"No 1D problem with {nq} nodes in {BANKS['1D']}. "
                           f"Create one: python -m lrqaoa new-problem 1D --nq {nq}")
        sol = bank["sol"][nq]
        return bank["G"][nq], sol[0] if isinstance(sol, (list, tuple)) else sol
    key = nl_key(backend or "", family)
    if key not in bank:
        raise KeyError(f"No native-layout problem for '{key}' in {BANKS['NL']}. "
                       f"Create one from the device coupling map: python -m lrqaoa new-problem NL --backend {backend}")
    return bank[key]["G"], bank[key]["sol"]


# --------------------------------------------------------------------- new instances
def random_weights(edges, choices, rng) -> nx.Graph:
    G = nx.Graph()
    for i, j in edges:
        G.add_edge(int(i), int(j), weight=float(rng.choice(choices)))
    return G


def solve_maxcut(G: nx.Graph) -> str:
    """Optimal cut as a bitstring (character = node index). Paths are solved exactly;
    other graphs need docplex + cplex, as in the original problem generation."""
    nodes = sorted(G.nodes)
    if nx.is_tree(G) and all(G[i][j]["weight"] > 0 for i, j in G.edges):
        colour = nx.bipartite.color(G)  # cutting every edge of a tree is optimal
        return "".join(str(colour[i]) for i in nodes)
    from docplex.mp.model import Model

    mdl = Model("MaxCut")
    index = {node: k for k, node in enumerate(nodes)}
    x = {k: mdl.binary_var(name=f"x_{k}") for k in range(len(nodes))}
    mdl.minimize(-mdl.sum(G[i][j]["weight"] * (x[index[i]] * (1 - x[index[j]]) + x[index[j]] * (1 - x[index[i]]))
                          for i, j in G.edges))
    if mdl.solve() is None:
        raise RuntimeError("CPLEX found no solution")
    return "".join(str(round(mdl.solution.get_value(v))) for v in mdl.iter_binary_vars())


def new_problem(topology: str, data_dir: Path, nq: int | None = None, backend: str | None = None,
                edges: list | None = None, seed: int = 123, overwrite: bool = False) -> str:
    """Create, solve and store a new instance; returns a description."""
    path = Path(data_dir) / BANKS[topology]
    bank = _load(path)
    rng = np.random.default_rng(seed)
    if topology == "FC":
        if nq in bank and not overwrite:
            raise ValueError(f"FC {nq} already exists (use --overwrite to replace it)")
        G = random_weights([(i, j) for i in range(nq) for j in range(i + 1, nq)], [0.1, 0.2, 0.5, 2.0], rng)
        bank[nq] = {"G": G, "sol": solve_maxcut(G)}
        what = f"FC {nq} nodes"
    elif topology == "1D":
        bank.setdefault("G", {})
        bank.setdefault("sol", {})
        if nq in bank["G"] and not overwrite:
            raise ValueError(f"1D {nq} already exists (use --overwrite to replace it)")
        G = random_weights([(i, i + 1) for i in range(nq - 1)], [0.1, 0.2, 0.3, 0.5, 1.0], rng)
        sol = solve_maxcut(G)
        flip = "".join("1" if c == "0" else "0" for c in sol)
        bank["G"][nq], bank["sol"][nq] = G, [sol, flip]
        what = f"1D {nq} nodes"
    else:
        key = nl_key(backend)
        if key in bank and not overwrite:
            raise ValueError(f"NL '{key}' already exists (use --overwrite to replace it)")
        G = random_weights(sorted(tuple(sorted(e)) for e in {frozenset(e) for e in edges}),
                           [0.1, 0.2, 0.3, 0.5, 1.0], rng)
        G.add_nodes_from(range(max(G.nodes) + 1))
        bank[key] = {"G": G, "sol": solve_maxcut(G)}
        what = f"NL '{key}' ({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)"
    np.save(path, bank)
    return what
