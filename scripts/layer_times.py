"""Time of one fully connected LR-QAOA layer vs problem size -> Data/layer_times.json.

The website's "Layer time" section reads this file (through scripts/build_site_data.py).
Run it by hand when calibrations or vendor numbers change; it needs the IBM Quantum account
for the live backends (the rest works offline):

    python scripts/layer_times.py                    # all series, live IBM calibrations
    python scripts/layer_times.py --offline          # skip the live IBM backends

Three kinds of numbers, each labelled on the site:
  computed  IBM: one SWAP-network layer compiled for the device along its longest 1D chain and
            scheduled with the calibrated gate durations; layer time = duration(p=2) - duration(p=1),
            so state preparation and readout cancel.
  estimate  Quantinuum Helios-1: (N-1) rounds of disjoint pairs (round robin), each like one
            "fully dense 2Q" layer of Fig. 4b in arXiv:2511.05465 (depth-1 time, which includes
            transport and cooling and Helios's batching through its 8 logic zones).
  estimate  IonQ, AQT: N(N-1)/2 two-qubit + N single-qubit gates applied one after another, with
            the gate durations each vendor publishes in its Amazon Braket device properties.
            Gate time only, so a lower bound.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "Data" / "layer_times.json"

HELIOS_URL = "https://arxiv.org/abs/2511.05465"
BRAKET_URL = "https://docs.aws.amazon.com/braket/latest/developerguide/braket-devices.html"

# Helios-1 depth-1 time (ms) for "fully dense 2Q" random programs: Fig. 4b of arXiv:2511.05465,
# read from the figure's published SVG (marker positions against the axis gridlines).
HELIOS_DEPTH1_MS = {16: 11.87, 20: 18.15, 24: 19.52, 28: 19.52, 32: 19.42, 36: 25.94, 40: 26.82,
                    44: 26.74, 48: 26.43, 52: 33.31, 56: 33.84, 60: 34.32, 64: 34.58, 68: 40.72,
                    72: 41.96, 76: 42.33, 80: 42.83, 84: 49.44, 88: 50.13, 92: 50.39, 96: 51.2,
                    98: 55.11}

# Trapped ions on Amazon Braket: (label, devices covered, qubits, 2Q gate µs, 1Q gate µs),
# from each device's published timing (properties.provider.timing / standardized durations).
BRAKET_IONS = [
    ("IonQ Aria", ["ionq_aria_2"], 25, 600, 135),
    ("IonQ Forte", ["ionq_forte"], 36, 970, 130),
    ("IonQ Forte Enterprise", ["ionq_forte_enterprise"], 36, 650, 63),
    ("AQT IBEX Q1", ["aqt_ibexq1"], 12, 335, 45),
]

SIZES = [5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130]


def ibm_layer_times(backend, name: str) -> tuple[list[list[float]], float, str]:
    """[(N, µs)] along the device's longest 1D chain, plus the median 2Q gate time (ns)."""
    import networkx as nx
    import numpy as np
    from qiskit import transpile
    from lrqaoa import circuits, layouts

    line = layouts.known_line(name)
    sizes = [n for n in SIZES if n <= len(line)] + ([len(line)] if len(line) not in SIZES else [])
    rng = np.random.default_rng(0)
    pts = []
    for n in sizes:
        G = nx.complete_graph(n)  # weights only set rotation angles, not the schedule
        for u, v in G.edges:
            G[u][v]["weight"] = float(rng.uniform(0, 1))
        t = []
        for p in (1, 2):
            prog = circuits.fc_swap_network(G, [0.3] * p, [0.2] * p, line, backend.num_qubits, max_sections=1)
            c = transpile(prog.circuit, backend, optimization_level=1, initial_layout=list(range(backend.num_qubits)))
            t.append(c.estimate_duration(backend.target, unit="s"))
        pts.append([n, round((t[1] - t[0]) * 1e6, 3)])
        print(f"  {name:14s} N={n:3d}  {pts[-1][1]:9.3f} µs", flush=True)
    two = "cz" if "cz" in backend.target.operation_names else "ecr"
    t2 = float(np.median([v.duration for v in backend.target[two].values() if v and v.duration])) * 1e9
    return pts, round(t2), two.upper()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="skip the live IBM backends")
    ap.add_argument("--account", default="mcm-primitives", help="saved QiskitRuntimeService account name")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    warnings.filterwarnings("ignore")

    from qiskit_ibm_runtime.fake_provider import FakeProviderForBackendV2
    from lrqaoa import layouts

    today = dt.date.today().isoformat()
    fake = FakeProviderForBackendV2()
    live = None
    if not args.offline:
        from qiskit_ibm_runtime import QiskitRuntimeService
        live = QiskitRuntimeService(name=args.account)

    def covers(family: str) -> list[str]:
        return sorted(k for k, v in layouts.FAMILY.items() if v == family)

    series = []
    # --- IBM: one series per processor generation; Heron r1-r3 as a band over three devices
    ibm = [("IBM Eagle", "eagle", ["ibm_brisbane"], "snapshot", covers("eagle-r3")),
           ("IBM Heron r1–r3", "heron", ["ibm_torino", "ibm_fez", "ibm_boston"], "mixed",
            covers("heron-r1") + covers("heron-r2")),
           ("IBM Nighthawk", "nighthawk", ["ibm_chicago"], "live", covers("nighthawk-r1"))]
    for label, key, names, _, cov in ibm:
        members = []
        for name in names:
            use_live = live is not None and name not in ("ibm_brisbane", "ibm_torino")
            be = live.backend(name) if use_live else fake.backend("fake_" + name[4:])
            src = f"live calibration, {today}" if use_live else "qiskit calibration snapshot"
            print(f"{label}: {name} ({src})", flush=True)
            pts, t2, gate = ibm_layer_times(be, name)
            members.append({"device": name, "source": src, "gate": gate, "t2q_ns": t2,
                            "chain": len(layouts.known_line(name)), "points": pts})
        s = {"key": key, "label": label, "provider": "IBM", "status": "computed", "covers": cov,
             "gate": members[0]["gate"], "t2q_ns": sorted({m["t2q_ns"] for m in members}),
             "method": "SWAP network along the device's longest 1D chain, compiled and scheduled "
                       "with calibrated gate durations",
             "source": "; ".join(f"{m['device']}: {m['source']}" for m in members), "short": "calibrations",
             "members": members}
        if len(members) == 1:
            s["points"] = members[0]["points"]
        else:  # band: min / max over the members at each size any of them reaches
            ns = sorted({n for m in members for n, _ in m["points"]})
            at = lambda m, n: next((t for k, t in m["points"] if k == n), None)  # noqa: E731
            lo, hi = [], []
            for n in ns:
                v = [t for m in members if (t := at(m, n)) is not None]
                if len(v) >= 2:
                    lo.append([n, min(v)]); hi.append([n, max(v)])
            s["lo"], s["hi"] = lo, hi
            s["points"] = [[n, round((a * b) ** 0.5, 3)] for (n, a), (_, b) in zip(lo, hi)]
        series.append(s)

    # --- Quantinuum Helios-1
    series.append({
        "key": "helios", "label": "Quantinuum Helios-1", "provider": "Quantinuum", "status": "estimate",
        "covers": ["quantinuum_helios_1"], "gate": "RZZ", "t2q_ns": [70000],
        "method": "(N−1) round-robin rounds × the measured depth-1 time of a fully dense random layer; "
                  "includes transport, cooling and batching through the 8 logic zones (⌈N/16⌉ batches per round)",
        "source": "Quantinuum Helios paper, arXiv:2511.05465, Fig. 4b (control-system simulator)",
        "url": HELIOS_URL, "short": "arXiv:2511.05465",
        "points": [[n, round((n - 1) * ms * 1e3, 1)] for n, ms in HELIOS_DEPTH1_MS.items()],
    })

    # --- Braket trapped ions
    for label, cov, qmax, t2, t1 in BRAKET_IONS:
        ns = sorted({n for n in SIZES if n <= qmax} | {qmax})
        series.append({
            "key": cov[0], "label": label, "provider": label.split()[0], "status": "estimate", "covers": cov,
            "gate": "MS", "t2q_ns": [t2 * 1000],
            "method": "N(N−1)/2 two-qubit and N single-qubit gates one after another; gate time only (lower bound)",
            "source": "vendor gate durations in the Amazon Braket device properties", "url": BRAKET_URL, "short": "Braket",
            "points": [[n, round(n * (n - 1) / 2 * t2 + n * t1, 1)] for n in ns],
        })

    out = {"updated": today, "series": series}
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
