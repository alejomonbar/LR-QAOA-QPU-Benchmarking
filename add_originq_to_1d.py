#!/usr/bin/env python3
"""
Script to add originq_wukong backend to 1D chain processed data for dashboard
"""
import json
import numpy as np
from pathlib import Path

# Load existing processed data
data_dir = Path("Data")
processed_file = data_dir / "1d_chain_processed.json"

with open(processed_file, 'r') as f:
    processed_data = json.load(f)

# Load originq_wukong data for 5 qubits
nq = 5
case = ""
prop = "r"

print("Loading originq_wukong data...")
results = np.load(f"./Data/originq_wukong/{nq}_1D_2.npy", allow_pickle=True).item()

# Process the data
delta = results["Deltas"][0]
ps = results["ps"]
best_mean = 0
best_sec = None

# Find the best section based on highest mean value
for sec_i in results[f"postprocessing{case}"][delta][ps[0]].keys():
    res_i = [results[f"postprocessing{case}"][delta][p][sec_i][prop] for p in ps]
    
    if np.mean(res_i) > best_mean:
        best_sec = res_i
        best_mean = np.mean(res_i)

# Get random baseline if available
random_r = None
if f"random{case}" in results:
    rand_data = []
    for v, c in zip(results[f"random{case}"]["results"][:, 1], 
                    results[f"random{case}"]["results"][:, 2]):
        rand_data += int(c) * [v]
    
    rand_mean = []
    for i in range(100):
        np.random.shuffle(rand_data)
        rand_mean.append(np.mean(rand_data[:1000]))
    
    random_r = float(np.mean(rand_mean))

# Create entry for originq_wukong
originq_entry = {
    "qubits": nq,
    "p_values": [int(p) for p in ps],
    "r_values": [float(r) for r in best_sec],
    "max_r": float(max(best_sec)),
    "optimal_p": int(ps[np.argmax(best_sec)])
}

if random_r is not None:
    originq_entry["random_r"] = random_r

# Add to processed data
processed_data["originq_wukong"] = originq_entry

print(f"originq_wukong processed:")
print(f"  Qubits: {originq_entry['qubits']}")
print(f"  Max r: {originq_entry['max_r']:.3f}")
print(f"  Optimal p: {originq_entry['optimal_p']}")
print(f"  P values range: {min(ps)} - {max(ps)}")

# Save updated data
with open(processed_file, 'w') as f:
    json.dump(processed_data, f, indent=2)

print(f"\nUpdated {processed_file}")
print(f"Total backends in 1D chain: {len(processed_data)}")
