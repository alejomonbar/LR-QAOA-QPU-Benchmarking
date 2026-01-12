"""
Generate JSON files with processed data for dashboard visualization
Extracts only essential information from .npy files for plotting
"""

import numpy as np
import json
from pathlib import Path
from collections import defaultdict
from scipy import stats

def process_fc_experiments():
    """Process Fully Connected experiments and save to JSON"""
    data_dir = Path("Data")
    
    # Backend configurations
    nqs = {
        "ibm_boston": [5,7,10,12,15,17,18,20,22,25,27,30,31,32,33,34,35],
        "ionq_forte": [10,13,15,17,20,21,23,25,27,30,35],
        "ibm_brisbane": [5,7,10,12,14,15,17,20],
        "ibm_fez": [5,7,10,12,15,17,18,20,22,25],
        "ibm_torino": [5,7,10,12,15,17,20,30,40],
        "ionq_harmony": [5,7,10],
        "iqm_garnet": [5,7,9,10,12,13,14,15],
        "H1-1E": [5,7,10,13,15,17,20],
        "H2-1E": [20,25,30],
        "qasm_simulator": [5,7,10,11,12,13,14,15,20,25],
        "ionq_aria_2": [5,10,13,15,17,20,23,25],
        "H2-1": [40, 50, 56],
        "ionq_forte_enterprise": [5,7,10,13,15,17,20,23,25,27,28,29,30],
        "ibm_marrakesh": [10,15,17,20],
        "iqm_emerald": [5,7,10,12,15],
        "aqt_ibexq1": [5,6,7,10,12]
    }
    
    backends = [
        "aqt_ibexq1", "ibm_brisbane", "ibm_fez", "ibm_boston",
        "H1-1E", "qasm_simulator", "H2-1E", "H2-1",
        "ionq_forte", "ionq_aria_2", "ionq_harmony", "ibm_torino",
        "ionq_forte_enterprise", "ibm_marrakesh", "iqm_garnet", "iqm_emerald"
    ]
    
    # Load HPC results
    try:
        res_hpc = np.load(data_dir / "LR_HPC_WMC_B.npy", allow_pickle=True).item()
    except:
        res_hpc = {}
    
    fc_results = {}
    case = ""
    
    for backend_name in backends:
        if backend_name not in nqs:
            continue
        
        fc_results[backend_name] = {}
        
        for nq in nqs[backend_name]:
            try:
                results = np.load(data_dir / backend_name / f"{nq}_FC.npy", allow_pickle=True).item()
                postprocessing = results["postprocessing" + case]
                postprocessing_random = results["random" + case]
                shots = sum(list(results["samples"][results["Deltas"][0]][results["ps"][0]].values()))
                
                # Process random data
                rand_data = []
                for v, c in zip(postprocessing_random["results"][:,1], postprocessing_random["results"][:,2]):
                    rand_data += int(c) * [v]
                rand_data = np.array(rand_data)
                
                # Random sampling analysis
                rand_mean = []
                np.random.seed(1)
                n_rand = 50
                for i in range(n_rand):
                    np.random.shuffle(rand_data)
                    rand_mean.append(np.mean(rand_data[:shots]))
                rand_mean = np.array(rand_mean)
                y1 = rand_mean.mean()
                y2 = 3 * rand_mean.std()
                
                # Calculate max approximation ratio
                deltas = results["Deltas"]
                ps = results["ps"]
                sections = results["sections"]
                r_max_nq = np.max([max([postprocessing[deltas[0]][p][i]["r"] for i in range(sections)]) for p in ps])
                p_eff = results["ps"][np.argmax([max([postprocessing[deltas[0]][p][i]["r"] for i in range(sections)]) for p in ps])]
                
                # Statistical test
                std = rand_mean.std()
                t_score = (r_max_nq - y1) / std
                p_value = float(1 - stats.t.cdf(t_score, df=n_rand-1))
                
                # Calculate effective approximation ratio
                r_eff = float((r_max_nq - (y1+y2))/(1-(y1+y2)))
                
                # Find best section across all p values
                best_yp = 0
                yp = []
                for i in range(sections):
                    ypi = [postprocessing[deltas[0]][p][i]["r"] for p in ps]
                    if np.max(ypi) > best_yp:
                        yp = ypi
                        best_yp = max(ypi)
                
                # Store essential data including r vs p curve
                fc_results[backend_name][str(nq)] = {
                    "r_eff": r_eff,
                    "r_max_qpu": float(r_max_nq),
                    "p_eff": int(p_eff),
                    "random_baseline": {
                        "mean": float(y1),
                        "std_3sigma": float(y2),
                        "threshold": float(y1 + y2)
                    },
                    "statistics": {
                        "t_score": float(t_score),
                        "p_value": p_value,
                        "significant": p_value < 0.001
                    },
                    "shots": int(shots),
                    "r_vs_p": {
                        "p_values": [int(p) for p in ps],
                        "r_values": [float(r) for r in yp]
                    }
                }
                
                print(f"✓ {backend_name} nq={nq}: r_eff={r_eff:.4f}, p-value={p_value:.6f}")
                
            except Exception as e:
                print(f"✗ {backend_name} nq={nq}: {str(e)}")
                continue
    
    # Add HPC results for qasm_simulator
    if res_hpc:
        if "qasm_simulator" not in fc_results:
            fc_results["qasm_simulator"] = {}
            
        for nq in [30, 40]:
            if nq in res_hpc:
                try:
                    results = np.load(data_dir / "ibm_torino" / f"{nq}_FC.npy", allow_pickle=True).item()
                    postprocessing_random = results["random"]
                    shots = sum(list(results["samples"][results["Deltas"][0]][results["ps"][0]].values()))
                    
                    rand_data = []
                    for v, c in zip(postprocessing_random["results"][:,1], postprocessing_random["results"][:,2]):
                        rand_data += int(c) * [v]
                    rand_data = np.array(rand_data)
                    
                    rand_mean = []
                    np.random.seed(1)
                    for i in range(50):
                        np.random.shuffle(rand_data)
                        rand_mean.append(np.mean(rand_data[:shots]))
                    rand_mean = np.array(rand_mean)
                    y1 = rand_mean.mean()
                    y2 = 3 * rand_mean.std()
                    
                    r_max_nq = res_hpc[nq][0]["objective"]["r"]
                    r_eff = float((r_max_nq - (y1+y2))/(1-(y1+y2)))
                    
                    fc_results["qasm_simulator"][str(nq)] = {
                        "r_eff": r_eff,
                        "r_max_qpu": float(r_max_nq),
                        "p_eff": None,
                        "random_baseline": {
                            "mean": float(y1),
                            "std_3sigma": float(y2),
                            "threshold": float(y1 + y2)
                        },
                        "statistics": {
                            "t_score": None,
                            "p_value": None,
                            "significant": True
                        },
                        "shots": int(shots),
                        "source": "HPC_simulation"
                    }
                    
                    print(f"✓ qasm_simulator nq={nq}: r_eff={r_eff:.4f} (HPC)")
                    
                except Exception as e:
                    print(f"✗ qasm_simulator nq={nq}: {str(e)}")
    
    # Save to JSON
    output_file = data_dir / "fc_processed.json"
    with open(output_file, 'w') as f:
        json.dump(fc_results, f, indent=2)
    
    print(f"\n✓ Saved FC results to {output_file}")
    
    # Generate summary
    summary = {
        "experiment_type": "fully_connected",
        "backends": list(fc_results.keys()),
        "total_datapoints": sum(len(data) for data in fc_results.values()),
        "description": "Effective approximation ratios for fully connected graphs with 3-sigma statistical filtering"
    }
    
    summary_file = data_dir / "fc_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"✓ Saved summary to {summary_file}")
    
    return fc_results


def process_1d_chain_experiments():
    """Process 1D Chain experiments and save to JSON"""
    data_dir = Path("Data")
    
    names = ["ibm_boston", "ibm_marrakesh", "ibm_fez", "ibm_torino", 
             "ibm_brisbane", "ibm_sherbrooke", "ibm_kyiv", "ibm_nazca", 
             "ibm_kyoto", "ibm_osaka", "ibm_brussels", "ibm_strasbourg"]
    
    nq = 100
    delta = 1
    case = ""
    kk = 0
    
    chain_results = {}
    
    for backend_name in names:
        try:
            results = np.load(data_dir / backend_name / f"{nq}_1D.npy", allow_pickle=True).item()
            postprocessing = results["postprocessing" + case]
            ps = list(postprocessing[delta].keys())
            rs = [float(postprocessing[delta][p][kk]["r"]) for p in ps]
            
            chain_results[backend_name] = {
                "qubits": nq,
                "p_values": ps,
                "r_values": rs,
                "max_r": float(max(rs)),
                "optimal_p": int(ps[rs.index(max(rs))])
            }
            
            # Get random baseline if available
            if backend_name == "ibm_brisbane" and "random" + case in results:
                res_random = results["random" + case]
                rand_data = res_random["results"][:,1]
                rand_mean = []
                np.random.seed(1)
                for i in range(10000):
                    np.random.shuffle(rand_data)
                    rand_mean.append(np.mean(rand_data[:1000]))
                rand_mean = np.array(rand_mean)
                y1 = rand_mean.mean()
                y2 = 3 * rand_mean.std()
                
                chain_results["random_baseline"] = {
                    "mean": float(y1),
                    "std_3sigma": float(y2),
                    "lower": float(y1 - y2),
                    "upper": float(y1 + y2)
                }
            
            print(f"✓ {backend_name}: max_r={max(rs):.4f} at p={ps[rs.index(max(rs))]}")
            
        except Exception as e:
            print(f"✗ {backend_name}: {str(e)}")
            continue
    
    # Add ibm_torino variants
    try:
        results_v1 = np.load(data_dir / "ibm_torino" / "100_1D_v1.npy", allow_pickle=True).item()
        postprocessing = results_v1["postprocessing" + case]
        ps = list(postprocessing[delta].keys())
        rs = [float(postprocessing[delta][p][kk]["r"]) for p in ps]
        
        chain_results["ibm_torino-v1"] = {
            "qubits": nq,
            "p_values": ps,
            "r_values": rs,
            "max_r": float(max(rs)),
            "optimal_p": int(ps[rs.index(max(rs))])
        }
        print(f"✓ ibm_torino-v1: max_r={max(rs):.4f}")
    except:
        pass
    
    if "ibm_torino" in chain_results:
        chain_results["ibm_torino-v0"] = chain_results.pop("ibm_torino")
    
    # Save to JSON
    output_file = data_dir / "1d_chain_processed.json"
    with open(output_file, 'w') as f:
        json.dump(chain_results, f, indent=2)
    
    print(f"\n✓ Saved 1D Chain results to {output_file}")
    
    return chain_results


def process_native_layout_experiments():
    """Process Native Layout experiments and save to JSON"""
    data_dir = Path("Data")
    
    case = ""
    prop = "r"
    delta = 1
    
    backend_files = {
        "ibm_brisbane": ("ibm_brisbane", "127_HE_day2.npy", delta, 1, 127),
        "ibm_torino-v0": ("ibm_torino", "133_HE.npy", delta, 1, 133),
        "ibm_torino-v1": ("ibm_torino", "133_HE_v1.npy", delta, 1, 133),
        "ibm_torino-f": ("ibm_torino", "133_HE_fractional.npy", 0.75, 0.75, 133),
        "ibm_fez": ("ibm_fez", "156_HE.npy", delta, 1, 156),
        "ibm_fez-f": ("ibm_fez", "156_HE_fractional.npy", 0.75, 0.75, 156),
        "ibm_marrakesh-f": ("ibm_marrakesh", "156_HE_fractional.npy", 0.75, 0.75, 156),
        "ibm_aachen-f": ("ibm_aachen", "156_HE_fractional.npy", 0.75, 0.75, 156),
        "ibm_kingston-f": ("ibm_kingston", "156_HE_fractional.npy", 0.75, 0.75, 156),
        "ibm_boston-f": ("ibm_boston", "156_HEw1.npy", 0.75, 0.75, 156),
        "iqm_garnet": ("iqm_garnet", "20_NL.npy", delta, 1, 20),
        "iqm_emerald": ("iqm_emerald", "54_HE.npy", 0.75, 0.75, 54),
        "rigetti_ankaa_3": ("rigetti_ankaa_3", "82_NL.npy", delta, 1, 82),
    }
    
    nl_results = {}
    
    for display_name, (folder, filename, delta_val, delta_key, qubits) in backend_files.items():
        try:
            results = np.load(data_dir / folder / filename, allow_pickle=True).item()
            postprocessing = results["postprocessing" + case]
            ps = list(results["ps"])
            
            # Handle different data structures
            if isinstance(postprocessing[delta_val][ps[0]], dict):
                if 0 in postprocessing[delta_val][ps[0]]:
                    rs = [float(postprocessing[delta_val][p][0][prop]) for p in ps]
                else:
                    rs = [float(postprocessing[delta_val][p][prop]) for p in ps]
            else:
                rs = [float(postprocessing[delta_val][p][prop]) for p in ps]
            
            nl_results[display_name] = {
                "qubits": qubits,
                "p_values": ps,
                "r_values": rs,
                "max_r": float(max(rs)),
                "optimal_p": int(ps[rs.index(max(rs))]),
                "has_random": "random" + case in results
            }
            
            if nl_results[display_name]["has_random"]:
                nl_results[display_name]["random_r"] = float(results["random" + case][prop])
            
            print(f"✓ {display_name}: max_r={max(rs):.4f} at p={ps[rs.index(max(rs))]}")
            
        except Exception as e:
            print(f"✗ {display_name}: {str(e)}")
            continue
    
    # Save to JSON
    output_file = data_dir / "native_layout_processed.json"
    with open(output_file, 'w') as f:
        json.dump(nl_results, f, indent=2)
    
    print(f"\n✓ Saved Native Layout results to {output_file}")
    
    return nl_results


if __name__ == "__main__":
    print("=" * 80)
    print("Processing Fully Connected Experiments")
    print("=" * 80)
    fc_results = process_fc_experiments()
    
    print("\n" + "=" * 80)
    print("Processing 1D Chain Experiments")
    print("=" * 80)
    chain_results = process_1d_chain_experiments()
    
    print("\n" + "=" * 80)
    print("Processing Native Layout Experiments")
    print("=" * 80)
    nl_results = process_native_layout_experiments()
    
    print("\n" + "=" * 80)
    print("✓ All data processed successfully!")
    print(f"  - FC: {sum(len(data) for data in fc_results.values())} datapoints across {len(fc_results)} backends")
    print(f"  - 1D Chain: {len(chain_results) - (1 if 'random_baseline' in chain_results else 0)} backends")
    print(f"  - Native Layout: {len(nl_results)} backends")
    print("=" * 80)
