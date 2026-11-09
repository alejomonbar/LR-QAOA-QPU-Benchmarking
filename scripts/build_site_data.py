"""
Build the data file behind the static website (site/data/results.json).

Every result file that follows the naming convention

    Data/<backend>/<N>_<TOPOLOGY>.npy        TOPOLOGY in {FC, 1D, NL, HE}

is discovered automatically, so publishing a new result means: save the .npy
with that name, commit, push. Files with other names (fractional variants,
repeated runs, ...) are only published when listed under "extra_files" in
Data/registry.json. Device metadata (display name, vendor, modality) also
lives in that registry; unknown backends get a best-effort guess and a warning.

Usage:
    python scripts/build_site_data.py [--out site/data/results.json]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pickle
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Data"
CANONICAL = re.compile(r"^(\d+)_(FC|1D|NL|HE)\.npy$")
TOPOLOGY = {"FC": "FC", "1D": "1D", "NL": "NL", "HE": "NL"}  # HE = legacy name for native layout
SIGNIFICANCE = 1e-3  # one-sided p-value threshold used in the paper
N_BOOTSTRAP = 50

VENDOR_PREFIXES = {
    "ibm": "IBM", "ionq": "IonQ", "iqm": "IQM", "rigetti": "Rigetti",
    "aqt": "AQT", "quantinuum": "Quantinuum", "h1": "Quantinuum", "h2": "Quantinuum",
    "originq": "OriginQ",
}


# --------------------------------------------------------------------------- dates
def git_first_added_dates() -> dict[str, str]:
    """Map repo-relative path -> date the file first appeared in git history (YYYY-MM-DD)."""
    try:
        out = subprocess.check_output(
            ["git", "log", "--diff-filter=A", "--format=@%as", "--name-only", "--", "Data"],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    dates, current = {}, None
    for line in out.splitlines():
        if line.startswith("@"):
            current = line[1:]
        elif line.strip() and current:
            dates[line.strip()] = current  # log is newest-first, so the last write is the oldest add
    return dates


def file_date(path: Path, git_dates: dict[str, str], overrides: dict[str, str]) -> tuple[str, str]:
    rel = path.relative_to(ROOT).as_posix()
    if rel in overrides:
        return overrides[rel], "registry"
    if rel in git_dates:
        return git_dates[rel], "git"
    return dt.date.fromtimestamp(path.stat().st_mtime).isoformat(), "mtime"


# --------------------------------------------------------------------------- loading
class _Stub:
    """Stand-in for classes from SDKs that are not installed (pytket, qiskit, ...).
    Only plain numeric fields are needed here, so their contents are ignored."""
    def __init__(self, *args, **kwargs): pass
    def __setstate__(self, state): pass


class _TolerantUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except (ModuleNotFoundError, AttributeError):
            return type(name, (_Stub,), {"__module__": module})


def load_npy(path: Path) -> dict:
    """np.load(..., allow_pickle=True).item() that does not need every SDK installed."""
    try:
        return np.load(path, allow_pickle=True).item()
    except (ModuleNotFoundError, AttributeError):
        with open(path, "rb") as f:
            major, _ = np.lib.format.read_magic(f)
            reader = np.lib.format.read_array_header_1_0 if major == 1 else np.lib.format.read_array_header_2_0
            reader(f)
            return _TolerantUnpickler(f, encoding="latin1").load().item()


# --------------------------------------------------------------------------- analysis
def r_curve(post_delta: dict) -> tuple[list[int], list[float]]:
    """r(p) for one delta. Files with several sections (placements) keep the best section,
    as in the FC analysis of the paper."""
    ps = list(post_delta.keys())
    first = post_delta[ps[0]]
    if isinstance(first, dict) and "r" in first:
        return [int(p) for p in ps], [float(post_delta[p]["r"]) for p in ps]
    sections = sorted(k for k in first.keys() if isinstance(k, (int, np.integer)))
    best, best_curve = -np.inf, None
    for s in sections:
        curve = [float(post_delta[p][s]["r"]) for p in ps if s in post_delta[p]]
        if len(curve) == len(ps) and max(curve) > best:
            best, best_curve = max(curve), curve
    if best_curve is None:
        raise ValueError("no complete section in postprocessing")
    return [int(p) for p in ps], best_curve


def random_baseline(random: dict, shots: int) -> dict | None:
    """Mean and 3-sigma spread of the approximation ratio of `shots` uniformly random
    bitstrings, bootstrapped from the stored random samples (same method as the paper)."""
    if not isinstance(random, dict) or "results" not in random:
        return None
    res = np.asarray(random["results"])
    counts = res[:, 2].astype(int) if res.shape[1] > 2 else np.ones(len(res), int)
    pool = np.repeat(res[:, 1].astype(float), np.maximum(counts, 1))
    n = max(1, min(int(shots), len(pool)))
    rng = np.random.RandomState(1)
    means = []
    for _ in range(N_BOOTSTRAP):
        rng.shuffle(pool)
        means.append(pool[:n].mean())
    means = np.array(means)
    mean, std = float(means.mean()), float(means.std())
    return {"mean": mean, "std": std, "threshold": mean + 3 * std}


def shots_of(results: dict, delta, p) -> int:
    """Shots actually recorded (sum of sample counts), as in the paper; falls back to the
    nominal 'shots' entry."""
    try:
        return int(sum(results["samples"][delta][p].values()))
    except Exception:
        return int(results.get("shots") or 1000)


def edges_of(results: dict, nq: int, topology: str) -> int | None:
    G = results.get("G")
    if hasattr(G, "number_of_edges"):
        return int(G.number_of_edges())
    if topology == "FC":
        return nq * (nq - 1) // 2
    if topology == "1D":
        return nq - 1
    return None


def analyse(path: Path, nq: int, topology: str, delta_override=None, merge: list[Path] = ()) -> dict:
    results = load_npy(path)
    if "postprocessing" not in results:
        raise LookupError("no postprocessing yet")
    post = results["postprocessing"]
    delta = delta_override if delta_override is not None else list(post.keys())[0]
    ps, rs = r_curve(post[delta])
    for extra in merge:  # extra depths stored in separate files (e.g. a single p=10000 run)
        m_post = load_npy(extra)["postprocessing"]
        m_ps, m_rs = r_curve(m_post[delta if delta in m_post else list(m_post.keys())[0]])
        known = set(ps)
        ps += [p for p in m_ps if p not in known]
        rs += [r for p, r in zip(m_ps, m_rs) if p not in known]
    order = np.argsort(ps)
    ps, rs = [ps[i] for i in order], [rs[i] for i in order]
    shots = shots_of(results, delta, list(post[delta].keys())[0])
    base = random_baseline(results.get("random"), shots)
    edges = edges_of(results, nq, topology)

    i_best = int(np.argmax(rs))
    stored_date = str(results.get("date") or "")[:10]  # optional: notebooks can save results["date"]
    run = {
        "_stored_date": stored_date if re.match(r"^\d{4}-\d{2}-\d{2}$", stored_date) else None,
        "nq": nq, "topology": topology, "delta": float(delta), "shots": shots, "edges": edges,
        "p": ps, "r": [round(x, 6) for x in rs],
        "best": {"p": ps[i_best], "r": round(rs[i_best], 6)},
        "random": {k: round(v, 6) for k, v in base.items()} if base else None,
    }
    if base:
        above = [p for p, r in zip(ps, rs) if r > base["threshold"]]
        run["deepest_p_above_random"] = max(above) if above else None
        if base["std"] > 0:
            t = (rs[i_best] - base["mean"]) / base["std"]
            run["p_value"] = float(1 - stats.t.cdf(t, df=N_BOOTSTRAP - 1))
        else:
            run["p_value"] = 0.0 if rs[i_best] > base["mean"] else 1.0
        run["passes"] = bool(run["p_value"] < SIGNIFICANCE)
        thr = base["threshold"]
        run["r_eff"] = round((rs[i_best] - thr) / (1 - thr), 6) if thr < 1 else None
        d = run["deepest_p_above_random"]
        run["gates_at_deepest"] = d * edges if (d and edges) else None
    else:
        run.update(deepest_p_above_random=None, p_value=None, passes=None, r_eff=None, gates_at_deepest=None)
    return run


# --------------------------------------------------------------------------- devices
def guess_device(backend: str) -> dict:
    vendor = next((v for k, v in VENDOR_PREFIXES.items() if backend.lower().startswith(k)), "Other")
    name = backend.replace("_", " ").title()
    return {"name": name, "vendor": vendor, "modality": "unknown", "kind": "qpu"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "site" / "data" / "results.json"))
    args = ap.parse_args()

    registry = json.loads((DATA / "registry.json").read_text())
    devices_meta = registry.get("devices", {})
    skip_dirs = set(registry.get("skip_dirs", []))
    exclude = set(registry.get("exclude_files", []))
    date_overrides = registry.get("date_overrides", {})
    git_dates = git_first_added_dates()

    jobs = []  # (path, backend, nq, topology, variant, delta)
    for d in sorted(p for p in DATA.iterdir() if p.is_dir() and p.name not in skip_dirs):
        for f in sorted(d.glob("*.npy")):
            m = CANONICAL.match(f.name)
            if m and f"{d.name}/{f.name}" not in exclude:
                jobs.append((f, d.name, int(m.group(1)), TOPOLOGY[m.group(2)], None, None))
    merges: dict[Path, list[Path]] = {}
    for extra in registry.get("extra_files", []):
        f = DATA / extra["file"]
        if "merge_with" in extra:
            merges.setdefault(DATA / extra["merge_with"], []).append(f)
        elif f.exists():
            jobs.append((f, extra.get("device", f.parent.name), int(extra["nq"]), extra["topology"],
                         extra.get("variant"), extra.get("delta")))
        else:
            print(f"! registry extra not found: {extra['file']}", file=sys.stderr)

    runs, pending, devices, warned = [], [], {}, set()
    for f, backend, nq, topology, variant, delta in jobs:
        rel = f.relative_to(ROOT).as_posix()
        if backend not in devices_meta and backend not in warned:
            print(f"! {backend} is not in Data/registry.json; guessing its metadata", file=sys.stderr)
            warned.add(backend)
        devices[backend] = {**guess_device(backend), **devices_meta.get(backend, {})}
        try:
            run = analyse(f, nq, topology, delta, [m for m in merges.get(f, []) if m.exists()])
        except LookupError as e:
            pending.append({"device": backend, "file": rel, "reason": str(e)})
            print(f"  … {rel}: {e}")
            continue
        except Exception as e:  # keep the build going; report the file
            pending.append({"device": backend, "file": rel, "reason": f"{type(e).__name__}: {e}"})
            print(f"! {rel}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        date, date_source = file_date(f, git_dates, date_overrides)
        stored = run.pop("_stored_date")
        if stored and date_source != "registry":
            date, date_source = stored, "file"
        run.update(id=f"{backend}/{f.stem}", device=backend, variant=variant, file=rel,
                   date=date, date_source=date_source)
        runs.append(run)
        flag = {True: "pass", False: "fail", None: "n/a"}[run["passes"]]
        print(f"  ✓ {rel:52s} {topology:2s} N={nq:<4d} best r={run['best']['r']:.3f} @p={run['best']['p']:<5d} {flag}")

    used = {r["device"] for r in runs} | {p["device"] for p in pending}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = None
    out = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "commit": commit,
        "significance": SIGNIFICANCE,
        "devices": {k: v for k, v in sorted(devices.items()) if k in used},
        "runs": sorted(runs, key=lambda r: (r["topology"], r["device"], r["nq"], r["variant"] or "")),
        "pending": pending,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, separators=(",", ":")))
    print(f"\nWrote {args.out}: {len(runs)} runs on {len(out['devices'])} devices, {len(pending)} pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())
