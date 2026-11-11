"""LR-QAOA QPU benchmark: build, run and score linear-ramp QAOA on any quantum processor.

    python -m lrqaoa run configs/ibm_fc.toml
    python -m lrqaoa collect --all

From Python:

    from lrqaoa import Config, run, collect
    run(Config(backend="qasm_simulator", topology="FC", nq=10, ps=[3, 5, 10]))
"""

from .experiment import Config, collect, load_config, run

__all__ = ["Config", "run", "collect", "load_config"]
