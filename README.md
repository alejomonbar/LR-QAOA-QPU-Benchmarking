# Quantum Computing Benchmarking with LR-QAOA: Evaluating the performance of quantum process units at large width and depth
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

These experiments were conducted on **21 QPUs** from **6 vendors**:  
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

## 📑 **Table of Contents**
### **1D-Chain Experiments**
- [1D-Chain-Figures.ipynb](./1D-Chain-Figures.ipynb) - Visualizations and analysis for 1D-chain topology.
- [1D-Chain-IBM-Experiments.ipynb](./1D-Chain-IBM-Experiments.ipynb) - Experimental results of 1D-chain on IBM QPUs.

### **Fully Connected (FC) Experiments**
- [FC-Experiments.ipynb](./FC-Experiments.ipynb) - Experimental results for fully connected graphs.
- [FC-Figures.ipynb](./FC-Figures.ipynb) - Figures and visualizations for fully connected experiments.

### **Native Layout (NL) Experiments**
- [NL-Experiments.ipynb](./NL-Experiments.ipynb) - Experimental results for native layout graphs.
- [NL-Figures.ipynb](./NL-Figures.ipynb) - Visualizations and analysis for native layout graphs.

### **Random problems generator**
- [generate_problems.ipynb](./generate_problems.ipynb) - Generate the random graphs used for the FC, NL, and 1D-Chain experiments.
  
### **Dependencies**
- [requirements.txt](./requirements.txt) - Required Python libraries for running the notebooks.

---

## 🚀 **Getting Started**
1. **Clone the repository:**
   ```bash
   git clone https://github.com/alejomonbar/LR-QAOA-QPU-Benchmarking.git

