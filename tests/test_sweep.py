"""Sweeps over problem sizes: one results file per size; on hardware, one job for the sweep."""

import shutil
from pathlib import Path

import numpy as np
import pytest

from lrqaoa import experiment
from lrqaoa.__main__ import main
from lrqaoa.backends import AerDevice

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def data(tmp_path):
    for bank in ("WMC_FC.npy", "problems_1DChain.npy", "NL-problems.npy"):
        shutil.copy(ROOT / "Data" / bank, tmp_path / bank)
    return tmp_path


def load(path):
    return np.load(path, allow_pickle=True).item()


def best_r(res, p):
    delta = res["Deltas"][0]
    return max(v["r"] for v in res["postprocessing"][delta][p].values())


def test_sweep_with_per_size_deltas(data, tmp_path):
    cfg = tmp_path / "sweep.toml"
    cfg.write_text(f'backend = "qasm_simulator"\ntopology = "FC"\nnq = [5, 7, 10]\nps = [3, 5]\n'
                   f'data_dir = "{data}"\n[deltas]\n"5" = [0.63]\n"7" = [0.5]\n')
    main(["run", str(cfg)])
    files = {n: load(data / "qasm_simulator" / f"{n}_FC.npy") for n in (5, 7, 10)}
    assert files[5]["Deltas"] == [0.63] and files[7]["Deltas"] == [0.5]
    assert files[10]["Deltas"] == [0.63]  # not listed: paper default for 10 nodes
    for n, res in files.items():
        assert res["status"] == "complete" and res["G"].number_of_nodes() == n
        assert res["meta"]["config"]["nq"] == n
        assert best_r(res, 5) > res["random"]["r"] + 0.1


def test_skip_existing(data):
    base = ["run", "--backend", "qasm_simulator", "--topology", "FC", "--ps", "2", "--data-dir", str(data)]
    main(base + ["--nq", "5", "6"])
    with pytest.raises(FileExistsError):
        main(base + ["--nq", "5", "6", "7"])
    assert not (data / "qasm_simulator" / "7_FC.npy").exists()  # nothing ran
    main(base + ["--nq", "5", "6", "7", "--skip-existing"])
    assert (data / "qasm_simulator" / "7_FC.npy").exists()


class QueuedDevice(AerDevice):
    """Behaves like hardware: submit returns a job id, results come later with fetch."""
    synchronous = False
    jobs: dict = {}
    fetches = 0

    def submit(self, executables, shots):
        QueuedDevice.jobs["job-1"] = (executables, shots)
        return {"job_id": "job-1"}

    def status(self, ref):
        return "DONE"

    def fetch(self, ref):
        QueuedDevice.fetches += 1
        execs, shots = QueuedDevice.jobs[ref["job_id"]]
        return AerDevice.run(self, execs, shots), {}


def test_hardware_sweep_is_one_job_split_per_file(data, monkeypatch):
    monkeypatch.setattr(experiment, "connect", lambda name, provider, frac: QueuedDevice(name, {"kind": "aer"}))
    experiment._FETCHED.clear()
    main(["run", "--backend", "qasm_simulator", "--topology", "FC", "--nq", "5", "8", "--ps", "2", "4",
          "--data-dir", str(data)])
    a, b = (load(data / "qasm_simulator" / f"{n}_FC.npy") for n in (5, 8))
    assert a["status"] == b["status"] == "submitted"
    assert a["job"]["job_id"] == b["job"]["job_id"] == "job-1"
    assert a["job"]["slice"] == [0, 2] and b["job"]["slice"] == [2, 4]

    main(["collect", "--all", "--data-dir", str(data)])
    assert QueuedDevice.fetches == 1  # downloaded once for both files
    a, b = (load(data / "qasm_simulator" / f"{n}_FC.npy") for n in (5, 8))
    for res, n in ((a, 5), (b, 8)):
        assert res["status"] == "complete"
        # each file got its own circuits: bitstrings have n characters per section
        assert all(len(k) == n * res["sections"] for k in res["samples"][0.63][2])
        assert best_r(res, 4) > res["random"]["r"] + 0.1
