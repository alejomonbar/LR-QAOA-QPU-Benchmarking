"""Scoring of sampled bitstrings: approximation ratio, random baseline, bit-flip mitigation.

Bitstring convention used everywhere in this package: character `sec * n + node` is the
value of `node` in parallel section `sec` (n = number of problem nodes).
The output dictionaries keep the format of the original notebooks, so old analysis
code and the website read new files unchanged.
"""

from __future__ import annotations

from collections import defaultdict

import networkx as nx
import numpy as np


def edge_arrays(G: nx.Graph) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    I, J, W = [], [], []
    for i, j in G.edges:
        I.append(i)
        J.append(j)
        W.append(G[i][j].get("weight", 1) if len(G[i][j]) else 1)
    return np.array(I, int), np.array(J, int), np.array(W, float)


def cut_values(bitstrings: list[str], G: nx.Graph, chunk: int = 2048) -> np.ndarray:
    """Weighted cut value of each bitstring (character `node` = side of `node`)."""
    I, J, W = edge_arrays(G)
    out = np.empty(len(bitstrings))
    for s in range(0, len(bitstrings), chunk):
        block = bitstrings[s:s + chunk]
        X = np.frombuffer("".join(block).encode(), dtype=np.uint8).reshape(len(block), -1)
        out[s:s + chunk] = ((X[:, I] != X[:, J]) * W).sum(axis=1)
    return out


def cost_maxcut(bitstring: str, weights: dict) -> float:
    """Cut value of one bitstring; `weights` maps (i, j) -> w. Kept for old notebooks."""
    return sum(w for (i, j), w in weights.items() if bitstring[i] != bitstring[j])


def objective_maxcut(samples: dict[str, int], G: nx.Graph, optimal: str) -> dict:
    """Approximation ratio of a sample set.

    Returns the same dictionary as the notebooks' `objective_MaxCut`:
    results ([cut, cut / max_cut, count] per distinct bitstring), G, weights,
    max_cut, r (mean approximation ratio) and probability (of an optimal cut).
    """
    weights = {(i, j): (G[i][j]["weight"] if len(G[i][j]) != 0 else 1) for i, j in G.edges}
    max_cut = float(cut_values([optimal], G)[0])
    strings = list(samples.keys())
    counts = np.array([samples[k] for k in strings], float)
    cuts = cut_values(strings, G)
    if (cuts > max_cut + 1e-6).any():
        print(f"There is a better cut than the stored optimum: {cuts.max() - max_cut}")
    shots = counts.sum()
    return {
        "results": np.column_stack([cuts, cuts / max_cut, counts]),
        "G": G,
        "weights": weights,
        "max_cut": max_cut,
        "r": float((cuts * counts).sum() / (shots * max_cut)),
        "probability": float(counts[np.abs(cuts - max_cut) < 1e-6].sum() / shots),
    }


def random_samples(num_samples: int, n_qubits: int, seed: int | None = None) -> dict[str, int]:
    """Uniformly random bitstrings, as counts."""
    rng = np.random.default_rng(seed)
    bits = rng.integers(0, 2, size=(num_samples, n_qubits), dtype=np.uint8) + 48
    out: dict[str, int] = defaultdict(int)
    for row in bits:
        out[row.tobytes().decode()] += 1
    return dict(out)


def mitigate(samples: dict[str, int], G: nx.Graph) -> dict[str, int]:
    """Greedy single-bit-flip local search on every sample (deterministic order)."""
    n = G.number_of_nodes()
    new: dict[str, int] = defaultdict(int)
    for bitstring, count in samples.items():
        best = bitstring
        best_cut = cut_values([best], G)[0]
        for q in range(n):
            flipped = best[:q] + ("1" if best[q] == "0" else "0") + best[q + 1:]
            c = cut_values([flipped], G)[0]
            if c > best_cut:
                best, best_cut = flipped, c
        new[best] += count
    return dict(new)


def split_sections(samples: dict[str, int], n: int, sections: int) -> list[dict[str, int]]:
    """Counts of each parallel section (characters sec*n .. (sec+1)*n)."""
    out = [defaultdict(int) for _ in range(sections)]
    for k, v in samples.items():
        for sec in range(sections):
            out[sec][k[sec * n:(sec + 1) * n]] += v
    return [dict(d) for d in out]


def postprocess(results: dict, random_shots: int = 10_000, mitigation: bool = False,
                seed: int | None = 1) -> dict:
    """Fill `postprocessing` (and `random`) of a results dictionary from its `samples`.

    postprocessing[delta][p][section] = objective_maxcut(...)
    """
    G = results["G"]
    n = G.number_of_nodes()
    optimal = results["optimal"]
    if isinstance(optimal, (list, tuple)):
        optimal = optimal[0]
    sections = int(results.get("sections", 1))

    post, post_mitig = {}, {}
    for delta, by_p in results["samples"].items():
        post[delta], post_mitig[delta] = {}, {}
        for p, counts in by_p.items():
            post[delta][p], post_mitig[delta][p] = {}, {}
            for sec, sec_counts in enumerate(split_sections(counts, n, sections)):
                post[delta][p][sec] = objective_maxcut(sec_counts, G, optimal)
                if mitigation:
                    post_mitig[delta][p][sec] = objective_maxcut(mitigate(sec_counts, G), G, optimal)
    results["postprocessing"] = post
    rand = random_samples(random_shots, n, seed)
    results["random"] = objective_maxcut(rand, G, optimal)
    if mitigation:
        results["postprocessing_mitig"] = post_mitig
        results["random_mitig"] = objective_maxcut(mitigate(rand, G), G, optimal)
    return results


def summary(results: dict) -> list[tuple]:
    """(delta, p, best r over sections, random r) rows, for printing."""
    rows = []
    rand = results.get("random", {}).get("r")
    for delta, by_p in results.get("postprocessing", {}).items():
        for p, secs in by_p.items():
            rs = [v["r"] for v in secs.values()] if "r" not in secs else [secs["r"]]
            rows.append((delta, p, max(rs), rand))
    return rows
