"""Run a benchmark: build the circuits, submit them, collect and score the results.

A run writes Data/<backend>/<N>_<FC|1D|NL><tag>.npy right after submission (status
"submitted", with the job reference); `collect` later fills in samples and postprocessing.
The file keeps the layout of the notebook-era files, plus "date", "status" and "meta".
"""

from __future__ import annotations

import datetime as dt
import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

import numpy as np

from . import analysis, circuits, layouts, problems
from .backends import connect
from .schedule import default_delta, linear_ramp

TOPOLOGIES = ("FC", "1D", "NL")
STRATEGIES = ("swap_network", "ladder", "all_to_all")


@dataclass
class Config:
    backend: str                         # name used for Data/<backend>/ and on the website
    topology: str                        # FC | 1D | NL
    ps: list[int]                        # numbers of LR-QAOA layers
    nq: int | list[int] | None = None    # problem size(s) (FC, 1D); a list runs a sweep, one file per size.
                                         # NL uses the whole device graph
    deltas: list[float] | dict | None = None  # ramp slopes for every size, or per size {"5": [0.63], "20": [0.3]};
                                              # missing -> paper default (schedule.default_delta)
    shots: int = 1000
    tag: str = ""                        # file-name suffix; "" = canonical file the website lists
    strategy: str | None = None          # FC: swap_network | ladder | all_to_all (default from device)
    two_qubit: str | None = None         # rzz | cx (default: rzz with fractional gates / all-to-all)
    fractional_gates: bool = True        # IBM: request the fractional-gate (RZZ) target
    max_sections: int | None = None      # cap on parallel copies of the problem
    line: list[int] | None = None        # override the qubit line (FC swap network, 1D)
    optimization_level: int = 1
    random_shots: int = 10_000
    mitigation: bool = False
    seed: int = 1
    data_dir: str = "Data"
    provider: dict = field(default_factory=dict)  # kind + options, see backends.py

    def __post_init__(self):
        self.topology = {"HE": "NL"}.get(self.topology.upper(), self.topology.upper())
        if self.topology not in TOPOLOGIES:
            raise ValueError(f"topology must be one of {TOPOLOGIES}")
        if self.topology != "NL" and not self.nq:
            raise ValueError("nq is required for FC and 1D")
        if self.strategy and self.strategy not in STRATEGIES:
            raise ValueError(f"strategy must be one of {STRATEGIES}")
        self.ps = [int(p) for p in self.ps]
        if isinstance(self.nq, (list, tuple)):
            self.nq = [int(n) for n in self.nq]
            if len(self.nq) == 1:
                self.nq = self.nq[0]

    @property
    def sizes(self) -> list[int | None]:
        return list(self.nq) if isinstance(self.nq, list) else [self.nq]

    def for_size(self, nq: int | None) -> "Config":
        """The single-size config of one member of a sweep (what its results file records)."""
        deltas = self.deltas
        if isinstance(deltas, dict):
            deltas = deltas.get(str(nq), deltas.get(nq))
        return replace(self, nq=nq, deltas=deltas)


def load_config(path: str | None = None, **overrides) -> Config:
    data = tomllib.loads(Path(path).read_text()) if path else {}
    data.update({k: v for k, v in overrides.items() if v is not None})
    known = {f.name for f in fields(Config)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"Unknown config keys: {sorted(unknown)}")
    return Config(**data)


def output_path(cfg: Config, nq: int) -> Path:
    return Path(cfg.data_dir) / cfg.backend / f"{nq}_{cfg.topology}{cfg.tag}.npy"


# --------------------------------------------------------------------- building
def _line(cfg: Config, device, n_needed: int) -> list[int]:
    if cfg.line:
        return list(cfg.line)
    if device.edges is None:  # simulator / all-to-all
        return list(range(n_needed))
    edge_set = {frozenset(e) for e in device.edges}
    known = layouts.known_line(cfg.backend)
    if known and layouts.is_valid_line(known, edge_set):
        return known
    found = layouts.find_line(device.edges)
    print(f"Using a line of {len(found)} qubits found in the coupling map of {cfg.backend}.")
    return found


def build(cfg: Config, device) -> tuple[list[dict], dict]:
    """Circuits for every (delta, p), plus problem data shared by all of them."""
    G, optimal = problems.load_problem(cfg.topology, Path(cfg.data_dir), cfg.nq, cfg.backend)
    n = G.number_of_nodes()
    deltas = cfg.deltas or [default_delta(cfg.topology, n, cfg.fractional_gates and cfg.topology == "1D")]
    simulator = device.edges is None and device.num_qubits is None
    width = device.num_qubits or n
    two_qubit = cfg.two_qubit or ("rzz" if (cfg.fractional_gates or device.edges is None) else "cx")
    max_sections = cfg.max_sections or (1 if simulator else None)

    strategy, line, ladders = cfg.strategy, None, None
    if cfg.topology == "FC":
        strategy = strategy or ("all_to_all" if device.edges is None else "swap_network")
        if strategy == "ladder":
            fam = layouts.family(cfg.backend)
            if fam not in layouts.GRID_SHAPES:
                raise ValueError(f"The ladder needs a square-lattice device; {cfg.backend} is not one.")
            rows, cols = layouts.GRID_SHAPES[fam]
            m, _ = layouts.ladder_shape(n)
            if m > max(rows, cols):
                raise ValueError(f"A ladder on a {rows}x{cols} lattice holds at most {2 * max(rows, cols)} nodes.")
            ladders = layouts.ladder_qubits(m, rows, cols)
        elif strategy == "swap_network":
            line = _line(cfg, device, n)
            if len(line) < n:
                raise ValueError(f"The qubit line has {len(line)} qubits, fewer than the {n} nodes.")
    elif cfg.topology == "1D":
        line = _line(cfg, device, n)
        if len(line) < n:
            raise ValueError(f"The qubit line has {len(line)} qubits, fewer than the {n} nodes.")
    elif device.num_qubits and max(G.nodes) >= device.num_qubits:
        raise ValueError("The native-layout problem has more nodes than the device has qubits.")

    items = []
    for delta in deltas:
        for p in cfg.ps:
            betas, gammas = linear_ramp(p, delta, decimals=4 if cfg.topology == "NL" else None)
            if cfg.topology == "FC" and strategy == "all_to_all":
                prog = circuits.fc_all_to_all(G, betas, gammas)
            elif cfg.topology == "FC" and strategy == "ladder":
                prog = circuits.fc_ladder(G, betas, gammas, ladders, width, max_sections)
            elif cfg.topology == "FC":
                prog = circuits.fc_swap_network(G, betas, gammas, line, width, max_sections)
            elif cfg.topology == "1D":
                prog = circuits.chain(G, betas, gammas, line, width, two_qubit, max_sections)
            else:
                prog = circuits.native_layout(G, betas, gammas, two_qubit, width=width)
            items.append({"delta": delta, "p": p, "program": prog, "betas": betas, "gammas": gammas})

    shared = {"G": G, "optimal": optimal, "n": n, "deltas": deltas, "strategy": strategy,
              "two_qubit": two_qubit, "line": line, "ladders": ladders}
    return items, shared


def _gate_stats(executable) -> dict:
    try:
        ops = dict(executable.count_ops())
    except AttributeError:
        return {}
    two_q = sum(ops.get(g, 0) for g in ("cx", "cz", "ecr", "rzz", "rxx", "ryy", "ms", "zz", "iswap", "swap"))
    return {"depth": executable.depth(), "two_qubit_gates": two_q, "ops": ops}


# --------------------------------------------------------------------- run / collect
def run(cfg: Config, dry_run: bool = False, force: bool = False, skip_existing: bool = False) -> list[Path]:
    """Run one size, or a sweep over sizes (cfg.nq a list): one results file per size, and on
    hardware a single job for the whole sweep (one queue wait)."""
    device = connect(cfg.backend, cfg.provider, cfg.fractional_gates)

    plans, existing = [], []
    for nq in cfg.sizes:
        c = cfg.for_size(nq)
        items, shared = build(c, device)
        path = output_path(c, shared["n"])
        if path.exists() and not dry_run and not force:
            if skip_existing:
                print(f"Skipping {path} (exists)")
            else:
                existing.append(path)
            continue
        plans.append((c, items, shared, path))
    if existing:
        raise FileExistsError("Already measured: " + ", ".join(map(str, existing))
                              + ". Use --skip-existing to run only the missing sizes, another tag, or --force.")
    if not plans:
        print("Nothing to run.")
        return []

    compiled = []
    for c, items, shared, path in plans:
        print(f"{c.backend} · {c.topology} · {shared['n']} nodes · {items[0]['program'].sections} section(s)"
              + (f" · strategy {shared['strategy']}" if shared["strategy"] else ""))
        execs = device.prepare(items, c.optimization_level)
        stats = [_gate_stats(e) for e in execs]
        for it, st in zip(items, stats):
            print(f"  delta={it['delta']:<5} p={it['p']:<6} depth={st.get('depth', '-'):<8} "
                  f"2q gates={st.get('two_qubit_gates', '-')}")
        compiled.append((execs, stats))
    if dry_run:
        print("Dry run: nothing submitted.")
        return []

    now = dt.datetime.now(dt.timezone.utc)
    sweep = [p.stem for *_, p in plans] if len(plans) > 1 else None
    outputs = [_new_results(c, items, shared, stats, device, now, sweep)
               for (c, items, shared, _), (_, stats) in zip(plans, compiled)]
    paths = [path for *_, path in plans]
    paths[0].parent.mkdir(parents=True, exist_ok=True)

    if device.synchronous:
        for (c, items, _, path), (execs, _), results in zip(plans, compiled, outputs):
            _store_samples(results, items, device.run(execs, c.shots))
            print(f"{path}:")
            _finish(results, c)
    else:
        all_execs = [e for execs, _ in compiled for e in execs]
        ref = device.submit(all_execs, cfg.shots)
        start = 0
        for (execs, _), results in zip(compiled, outputs):
            job = dict(ref)
            if len(plans) > 1:  # this file's share of the sweep job
                job["slice"] = [start, start + len(execs)]
            start += len(execs)
            results["job"], results["id"] = job, ref.get("job_id")
        print(f"Submitted job {ref.get('job_id')} ({len(all_execs)} circuits, {len(plans)} file(s)). "
              "Collect it later with: python -m lrqaoa collect --all")
    for path, results in zip(paths, outputs):
        np.save(path, results)
        print(f"Saved {path}")
    return paths


def _new_results(cfg: Config, items, shared, stats, device, now, sweep) -> dict:
    prog0, n = items[0]["program"], shared["n"]
    results = {
        "Deltas": shared["deltas"], "ps": list(cfg.ps), "G": shared["G"], "optimal": shared["optimal"],
        "nq": n, "sections": prog0.sections, "shots": cfg.shots, "total_qubits_used": prog0.qubits,
        "date": now.date().isoformat(), "status": "submitted",
        "meta": {
            "config": asdict(cfg), "device": device.describe(), "strategy": shared["strategy"],
            "two_qubit": shared["two_qubit"], "line": shared["line"], "ladders": shared["ladders"],
            "submitted_at": now.isoformat(timespec="seconds"), "sweep": sweep,
            "circuits": [{"delta": it["delta"], "p": it["p"], **st} for it, st in zip(items, stats)],
            "versions": _versions(),
        },
    }
    if cfg.topology == "1D" and shared["line"]:
        results["GT"] = circuits.repeat_subgraph(shared["G"], shared["line"][:prog0.sections * n])
    return results


def _store_samples(results: dict, items: list[dict], counts: list[dict]):
    if len(counts) != len(items):
        raise RuntimeError(f"Expected {len(items)} result sets, got {len(counts)}")
    samples: dict = {}
    for it, c in zip(items, counts):
        samples.setdefault(it["delta"], {})[it["p"]] = c
    results["samples"] = samples


def _finish(results: dict, cfg: Config):
    analysis.postprocess(results, random_shots=cfg.random_shots, mitigation=cfg.mitigation, seed=cfg.seed)
    results["status"] = "complete"
    results.setdefault("meta", {})["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for delta, p, r, rand in analysis.summary(results):
        print(f"  delta={delta:<5} p={p:<6} r={r:.4f}   random r={rand:.4f}")


def _items_of(results: dict) -> list[dict]:
    return [{"delta": d, "p": p} for d in results["Deltas"] for p in results["ps"]]


_FETCHED: dict = {}  # job_id -> (counts, runtime): a sweep job is downloaded once for all its files


def _fetch(device, job: dict) -> tuple[list[dict], dict]:
    key = job.get("job_id")
    if key not in _FETCHED:
        _FETCHED[key] = device.fetch(job)
    counts, runtime = _FETCHED[key]
    if "slice" in job:
        a, b = job["slice"]
        counts = counts[a:b]
    return counts, runtime


def collect(path: Path, force: bool = False) -> bool:
    """Fetch a submitted job and score it. Returns False if the job is not finished."""
    results = np.load(path, allow_pickle=True).item()
    if results.get("status") == "complete" and not force:
        print(f"{path}: already complete")
        return True
    if "job" not in results:
        raise ValueError(f"{path} has no job reference (made by an older notebook?)")
    cfg = Config(**results["meta"]["config"])
    device = connect(cfg.backend, cfg.provider, cfg.fractional_gates)
    status = device.status(results["job"])
    if any(s in status.upper() for s in ("QUEUED", "RUNNING", "INITIALIZING", "VALIDATING", "SUBMITTED")):
        print(f"{path}: job {results['job'].get('job_id')} is {status}")
        return False
    counts, runtime = _fetch(device, results["job"])
    _store_samples(results, _items_of(results), counts)
    results["runtime"] = runtime
    print(f"{path}:")
    _finish(results, cfg)
    np.save(path, results)
    return True


def postprocess_file(path: Path, random_shots: int = 10_000, mitigation: bool = False):
    results = np.load(path, allow_pickle=True).item()
    analysis.postprocess(results, random_shots=random_shots, mitigation=mitigation)
    results["status"] = "complete"
    np.save(path, results)


def pending_files(data_dir: Path) -> list[Path]:
    out = []
    for f in sorted(Path(data_dir).glob("*/*.npy")):
        try:
            r = np.load(f, allow_pickle=True).item()
        except Exception:
            continue
        if isinstance(r, dict) and r.get("status") == "submitted":
            out.append(f)
    return out


def _versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version

    out = {}
    for pkg in ("qiskit", "qiskit-aer", "qiskit-ibm-runtime", "qiskit-braket-provider", "amazon-braket-sdk",
                "qiskit-iqm", "qnexus", "guppylang", "numpy", "networkx"):
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            pass
    return out
