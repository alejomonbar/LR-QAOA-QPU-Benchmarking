"""Full runs through the command line on local simulators, into a temporary Data/ folder."""

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from lrqaoa.__main__ import main

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def data(tmp_path):
    for bank in ("WMC_FC.npy", "problems_1DChain.npy", "NL-problems.npy"):
        shutil.copy(ROOT / "Data" / bank, tmp_path / bank)
    shutil.copy(ROOT / "Data" / "registry.json", tmp_path / "registry.json")
    return tmp_path


def load(path):
    return np.load(path, allow_pickle=True).item()


def best_r(res, delta, p):
    return max(v["r"] for v in res["postprocessing"][delta][p].values())


def test_ideal_simulator_matches_stored_results(data):
    main(["run", "--backend", "qasm_simulator", "--topology", "FC", "--nq", "10", "--ps", "3", "5", "10",
          "--shots", "4000", "--data-dir", str(data)])
    new = load(data / "qasm_simulator" / "10_FC.npy")
    old = load(ROOT / "Data" / "qasm_simulator" / "10_FC.npy")
    assert new["status"] == "complete" and new["date"]
    for p in (3, 5, 10):
        assert abs(best_r(new, 0.63, p) - best_r(old, 0.63, p)) < 0.02
    assert best_r(new, 0.63, 10) > new["random"]["r"] + 0.1


def test_refuses_to_overwrite(data):
    args = ["run", "--backend", "qasm_simulator", "--topology", "FC", "--nq", "5", "--ps", "1",
            "--data-dir", str(data)]
    main(args)
    with pytest.raises(FileExistsError):
        main(args)
    main(args + ["--tag", "_repeat"])
    assert (data / "qasm_simulator" / "5_FC_repeat.npy").exists()


def test_fake_ibm_fc_swap_network_and_chain(data):
    main(["run", "--backend", "fake_fez", "--topology", "FC", "--nq", "6", "--ps", "2", "4",
          "--max-sections", "2", "--data-dir", str(data)])
    fc = load(data / "fake_fez" / "6_FC.npy")
    assert fc["sections"] == 2 and fc["meta"]["strategy"] == "swap_network"
    assert len(set(fc["total_qubits_used"])) == 12
    assert best_r(fc, 0.63, 2) > fc["random"]["r"]

    main(["run", "--backend", "fake_fez", "--topology", "1D", "--nq", "6", "--ps", "3", "6",
          "--max-sections", "2", "--data-dir", str(data)])
    ch = load(data / "fake_fez" / "6_1D.npy")
    assert ch["sections"] == 2 and ch["GT"].number_of_nodes() == 12
    assert best_r(ch, ch["Deltas"][0], 3) > ch["random"]["r"] + 0.05


def test_native_layout_new_problem(data):
    main(["new-problem", "NL", "--backend", "fake_manila", "--data-dir", str(data)])
    main(["run", "--backend", "fake_manila", "--topology", "NL", "--ps", "2", "4", "--data-dir", str(data)])
    nl = load(data / "fake_manila" / "5_NL.npy")
    assert nl["G"].number_of_nodes() == 5
    assert best_r(nl, 0.75, 2) > nl["random"]["r"]


def test_braket_local_matches_aer(data):
    pytest.importorskip("qiskit_braket_provider")
    common = ["--topology", "FC", "--nq", "6", "--ps", "3", "--shots", "4000", "--data-dir", str(data)]
    main(["run", "--backend", "qasm_simulator"] + common)
    main(["run", "--backend", "braket_local"] + common)
    a = best_r(load(data / "qasm_simulator" / "6_FC.npy"), 0.63, 3)
    b = best_r(load(data / "braket_local" / "6_FC.npy"), 0.63, 3)
    assert abs(a - b) < 0.02, (a, b)


def test_quantinuum_guppy_emulator_matches_aer(data, tmp_path):
    pytest.importorskip("guppylang")
    cfg = tmp_path / "helios.toml"
    cfg.write_text('backend = "quantinuum_helios_1"\ntopology = "FC"\nnq = 5\nps = [3]\nshots = 2000\n'
                   f'data_dir = "{data}"\n[provider]\nkind = "quantinuum"\nemulate = true\n')
    try:
        main(["run", str(cfg)])
    except Exception as err:  # the local emulator needs selene-sim
        pytest.skip(f"Guppy emulator unavailable: {err}")
    main(["run", "--backend", "qasm_simulator", "--topology", "FC", "--nq", "5", "--ps", "3",
          "--shots", "4000", "--data-dir", str(data)])
    a = best_r(load(data / "qasm_simulator" / "5_FC.npy"), 0.63, 3)
    b = best_r(load(data / "quantinuum_helios_1" / "5_FC.npy"), 0.63, 3)
    assert abs(a - b) < 0.03, (a, b)


def test_website_reads_new_files(data):
    main(["run", "--backend", "qasm_simulator", "--topology", "1D", "--nq", "8", "--ps", "2", "5",
          "--data-dir", str(data)])
    out = data / "results.json"
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_site_data.py"),
                           "--data-dir", str(data), "--out", str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    import json
    runs = json.loads(out.read_text())["runs"]
    run = next(r for r in runs if r["device"] == "qasm_simulator" and r["topology"] == "1D")
    assert run["p"] == [2, 5] and run["date_source"] == "file"
