"""One adapter per way of reaching a device. Each SDK is imported only when used.

Interface:
  prepare(items)        -> executables (compiled circuits / programs), one per item
  submit(execs, shots)  -> job reference (plain dict, saved in the results file)
  fetch(ref)            -> (counts per executable, runtime metadata)
  run(execs, shots)     -> counts per executable (local simulators, `synchronous = True`)
Counts are returned with character c = classical bit c (see analysis.py).
"""

from __future__ import annotations

import os
from collections import Counter

from qiskit import transpile

# Braket device names for the backend names used in Data/
BRAKET_DEVICES = {
    "iqm_garnet": "Garnet", "iqm_emerald": "Emerald",
    "ionq_aria_1": "Aria 1", "ionq_aria_2": "Aria 2", "ionq_forte": "Forte 1",
    "ionq_forte_enterprise": "Forte Enterprise 1",
    "rigetti_ankaa_3": "Ankaa-3", "rigetti_cepheus_1_108q": "Cepheus-1-108Q",
    "aqt_ibexq1": "IBEX Q1",
}
NEXUS_SYSTEMS = {"quantinuum_helios_1": "Helios-1", "quantinuum_helios_1e": "Helios-1E"}


def clbit_order(counts: dict) -> dict[str, int]:
    """qiskit counts (clbit 0 rightmost, maybe space-separated) -> character c = clbit c."""
    return {k.replace(" ", "")[::-1]: int(v) for k, v in counts.items()}


def infer_provider(backend: str) -> dict:
    if backend in ("qasm_simulator", "qiskit_mps") or backend.startswith("fake_"):
        return {"kind": "aer"}
    if backend == "braket_local":
        return {"kind": "braket", "local": True}
    if backend.startswith("ibm_"):
        return {"kind": "ibm"}
    if backend in NEXUS_SYSTEMS:
        return {"kind": "quantinuum", "system": NEXUS_SYSTEMS[backend]}
    if backend in BRAKET_DEVICES:
        return {"kind": "braket", "device": BRAKET_DEVICES[backend]}
    raise ValueError(f"Don't know how to reach '{backend}'. Add a [provider] table to the config "
                     "(kind = ibm | braket | iqm | quantinuum | aer).")


def connect(backend: str, provider: dict | None = None, fractional_gates: bool = True):
    provider = {**infer_provider(backend), **(provider or {})} if not (provider or {}).get("kind") else provider
    kind = provider["kind"]
    if kind == "aer":
        return AerDevice(backend, provider)
    if kind == "ibm":
        return IBMDevice(backend, provider, fractional_gates)
    if kind == "braket":
        return BraketDevice(backend, provider)
    if kind == "iqm":
        return IQMDevice(backend, provider)
    if kind == "quantinuum":
        return NexusDevice(backend, provider)
    raise ValueError(f"Unknown provider kind '{kind}'")


class Device:
    kind = "base"
    synchronous = False
    all_to_all = False

    def __init__(self, name: str, provider: dict):
        self.name, self.provider = name, provider
        self.num_qubits: int | None = None
        self.edges: list[tuple[int, int]] | None = None  # None = all-to-all
        self.target = None  # what qiskit transpiles against

    # -- compilation
    def prepare(self, items: list[dict], optimization_level: int = 1) -> list:
        circs = [it["program"].circuit for it in items]
        if self.target is None:
            return circs
        layout = list(range(circs[0].num_qubits)) if self.edges else None
        return transpile(circs, backend=self.target, optimization_level=optimization_level,
                         initial_layout=layout)

    def describe(self) -> dict:
        return {"provider": self.kind, "num_qubits": self.num_qubits, "all_to_all": self.edges is None}

    def submit(self, executables, shots: int) -> dict:
        raise NotImplementedError

    def fetch(self, ref: dict) -> tuple[list[dict], dict]:
        raise NotImplementedError

    def run(self, executables, shots: int) -> list[dict]:
        raise NotImplementedError

    def status(self, ref: dict) -> str:
        return "unknown"


# --------------------------------------------------------------------- local simulators
class AerDevice(Device):
    """qasm_simulator, qiskit_mps (bond dimension: provider.bond_dimension) or fake_<ibm device>
    (noisy simulation with the fake backend's noise model and coupling map)."""
    kind, synchronous = "aer", True

    def __init__(self, name, provider):
        super().__init__(name, provider)
        from qiskit_aer import AerSimulator

        if name.startswith("fake_"):
            from qiskit_ibm_runtime.fake_provider import FakeProviderForBackendV2

            fake = FakeProviderForBackendV2().backend(name)
            self.sim = AerSimulator.from_backend(fake)
            self.num_qubits = fake.num_qubits
            self.edges = [tuple(e) for e in fake.coupling_map.get_edges()]
        elif name == "qiskit_mps":
            self.sim = AerSimulator(method="matrix_product_state",
                                    matrix_product_state_max_bond_dimension=provider.get("bond_dimension", 20))
        else:
            self.sim = AerSimulator()
        self.target = self.sim

    def run(self, executables, shots):
        result = self.sim.run(executables, shots=shots, seed_simulator=self.provider.get("seed")).result()
        if not result.success:
            errors = {r.status for r in result.results if not r.success}
            raise RuntimeError(f"Simulation failed: {'; '.join(errors) or result.status}. "
                               "Too many active qubits? Lower --max-sections or nq, or use qiskit_mps.")
        counts = result.get_counts()
        return [clbit_order(c) for c in (counts if isinstance(counts, list) else [counts])]


# --------------------------------------------------------------------- IBM Quantum
class IBMDevice(Device):
    """provider options: service (saved account name), channel, instance."""
    kind = "ibm"

    def __init__(self, name, provider, fractional_gates=True):
        super().__init__(name, provider)
        self.service = self._service()
        self.backend = self.service.backend(name, use_fractional_gates=fractional_gates)
        self.target = self.backend
        self.num_qubits = self.backend.num_qubits
        self.edges = [tuple(e) for e in self.backend.coupling_map.get_edges()]

    def _service(self):
        from qiskit_ibm_runtime import QiskitRuntimeService

        kw = {k: self.provider[k] for k in ("channel", "instance") if k in self.provider}
        if "service" in self.provider:
            kw["name"] = self.provider["service"]
        return QiskitRuntimeService(**kw)

    def submit(self, executables, shots):
        from qiskit_ibm_runtime import SamplerV2

        job = SamplerV2(mode=self.backend).run(executables, shots=shots)
        return {"job_id": job.job_id()}

    def status(self, ref):
        return str(self.service.job(ref["job_id"]).status())

    def fetch(self, ref):
        job = self.service.job(ref["job_id"])
        result = job.result()
        counts = [clbit_order(pub.data.c.get_counts()) for pub in result]
        runtime = {}
        try:
            runtime["usage_seconds"] = job.usage()
            runtime["timestamps"] = {k: str(v) for k, v in job.metrics().get("timestamps", {}).items()}
        except Exception:
            pass
        return counts, runtime


# --------------------------------------------------------------------- qiskit-style providers
class _QiskitProviderDevice(Device):
    """Shared by Braket (qiskit-braket-provider) and IQM Resonance (qiskit-iqm)."""

    def _from_backend(self, backend):
        self.backend = self.target = backend
        self.num_qubits = getattr(backend, "num_qubits", None)
        cmap = getattr(backend, "coupling_map", None)
        edges = [tuple(e) for e in cmap.get_edges()] if cmap is not None and len(cmap.get_edges()) else None
        # a fully connected coupling map means all-to-all (IonQ, AQT)
        if edges and self.num_qubits and len({frozenset(e) for e in edges}) >= self.num_qubits * (self.num_qubits - 1) // 2:
            edges = None
        self.edges = edges

    def submit(self, executables, shots):
        job = self.backend.run(executables, shots=shots, **self.provider.get("run_options", {}))
        return {"job_id": job.job_id()}

    def fetch(self, ref):
        result = self.backend.retrieve_job(ref["job_id"]).result()
        counts = result.get_counts()
        counts = counts if isinstance(counts, list) else [counts]
        return [clbit_order(c) for c in counts], {}


class BraketDevice(_QiskitProviderDevice):
    """provider options: device (Braket name, e.g. "Forte 1"), run_options, local = true for the
    local state-vector simulator (testing)."""
    kind = "braket"

    def __init__(self, name, provider):
        super().__init__(name, provider)
        if provider.get("local"):
            from qiskit_braket_provider import BraketLocalBackend

            self.synchronous = True
            self._from_backend(BraketLocalBackend())
            self.edges = None
        else:
            from qiskit_braket_provider import BraketProvider

            self._from_backend(BraketProvider().get_backend(provider.get("device", BRAKET_DEVICES.get(name))))

    def run(self, executables, shots):
        counts = self.backend.run(executables, shots=shots).result().get_counts()
        return [clbit_order(c) for c in (counts if isinstance(counts, list) else [counts])]

    def status(self, ref):
        return str(self.backend.retrieve_job(ref["job_id"]).status())


class IQMDevice(_QiskitProviderDevice):
    """IQM Resonance. provider options: url (e.g. https://cocos.resonance.meetiqm.com/emerald),
    token_env (environment variable holding the API token, default RESONANCE_API_TOKEN)."""
    kind = "iqm"

    def __init__(self, name, provider):
        super().__init__(name, provider)
        from iqm.qiskit_iqm import IQMProvider

        token = os.environ.get(provider.get("token_env", "RESONANCE_API_TOKEN"))
        self._from_backend(IQMProvider(provider["url"], token=token).get_backend())


# --------------------------------------------------------------------- Quantinuum (Nexus + Guppy)
class NexusDevice(Device):
    """Quantinuum Helios through Nexus, with Guppy programs (all-to-all, FC only).
    provider options: system ("Helios-1"), project (Nexus project), max_cost (HQC cap),
    emulate = true to run locally on the Guppy emulator instead (testing, small n)."""
    kind = "quantinuum"

    def __init__(self, name, provider):
        super().__init__(name, provider)
        self.edges = None
        self.synchronous = bool(provider.get("emulate"))

    @staticmethod
    def guppy_program(n: int, schedule, betas, gammas):
        """Same circuit as circuits.fc_all_to_all, in Guppy. Angles are in half-turns."""
        import numpy as np
        from guppylang import guppy
        from guppylang.std.angles import angle
        from guppylang.std.builtins import array, comptime, result
        from guppylang.std.quantum import h, measure_array, qubit, rx
        from guppylang.std.qsystem import zz_phase

        pairs = [(int(u), int(v)) for u, v, _ in schedule]
        weights = [float(w) / float(np.pi) for _, _, w in schedule]
        g, b, layers = [float(x) for x in gammas], [float(x) for x in betas], len(gammas)

        @guppy
        def main() -> None:
            qs = array(qubit() for _ in range(comptime(n)))
            for i in range(len(qs)):
                h(qs[i])
            for layer in range(comptime(layers)):
                k = 0
                for i, j in comptime(pairs):
                    zz_phase(qs[i], qs[j], angle(2.0 * comptime(g)[layer] * comptime(weights)[k]))
                    k += 1
                for i in range(len(qs)):
                    rx(qs[i], angle(-2.0 * comptime(b)[layer] / comptime(float(np.pi))))
            result("c", measure_array(qs))

        return main

    def prepare(self, items, optimization_level=1):
        execs = []
        for it in items:
            prog = it["program"]
            if not prog.schedule:
                raise ValueError("Quantinuum runs use the all-to-all FC builder (strategy = 'all_to_all').")
            n = len(prog.qubits)
            execs.append((n, self.guppy_program(n, prog.schedule, it["betas"], it["gammas"])))
        return execs

    def run(self, executables, shots):  # local emulator
        out = []
        for n, prog in executables:
            res = prog.emulator(n_qubits=n).with_shots(shots).run()
            out.append(dict(Counter("".join(str(int(b)) for b in entry[1])
                                    for shot in res for entry in shot)))
        return out

    def submit(self, executables, shots):
        import uuid

        import qnexus as qnx

        project = qnx.projects.get_or_create(self.provider.get("project", "LR-QAOA"))
        qnx.context.set_active_project(project)
        tag = uuid.uuid4().hex[:8]
        refs = [qnx.hugr.upload(prog.compile(), name=f"lrqaoa-{self.name}-{n}q-{k}-{tag}")
                for k, (n, prog) in enumerate(executables)]
        config = qnx.models.HeliosConfig(system_name=self.provider.get("system", "Helios-1"),
                                         max_cost=self.provider.get("max_cost"))
        job = qnx.start_execute_job(programs=refs, n_shots=[shots] * len(refs), backend_config=config,
                                    name=f"lrqaoa-{self.name}-{tag}")
        return {"job_id": str(job.id), "project": project.annotations.name}

    def fetch(self, ref):
        import qnexus as qnx

        job = qnx.jobs.get(id=ref["job_id"])
        qnx.jobs.wait_for(job)
        counts = []
        for item in qnx.jobs.results(job):
            shots = item.download_result()
            counts.append(dict(Counter("".join(str(int(b)) for b in s.to_register_bits()["c"]) for s in shots)))
        return counts, {}

    def status(self, ref):
        import qnexus as qnx

        return str(qnx.jobs.status(qnx.jobs.get(id=ref["job_id"])).status)
