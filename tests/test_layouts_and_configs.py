"""Stored qubit lines, ladders and native-layout problems must only use coupled qubit pairs,
and every example config must parse and point at an existing problem."""

from pathlib import Path

import pytest

from lrqaoa import experiment, layouts
from lrqaoa.backends import infer_provider

ROOT = Path(__file__).resolve().parent.parent


class FakeDevice:
    """Coupling map only: enough for experiment.build()."""
    def __init__(self, num_qubits, edges):
        self.num_qubits, self.edges = num_qubits, edges


def coupling(name):
    from qiskit_ibm_runtime.fake_provider import FakeProviderForBackendV2

    b = FakeProviderForBackendV2().backend(name)
    return FakeDevice(b.num_qubits, [tuple(e) for e in b.coupling_map.get_edges()])


def grid(rows, cols):
    edges = [(cols * r + c, cols * r + c + 1) for r in range(rows) for c in range(cols - 1)]
    edges += [(cols * r + c, cols * (r + 1) + c) for r in range(rows - 1) for c in range(cols)]
    return FakeDevice(rows * cols, edges)


def assert_coupled(items, device):
    allowed = {frozenset(e) for e in device.edges}
    for it in items:
        for inst in it["program"].circuit.data:
            if inst.operation.num_qubits == 2:
                pair = frozenset(it["program"].circuit.find_bit(q).index for q in inst.qubits)
                assert pair in allowed, f"gate {inst.operation.name} on uncoupled qubits {set(pair)}"


DEVICES = {"ibm_brisbane": "fake_brisbane", "ibm_torino": "fake_torino", "ibm_fez": "fake_fez"}


@pytest.mark.parametrize("backend", list(DEVICES))
@pytest.mark.parametrize("topology,nq", [("FC", 12), ("1D", 100), ("NL", None)])
def test_ibm_layouts_use_coupled_pairs(backend, topology, nq):
    device = coupling(DEVICES[backend])
    assert layouts.is_valid_line(layouts.known_line(backend), {frozenset(e) for e in device.edges})
    cfg = experiment.Config(backend=backend, topology=topology, nq=nq, ps=[2], data_dir=str(ROOT / "Data"))
    items, _ = experiment.build(cfg, device)
    assert_coupled(items, device)


@pytest.mark.parametrize("nq", [10, 17, 24])
def test_nighthawk_ladder_and_line(nq):
    device = grid(12, 10)
    for strategy in ("ladder", "swap_network"):
        cfg = experiment.Config(backend="ibm_phoenix", topology="FC", nq=nq, ps=[2], strategy=strategy,
                                data_dir=str(ROOT / "Data"))
        items, _ = experiment.build(cfg, device)
        assert_coupled(items, device)


@pytest.mark.parametrize("backend", list(DEVICES))
def test_find_line_on_unknown_device(backend):
    """Devices without a hand-made line get one found in their coupling map."""
    device = coupling(DEVICES[backend])
    line = layouts.find_line(device.edges)
    assert layouts.is_valid_line(line, {frozenset(e) for e in device.edges})
    assert len(line) >= 0.85 * len(layouts.known_line(backend))


@pytest.mark.parametrize("path", sorted((ROOT / "configs").glob("*.toml")), ids=lambda p: p.name)
def test_example_configs(path):
    from lrqaoa import problems

    cfg = experiment.load_config(str(path), data_dir=str(ROOT / "Data"))
    assert cfg.provider.get("kind") or infer_provider(cfg.backend)
    for nq in cfg.sizes:
        G, optimal = problems.load_problem(cfg.topology, ROOT / "Data", nq, cfg.backend)
        assert len(optimal) >= G.number_of_nodes()


def nighthawk_coupling():
    """The real Nighthawk coupling map, as stored in the native-layout bank."""
    import numpy as np

    bank = np.load(ROOT / "Data" / "NL-problems.npy", allow_pickle=True).item()
    return FakeDevice(120, [tuple(e) for e in bank["nighthawk-r1"]["G"].edges()])


@pytest.mark.parametrize("backend", ["ibm_chicago", "ibm_future_nighthawk"])
def test_nighthawk_devices_found_by_name_or_coupling_map(backend):
    device = nighthawk_coupling()
    nl = experiment.Config(backend=backend, topology="NL", ps=[2], data_dir=str(ROOT / "Data"))
    items, shared = experiment.build(nl, device)
    assert shared["family"] == "nighthawk-r1" and shared["n"] == 120
    fc = experiment.Config(backend=backend, topology="FC", nq=20, ps=[2], strategy="ladder",
                           data_dir=str(ROOT / "Data"))
    experiment.build(fc, device)  # ladder geometry comes with the family


def test_layout_that_does_not_fit_is_refused():
    device = nighthawk_coupling()
    device.edges = device.edges[1:]  # one coupler missing: not the stored Nighthawk device
    cfg = experiment.Config(backend="ibm_phoenix", topology="NL", ps=[2], data_dir=str(ROOT / "Data"))
    with pytest.raises(ValueError, match="does not fit the coupling map"):
        experiment.build(cfg, device)
