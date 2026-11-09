# Quantum Computing Benchmarking with LR-QAOA: Evaluating the performance of quantum processing units at large width and depth
Paper:https://arxiv.org/abs/2502.06471

## Overview
Currently, we are in a stage where quantum computers surpass the size that can be simulated exactly on classical computers, and noise is the central issue in extracting their full potential. Effective ways to characterize and measure their progress for practical applications are needed.

In this work, we use the **Linear Ramp Quantum Approximate Optimization Algorithm (LR-QAOA)** [[1]](https://arxiv.org/abs/2405.09169) protocol, a fixed **Quantum Approximate Optimization Algorithm (QAOA)** protocol, as an easy-to-implement, scalable benchmarking methodology. This approach assesses **Quantum Processing Units (QPUs)** at different **widths (number of qubits)** and **2-qubit gate depths**. 
![Description](paper-layouts-tested.png)

Scheme of the Quantum Processing Units (QPUs) benchmarking. (a) Graphs used for the benchmarking. In yellow is the 1D-Chain, in green is the native layout (NL), and in pink is the fully connected (FC) graph. (b) QAOA protocol consists of alternating layers of the problem Hamiltonian and the mixer Hamiltonian. $p$ represents the depth of the algorithm. (c) Schedule of the LR-QAOA algorithm, $\Delta_{\gamma, \beta}/p$ is the slope. (d) Expected results of LR-QAOA in terms of approximation ratio versus number of LR-QAOA layers. Black curves represent different levels of depolarizing noise strength.

The benchmarking identifies the depth at which a **fully mixed state** is reached, meaning results become indistinguishable from those of a random sampler.

### **Tested Systems & Vendors**
We evaluate this methodology using **three graph topologies**:
- **1D-chain**
- **Native Layout (NL)**
- **Fully Connected (FC)**  

These experiments were conducted on **28 QPUs** from **7 vendors**:  
✅ AQT  
✅ IBM  
✅ IQM  
✅ IonQ  
✅ Quantinuum  
✅ Rigetti  
✅ OriginQ 


### **Key Findings**
- The largest problem tested: **1D-chain with \( p = 10,000 \)** involving **990,000 2-qubit gates on `ibm_fez`**.
- **`ibm_fez` performs best** for **1D-chain & native layout**, retaining coherence at **\( p=200 \)** with **35,200 fractional 2-qubit gates**.
- **`quantinuum_H2-1` performs best** for **fully connected graphs**, successfully passing the test at **\( N_q=56 \) qubits, \( p=3 \) (4,620 2-qubit gates)**.

---

## 🌐 **Website**

Live results: **https://alejomonbar.github.io/LR-QAOA-QPU-Benchmarking/** (static site in [`site/`](./site), published by [GitHub Actions](./.github/workflows/site.yml)).

**Publishing a new result** takes no code changes:

1. Save the run as `Data/<backend>/<N>_<FC|1D|NL>.npy` (the usual dict with `postprocessing`, `random`, `ps`, `Deltas`, …).
2. If the backend is new, add a line for it under `devices` in [`Data/registry.json`](./Data/registry.json) (name, vendor, modality). Without it, the build guesses the metadata and prints a warning.
3. Commit and push to `main`. The workflow runs [`scripts/build_site_data.py`](./scripts/build_site_data.py), which finds every result file, computes the random baseline, pass/fail and gate counts, and redeploys the page. A result's date is `results["date"]` (`"YYYY-MM-DD"`) if the file stores one, otherwise the date the file was first committed.

Files with other names (variants, repeated runs) are only published when listed under `extra_files` in the registry. To preview locally:

```bash
python scripts/build_site_data.py && python -m http.server -d site 8000   # open http://localhost:8000
```

---

## 📂 **Repository Structure**

```
LR-QAOA-QPU-Benchmarking/
├── 1D-Chain-Experiments.ipynb   # Experimental results for 1D-chain topology
├── 1D-Chain-Figures.ipynb       # Visualizations and analysis for 1D-chain topology
├── 1D-Chain-Origin-Quantum.ipynb # 1D-chain experiments on Origin Quantum QPU
├── FC-Experiments.ipynb         # Experimental results for fully connected graphs
├── FC-Figures.ipynb             # Figures and visualizations for FC experiments
├── NL-Experiments.ipynb         # Experimental results for native layout graphs
├── NL-Figures.ipynb             # Visualizations and analysis for native layout graphs
├── Figures_sampling.ipynb       # Sampling-related figures and analysis
├── generate_problems.ipynb      # Generate random graphs for FC, NL, and 1D-Chain experiments
├── LR-QAOA-Benchmark.md         # Detailed benchmark protocol documentation
├── paper-layouts-tested.png     # Diagram of QPU benchmarking layouts
├── requirements.txt             # Required Python libraries
├── LICENSE                      # License file
├── README.md                    # This file
├── Data/                        # Experimental data and results
│   ├── problems_1DChain.json    # 1D-Chain problem definitions
│   ├── NL-problems.npy          # Native layout problem definitions
│   ├── WMC_FC.npy               # Fully connected problem data
│   ├── qpu_benchmark_results.xlsx # Benchmark results summary
│   ├── ibm_fez/                 # IBM QPU experiment data (also: ibm_torino, ibm_brisbane, etc.)
│   ├── iqm_garnet/              # IQM QPU experiment data (also: iqm_spark, iqm_sirius, etc.)
│   ├── ionq_aria_2/             # IonQ QPU experiment data (also: ionq_forte, etc.)
│   ├── rigetti_ankaa_2/         # Rigetti QPU experiment data (also: rigetti_ankaa_3)
│   ├── H1-1/                    # Quantinuum H1-1 experiment data (also: H2-1, H1-1E, H2-1E)
│   ├── aqt_ibexq1/              # AQT QPU experiment data
│   └── originq_wukong/          # OriginQ QPU experiment data
└── Figures/                     # Generated figures and plots
    ├── 1D-Chain/                # 1D-chain topology figures
    ├── FC/                      # Fully connected graph figures
    ├── NL/                      # Native layout figures
    └── sampling/                # Sampling analysis figures
```

---

## 📑 **Table of Contents**
### **1D-Chain Experiments**
- [1D-Chain-Experiments.ipynb](./1D-Chain-Experiments.ipynb) - Experimental results for 1D-chain topology.
- [1D-Chain-Figures.ipynb](./1D-Chain-Figures.ipynb) - Visualizations and analysis for 1D-chain topology.
- [1D-Chain-Origin-Quantum.ipynb](./1D-Chain-Origin-Quantum.ipynb) - 1D-chain experiments on Origin Quantum QPU.

### **Fully Connected (FC) Experiments**
- [FC-Experiments.ipynb](./FC-Experiments.ipynb) - Experimental results for fully connected graphs.
- [FC-Figures.ipynb](./FC-Figures.ipynb) - Figures and visualizations for fully connected experiments.

### **Native Layout (NL) Experiments**
- [NL-Experiments.ipynb](./NL-Experiments.ipynb) - Experimental results for native layout graphs.
- [NL-Figures.ipynb](./NL-Figures.ipynb) - Visualizations and analysis for native layout graphs.

### **Additional Notebooks**
- [generate_problems.ipynb](./generate_problems.ipynb) - Generate the random graphs used for the FC, NL, and 1D-Chain experiments.
- [Figures_sampling.ipynb](./Figures_sampling.ipynb) - Sampling-related figures and analysis.
  
### **Dependencies**
- [requirements.txt](./requirements.txt) - Required Python libraries for running the notebooks.

---

## 🚀 **Getting Started**
1. **Clone the repository:**
   ```bash
   git clone https://github.com/alejomonbar/LR-QAOA-QPU-Benchmarking.git

