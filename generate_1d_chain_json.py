"""
Generate 1D chain processed JSON data from numpy files for dashboard
"""
import json
import numpy as np
from pathlib import Path

def generate_1d_chain_json():
    """Extract real data from numpy files and create JSON for dashboard"""
    
    data = {"5q": {}, "100q": {}}
    nq = 5
    case = ""
    prop = "r"
    
    # ========== 5 QUBIT DATA ==========
    print("Processing 5-qubit data...")
    
    # Define backends for 5q
    backends_5q = ["qasm_simulator", "iqm_emerald", "iqm_garnet", "ibm_fez", 
                   "ibm_marrakesh", "ibm_brisbane", "rigetti_ankaa_2", "rigetti_ankaa_3"]
    
    for backend in backends_5q:
        try:
            results = np.load(f"./Data/{backend}/{nq}_1D.npy", allow_pickle=True).item()
            
            # Override iqm_emerald with AWS version
            if backend == "iqm_emerald":
                results = np.load(f"./Data/iqm_emerald/{nq}_1D_aws.npy", allow_pickle=True).item()
            
            delta = results["Deltas"][0]
            ps = results["ps"]
            
            # Find best section based on highest mean
            best_mean = 0
            best_sec = None
            for sec_i in results[f"postprocessing{case}"][delta][ps[0]].keys():
                res_i = [results[f"postprocessing{case}"][delta][p][sec_i][prop] for p in ps]
                if np.mean(res_i) > best_mean:
                    best_sec = res_i
                    best_mean = np.mean(res_i)
            
            # Extract random baseline
            random_r = results.get(f"random{case}", {}).get(prop, 0.667)
            
            data["5q"][backend] = {
                "qubits": nq,
                "p_values": ps,
                "r_values": [round(r, 3) for r in best_sec],
                "max_r": round(max(best_sec), 3),
                "optimal_p": int(ps[np.argmax(best_sec)]),
                "random_r": round(random_r, 3)
            }
            print(f"  {backend}: max_r = {round(max(best_sec), 3)} at p = {ps[np.argmax(best_sec)]}")
            
        except Exception as e:
            print(f"  Warning: Could not load {backend}: {e}")
    
    # Add special cases for 5q
    try:
        results = np.load(f"./Data/originq_wukong/{nq}_1D_2.npy", allow_pickle=True).item()
        delta = results["Deltas"][0]
        ps = results["ps"]
        best_mean = 0
        for sec_i in results[f"postprocessing{case}"][delta][ps[0]].keys():
            res_i = [results[f"postprocessing{case}"][delta][p][sec_i][prop] for p in ps]
            if np.mean(res_i) > best_mean:
                best_sec = res_i
                best_mean = np.mean(res_i)
        
        data["5q"]["originq_wukong"] = {
            "qubits": nq,
            "p_values": ps,
            "r_values": [round(r, 3) for r in best_sec],
            "max_r": round(max(best_sec), 3),
            "optimal_p": int(ps[np.argmax(best_sec)]),
            "random_r": 0.667
        }
        print(f"  originq_wukong: max_r = {round(max(best_sec), 3)} at p = {ps[np.argmax(best_sec)]}")
    except Exception as e:
        print(f"  Warning: Could not load originq_wukong: {e}")
    
    try:
        results = np.load(f"./Data/iqm_sirius/{nq}_1D_Single.npy", allow_pickle=True).item()
        delta = results["Deltas"][0]
        ps = results["ps"]
        best_mean = 0
        for sec_i in results[f"postprocessing{case}"][delta][ps[0]].keys():
            res_i = [results[f"postprocessing{case}"][delta][p][sec_i][prop] for p in ps]
            if np.mean(res_i) > best_mean:
                best_sec = res_i
                best_mean = np.mean(res_i)
        
        data["5q"]["iqm_sirius"] = {
            "qubits": nq,
            "p_values": ps,
            "r_values": [round(r, 3) for r in best_sec],
            "max_r": round(max(best_sec), 3),
            "optimal_p": int(ps[np.argmax(best_sec)]),
            "random_r": 0.667
        }
        print(f"  iqm_sirius: max_r = {round(max(best_sec), 3)} at p = {ps[np.argmax(best_sec)]}")
    except Exception as e:
        print(f"  Warning: Could not load iqm_sirius: {e}")
    
    # ========== 100 QUBIT DATA ==========
    print("\nProcessing 100-qubit data...")
    nq = 100
    delta = 1
    kk = 0
    
    backends_100q = ["ibm_marrakesh", "ibm_brisbane", "ibm_sherbrooke", "ibm_kyiv", 
                     "ibm_nazca", "ibm_kyoto", "ibm_osaka", "ibm_fez", "ibm_brussels", 
                     "ibm_strasbourg"]
    
    for backend in backends_100q:
        try:
            results = np.load(f"./Data/{backend}/{nq}_1D.npy", allow_pickle=True).item()
            res_backend = results[f"postprocessing{case}"]
            ps = list(res_backend[delta].keys())
            rs = [res_backend[delta][p][kk][prop] for p in ps]
            
            # Get random baseline
            if backend == "ibm_brisbane":
                random_r = results.get(f"random{case}", {}).get(prop, 0.50)
            else:
                random_r = 0.50
            
            data["100q"][backend] = {
                "qubits": nq,
                "p_values": ps,
                "r_values": [round(r, 3) for r in rs],
                "max_r": round(max(rs), 3),
                "optimal_p": int(ps[np.argmax(rs)]),
                "random_r": round(random_r, 3)
            }
            print(f"  {backend}: max_r = {round(max(rs), 3)} at p = {ps[np.argmax(rs)]}")
            
        except Exception as e:
            print(f"  Warning: Could not load {backend}: {e}")
    
    # Add torino variants
    try:
        results = np.load(f"./Data/ibm_torino/{nq}_1D_v1.npy", allow_pickle=True).item()
        res_backend = results[f"postprocessing{case}"]
        ps = list(res_backend[delta].keys())
        rs = [res_backend[delta][p][kk][prop] for p in ps]
        
        data["100q"]["ibm_torino-v1"] = {
            "qubits": nq,
            "p_values": ps,
            "r_values": [round(r, 3) for r in rs],
            "max_r": round(max(rs), 3),
            "optimal_p": int(ps[np.argmax(rs)]),
            "random_r": 0.50
        }
        print(f"  ibm_torino-v1: max_r = {round(max(rs), 3)} at p = {ps[np.argmax(rs)]}")
    except Exception as e:
        print(f"  Warning: Could not load ibm_torino-v1: {e}")
    
    try:
        results = np.load(f"./Data/ibm_torino/{nq}_1D.npy", allow_pickle=True).item()
        res_backend = results[f"postprocessing{case}"]
        ps = list(res_backend[delta].keys())
        rs = [res_backend[delta][p][kk][prop] for p in ps]
        
        data["100q"]["ibm_torino-v0"] = {
            "qubits": nq,
            "p_values": ps,
            "r_values": [round(r, 3) for r in rs],
            "max_r": round(max(rs), 3),
            "optimal_p": int(ps[np.argmax(rs)]),
            "random_r": 0.50
        }
        print(f"  ibm_torino-v0: max_r = {round(max(rs), 3)} at p = {ps[np.argmax(rs)]}")
    except Exception as e:
        print(f"  Warning: Could not load ibm_torino-v0: {e}")
    
    try:
        results = np.load(f"./Data/ibm_boston/{nq}_1D.npy", allow_pickle=True).item()
        res_backend = results[f"postprocessing{case}"]
        ps = list(res_backend[delta].keys())
        rs = [res_backend[delta][p][kk][prop] for p in ps]
        
        data["100q"]["ibm_boston"] = {
            "qubits": nq,
            "p_values": ps,
            "r_values": [round(r, 3) for r in rs],
            "max_r": round(max(rs), 3),
            "optimal_p": int(ps[np.argmax(rs)]),
            "random_r": 0.50
        }
        print(f"  ibm_boston: max_r = {round(max(rs), 3)} at p = {ps[np.argmax(rs)]}")
    except Exception as e:
        print(f"  Warning: Could not load ibm_boston: {e}")
    
    # Save to JSON
    output_path = Path("Data/1d_chain_processed.json")
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✓ Successfully saved data to {output_path}")
    print(f"  5q backends: {len(data['5q'])}")
    print(f"  100q backends: {len(data['100q'])}")

if __name__ == "__main__":
    generate_1d_chain_json()
