"""Where the problem goes on each device: qubit lines, ladders and processor families.

Known lines are copied from the experiment notebooks. For any other device a line is
searched in its coupling map (`find_line`), so new devices work without editing this file.
"""

from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------- qubit lines
_EAGLE = (list(range(13, -1, -1)) + [14] + list(range(18, 33)) + [36] + list(range(51, 36, -1)) + [52]
          + list(range(56, 71)) + [74] + list(range(89, 74, -1)) + [90] + list(range(94, 109)) + [112]
          + list(range(126, 112, -1)))
_HERON_R1 = (list(range(14, -1, -1)) + [15] + list(range(19, 34)) + [37] + list(range(52, 37, -1)) + [53]
             + list(range(57, 72)) + [75] + list(range(90, 75, -1)) + [91] + list(range(95, 110)) + [113]
             + list(range(128, 113, -1)) + [129])
_HERON_R2 = (list(range(0, 16)) + [19] + list(range(35, 20, -1)) + [36] + list(range(41, 56)) + [59]
             + list(range(75, 60, -1)) + [76] + list(range(81, 96)) + [99] + list(range(115, 100, -1)) + [116]
             + list(range(121, 136)) + [139] + list(range(155, 139, -1)))
_NIGHTHAWK = [q for r in range(12) for q in (range(10 * r, 10 * r + 10) if r % 2 == 0
                                               else reversed(range(10 * r, 10 * r + 10)))]
_ANKAA_2 = [i + j * 7 for i in range(7) for j in (reversed(range(12)) if i % 2 == 0 else range(12))]
_CEPHEUS_LABELS = (list(reversed(range(0, 8))) + list(range(9, 18)) + list(reversed(range(18, 27)))
                   + list(range(27, 36)) + list(reversed(range(36, 45))) + list(range(45, 54))
                   + list(reversed(range(54, 63))) + list(range(63, 72)) + list(reversed(range(72, 81)))
                   + list(range(81, 90)) + list(reversed(range(90, 99))) + list(range(99, 107)))

FAMILY = {
    **{b: "eagle-r3" for b in ["ibm_brisbane", "ibm_kyiv", "ibm_kyoto", "ibm_osaka", "ibm_nazca",
                               "ibm_sherbrooke", "ibm_brussels", "ibm_strasbourg"]},
    "ibm_torino": "heron-r1",
    **{b: "heron-r2" for b in ["ibm_fez", "ibm_marrakesh", "ibm_aachen", "ibm_kingston",
                               "ibm_boston", "ibm_pittsburgh"]},
    # Nighthawk: 12 x 10 square lattice, 218 couplers (ibm_chicago checked against ibm_phoenix)
    **{b: "nighthawk-r1" for b in ["ibm_miami", "ibm_phoenix", "ibm_chicago"]},
}

LINES = {
    "eagle-r3": _EAGLE,
    "heron-r1": _HERON_R1,
    "heron-r2": _HERON_R2,
    "nighthawk-r1": _NIGHTHAWK,
    "iqm_garnet": [2, 3, 0, 1, 4, 5, 6, 11, 10, 9, 8, 7, 12, 13, 14, 15, 19, 18, 17],
    "iqm_emerald": [q - 1 for q in [1, 2, 6, 12, 13, 14, 22, 30, 31, 39, 38, 46, 45, 51, 50, 54, 53, 52, 48,
                                    42, 43, 35, 36, 37, 29, 21, 20, 28, 27, 19, 11, 5, 4, 10, 18, 26, 34, 33,
                                    32, 24, 23, 15, 16, 17, 9, 3]],
    "iqm_sirius": list(range(16)),
    "rigetti_ankaa_2": _ANKAA_2,
    # Cepheus labels skip 8; index = label for label < 8, label - 1 above
    "rigetti_cepheus_1_108q": [q if q < 8 else q - 1 for q in _CEPHEUS_LABELS],
}

# Square-lattice devices (n_rows, n_cols), qubit = n_cols * row + col: used by the FC ladder
GRID_SHAPES = {"nighthawk-r1": (12, 10)}

# Native-layout problem bank keys (Data/NL-problems.npy)
NL_BANK_KEY = {"eagle-r3": "Eagle-r3", "heron-r1": "Heron-r1", "heron-r2": "Heron-r2",
               "nighthawk-r1": "nighthawk-r1"}


def family(backend: str) -> str:
    if backend.startswith("fake_"):  # qiskit fake backends share the real device's layout
        backend = "ibm_" + backend[5:]
    return FAMILY.get(backend, backend)


def known_line(backend: str) -> list[int] | None:
    return LINES.get(family(backend))


def is_valid_line(line: list[int], edges: set[frozenset] | None) -> bool:
    if edges is None:
        return True
    return all(frozenset((a, b)) in edges for a, b in zip(line, line[1:]))


def find_line(edges: list[tuple[int, int]], length: int | None = None, tries: int = 3000,
              seed: int = 0) -> list[int]:
    """Long simple path in a coupling graph (Warnsdorff-style greedy walk, best of `tries`).

    Stops early once `length` qubits are reached.
    """
    adj: dict[int, set[int]] = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    rng = np.random.default_rng(seed)
    nodes = sorted(adj)
    starts = sorted(nodes, key=lambda q: len(adj[q]))  # low-degree qubits (corners, ends) first

    def walk(path: list[int], seen: set[int]) -> None:
        while not (length and len(path) >= length):
            options = [q for q in adj[path[-1]] if q not in seen]
            if not options:
                return
            onward = {q: len([x for x in adj[q] if x not in seen]) for q in options}
            # Warnsdorff: fewest onward exits first, but avoid dead ends while there is a way on
            pool = [q for q in options if onward[q] > 0] or options
            pool.sort(key=lambda q: (onward[q], rng.random()))
            pick = pool[1] if len(pool) > 1 and rng.random() < 0.25 else pool[0]
            path.append(pick)
            seen.add(pick)

    best: list[int] = []
    for t in range(tries):
        start = starts[t] if t < len(starts) else nodes[rng.integers(len(nodes))]
        path, seen = [start], {start}
        walk(path, seen)
        path.reverse()  # then grow the other end
        walk(path, seen)
        if len(path) > len(best):
            best = path
            if length and len(best) >= length:
                return best[:length]
    return best


# --------------------------------------------------------------------- ladders (FC on square lattices)
def ladder_shape(num_nodes: int) -> tuple[int, int]:
    """(m, n_dummy): a 2 x m ladder holds the problem; odd sizes leave one idle position."""
    m = (num_nodes + 1) // 2
    return m, 2 * m - num_nodes


def ladder_qubits(m: int, n_rows: int, n_cols: int) -> list[list[int]]:
    """All disjoint 2 x m ladders on a square lattice, each ordered row0 + row1."""
    vertical = []
    if m <= n_rows:
        for c in range(0, n_cols - 1, 2):
            for r0 in range(0, n_rows - m + 1, m):
                vertical.append([n_cols * (r0 + k) + c for k in range(m)]
                                + [n_cols * (r0 + k) + c + 1 for k in range(m)])
    horizontal = []
    if m <= n_cols:
        for r in range(0, n_rows - 1, 2):
            for c0 in range(0, n_cols - m + 1, m):
                horizontal.append([n_cols * r + c0 + k for k in range(m)]
                                  + [n_cols * (r + 1) + c0 + k for k in range(m)])
    return horizontal if len(horizontal) > len(vertical) else vertical
