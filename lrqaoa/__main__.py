"""Command line:  python -m lrqaoa <command> ...

  run CONFIG.toml [overrides]     build, submit and save Data/<backend>/<N>_<TOPO>.npy
  run --backend ibm_fez --topology FC --nq 20 --ps 3 4 5     (same, without a config file)
  run ... --nq 5 7 10 15 20       sweep over sizes: one job, one results file per size
  collect FILE [FILE ...]         fetch finished jobs and score them   (--all: every submitted file)
  status  [FILE ...]              job status of submitted files
  postprocess FILE [FILE ...]     recompute r and the random baseline from stored samples
  new-problem FC|1D|NL            add an instance to a problem bank (--nq, or --backend for NL)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from . import experiment, problems
from .backends import connect


def _run(a):
    overrides = dict(backend=a.backend, topology=a.topology, nq=a.nq, ps=a.ps, deltas=a.deltas,
                     shots=a.shots, tag=a.tag, strategy=a.strategy, max_sections=a.max_sections,
                     data_dir=a.data_dir)
    cfg = experiment.load_config(a.config, **overrides)
    experiment.run(cfg, dry_run=a.dry_run, force=a.force, skip_existing=a.skip_existing)


def _files(a):
    files = [Path(f) for f in a.files]
    if getattr(a, "all", False) or not files:
        files = experiment.pending_files(Path(a.data_dir))
        if not files:
            print("No submitted runs waiting to be collected.")
    return files


def _collect(a):
    waiting = [f for f in _files(a) if not experiment.collect(f, force=a.force)]
    if waiting:
        print(f"{len(waiting)} job(s) not finished yet.")


def _status(a):
    for f in _files(a):
        r = np.load(f, allow_pickle=True).item()
        if "job" not in r:
            print(f"{f}: {r.get('status', 'no job reference')}")
            continue
        cfg = experiment.Config(**r["meta"]["config"])
        device = connect(cfg.backend, cfg.provider, cfg.fractional_gates)
        print(f"{f}: {r.get('status')} · job {r['job'].get('job_id')} · {device.status(r['job'])}")


def _postprocess(a):
    for f in a.files:
        experiment.postprocess_file(Path(f), mitigation=a.mitigation)
        print(f"Updated {f}")


def _new_problem(a):
    edges = None
    if a.topology.upper() == "NL":
        if not a.backend:
            sys.exit("NL problems need --backend (its coupling map becomes the problem graph).")
        device = connect(a.backend, None)
        if device.edges is None:
            sys.exit(f"{a.backend} is all-to-all; a native-layout problem needs a coupling map.")
        edges = device.edges
    print("Added", problems.new_problem(a.topology.upper(), Path(a.data_dir), a.nq, a.backend, edges,
                                        seed=a.seed, overwrite=a.overwrite))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m lrqaoa", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="build, submit and save a benchmark run")
    r.add_argument("config", nargs="?", help="TOML file (see configs/)")
    r.add_argument("--backend")
    r.add_argument("--topology", choices=["FC", "1D", "NL", "fc", "1d", "nl"])
    r.add_argument("--nq", type=int, nargs="+", help="problem size(s); several sizes run as one sweep")
    r.add_argument("--ps", type=int, nargs="+")
    r.add_argument("--deltas", type=float, nargs="+")
    r.add_argument("--shots", type=int)
    r.add_argument("--tag")
    r.add_argument("--strategy", choices=list(experiment.STRATEGIES))
    r.add_argument("--max-sections", type=int)
    r.add_argument("--data-dir")
    r.add_argument("--dry-run", action="store_true", help="build and compile only, print gate counts")
    r.add_argument("--force", action="store_true", help="overwrite existing results files")
    r.add_argument("--skip-existing", action="store_true", help="in a sweep, only run sizes not measured yet")
    r.set_defaults(func=_run)

    for name, func, helptext in [("collect", _collect, "fetch and score submitted jobs"),
                                 ("status", _status, "job status of submitted runs")]:
        c = sub.add_parser(name, help=helptext)
        c.add_argument("files", nargs="*")
        c.add_argument("--all", action="store_true", help="every submitted run in --data-dir")
        c.add_argument("--data-dir", default="Data")
        c.add_argument("--force", action="store_true", help="re-fetch even if already complete")
        c.set_defaults(func=func)

    pp = sub.add_parser("postprocess", help="recompute scores from stored samples")
    pp.add_argument("files", nargs="+")
    pp.add_argument("--mitigation", action="store_true")
    pp.set_defaults(func=_postprocess)

    npb = sub.add_parser("new-problem", help="add an instance to a problem bank")
    npb.add_argument("topology", choices=["FC", "1D", "NL", "fc", "1d", "nl"])
    npb.add_argument("--nq", type=int)
    npb.add_argument("--backend")
    npb.add_argument("--seed", type=int, default=123)
    npb.add_argument("--overwrite", action="store_true")
    npb.add_argument("--data-dir", default="Data")
    npb.set_defaults(func=_new_problem)

    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
