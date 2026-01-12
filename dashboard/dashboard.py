import streamlit as st
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from pathlib import Path
from collections import defaultdict
from scipy import stats

# Set page configuration
st.set_page_config(
    page_title="LR-QAOA QPU Benchmarking",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("⚛️ LR-QAOA QPU Benchmarking Dashboard")
st.markdown("""
Benchmarking QAOA performance across quantum processors for different problem types.
Explore 1D Chain, Native Layout, and Fully Connected graph experiments.
""")

# Function to load 1D chain results
@st.cache_data
def load_1d_chain_results():
    """Load 1D chain experiment results for nq=100 comparison"""
    data_dir = Path(__file__).parent.parent / "Data"
    
    names = ["ibm_boston", "ibm_marrakesh", "ibm_fez", "ibm_torino", 
             "ibm_brisbane", "ibm_sherbrooke", "ibm_kyiv", "ibm_nazca", 
             "ibm_kyoto", "ibm_osaka", "ibm_brussels", "ibm_strasbourg"]
    
    nq = 100
    delta = 1
    case = ""
    kk = 0  # section index
    
    results_data = {}
    for backend_name in names:
        try:
            results = np.load(data_dir / backend_name / f"{nq}_1D.npy", allow_pickle=True).item()
            postprocessing = results["postprocessing" + case]
            ps = list(postprocessing[delta].keys())
            rs = [postprocessing[delta][p][kk]["r"] for p in ps]
            results_data[backend_name] = {"ps": ps, "rs": rs}
            
            if backend_name == "ibm_brisbane":
                # Store random baseline data
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
                results_data["random_baseline"] = {"y1": y1, "y2": y2}
        except:
            continue
    
    # Add ibm_torino variants
    try:
        results_v1 = np.load(data_dir / "ibm_torino" / "100_1D_v1.npy", allow_pickle=True).item()
        postprocessing = results_v1["postprocessing" + case]
        ps = list(postprocessing[delta].keys())
        rs = [postprocessing[delta][p][kk]["r"] for p in ps]
        results_data["ibm_torino-v1"] = {"ps": ps, "rs": rs}
    except:
        pass
        
    if "ibm_torino" in results_data:
        results_data["ibm_torino-v0"] = results_data["ibm_torino"]
        del results_data["ibm_torino"]
    
    return results_data


# Function to load native layout results
@st.cache_data
def load_nl_results():
    """Load native layout experiment results"""
    data_dir = Path(__file__).parent.parent / "Data"
    
    case = ""
    prop = "r"
    delta = 1
    
    backends_data = {}
    
    # Load different backend results
    backend_files = {
        "ibm_brisbane": ("ibm_brisbane", "127_HE_day2.npy", delta, 1),
        "ibm_torino-v0": ("ibm_torino", "133_HE.npy", delta, 1),
        "ibm_torino-v1": ("ibm_torino", "133_HE_v1.npy", delta, 1),
        "ibm_torino-f": ("ibm_torino", "133_HE_fractional.npy", 0.75, 0.75),
        "ibm_fez": ("ibm_fez", "156_HE.npy", delta, 1),
        "ibm_fez-f": ("ibm_fez", "156_HE_fractional.npy", 0.75, 0.75),
        "ibm_marrakesh-f": ("ibm_marrakesh", "156_HE_fractional.npy", 0.75, 0.75),
        "ibm_aachen-f": ("ibm_aachen", "156_HE_fractional.npy", 0.75, 0.75),
        "ibm_kingston-f": ("ibm_kingston", "156_HE_fractional.npy", 0.75, 0.75),
        "ibm_boston-f": ("ibm_boston", "156_HEw1.npy", 0.75, 0.75),
        "iqm_garnet": ("iqm_garnet", "20_NL.npy", delta, 1),
        "iqm_emerald": ("iqm_emerald", "54_HE.npy", 0.75, 0.75),
        "rigetti_ankaa_3": ("rigetti_ankaa_3", "82_NL.npy", delta, 1),
    }
    
    for display_name, (folder, filename, delta_val, delta_key) in backend_files.items():
        try:
            results = np.load(data_dir / folder / filename, allow_pickle=True).item()
            postprocessing = results["postprocessing" + case]
            ps = results["ps"]
            
            # Handle different data structures
            if isinstance(postprocessing[delta_val][ps[0]], dict):
                if 0 in postprocessing[delta_val][ps[0]]:
                    rs = [postprocessing[delta_val][p][0][prop] for p in ps]
                else:
                    rs = [postprocessing[delta_val][p][prop] for p in ps]
            else:
                rs = [postprocessing[delta_val][p][prop] for p in ps]
            
            backends_data[display_name] = {
                "ps": list(ps),
                "rs": rs,
                "has_random": "random" + case in results
            }
            
            if backends_data[display_name]["has_random"]:
                backends_data[display_name]["random_r"] = results["random" + case][prop]
                
        except Exception as e:
            continue
    
    return backends_data


# Function to load fully connected results
@st.cache_data
def load_fc_results():
    """Load and process fully connected experiment results"""
    data_dir = Path(__file__).parent.parent / "Data"
    
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
    
    r = defaultdict(dict)
    case = ""
    
    for backend_name in backends:
        if backend_name not in nqs:
            continue
            
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
                
                # Statistical test
                std = rand_mean.std()
                t_score = (r_max_nq - y1) / std
                p_value = (1 - stats.t.cdf(t_score, df=n_rand-1))
                
                if p_value < 0.001:  # 3σ level
                    r[backend_name][nq] = ((r_max_nq - (y1+y2))/(1-(y1+y2)))
                    
            except Exception as e:
                continue
    
    # Add HPC results for specific cases
    if "ibm_torino" in r and res_hpc:
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
                    r["qasm_simulator"][nq] = ((r_max_nq - (y1+y2))/(1-(y1+y2)))
                except:
                    pass
    
    return r, backends


# Create tabs
tab1, tab2, tab3 = st.tabs(["� 1D Chain", "🔷 Native Layout", "📊 Fully Connected"])

# Tab 1: 1D Chain Experiments
with tab1:
    st.header("1D Chain Experiments - 100 Qubit Comparison")
    st.markdown("""
    Approximation ratio vs QAOA layers (p) for 1D chain graphs with 100 qubits.
    Comparing Eagle and Heron IBM QPUs with random baseline.
    """)
    
    chain_results = load_1d_chain_results()
    
    # Color and marker definitions
    colors_1d = {
        "ibm_boston": "#e41a1c", "ibm_marrakesh": "#ffed6f", "ibm_fez": "#b3de69",
        "ibm_torino-v1": "#fdb462", "ibm_torino-v0": "#fdb462", "ibm_brisbane": "#bebada",
        "ibm_sherbrooke": "#fb8072", "ibm_kyiv": "#d9d9d9", "ibm_nazca": "#80b1d3",
        "ibm_kyoto": "#bc80bd", "ibm_osaka": "#ccebc5", "ibm_brussels": "#fccde5",
        "ibm_strasbourg": "#ffffb3"
    }
    
    markers_1d = {
        "ibm_boston": "circle", "ibm_marrakesh": "circle-open", "ibm_fez": "diamond-tall",
        "ibm_torino-v1": "star", "ibm_torino-v0": "square", "ibm_brisbane": "diamond",
        "ibm_sherbrooke": "triangle-left", "ibm_kyiv": "x", "ibm_nazca": "circle",
        "ibm_kyoto": "cross", "ibm_osaka": "square", "ibm_brussels": "triangle-up",
        "ibm_strasbourg": "diamond-open"
    }
    
    linestyles_1d = {
        "ibm_torino-v0": "dash", "ibm_torino-v1": "dash", "ibm_fez": "dash"
    }
    
    fig_1d = go.Figure()
    
    # Plot each backend
    backend_order = ["ibm_boston", "ibm_marrakesh", "ibm_fez", "ibm_torino-v1", 
                     "ibm_torino-v0", "ibm_brisbane", "ibm_sherbrooke", "ibm_kyiv",
                     "ibm_nazca", "ibm_kyoto", "ibm_osaka", "ibm_brussels", "ibm_strasbourg"]
    
    for backend_name in backend_order:
        if backend_name not in chain_results:
            continue
        data = chain_results[backend_name]
        
        fig_1d.add_trace(go.Scatter(
            x=data["ps"],
            y=data["rs"],
            mode='lines+markers',
            name=backend_name,
            marker=dict(
                symbol=markers_1d.get(backend_name, "circle"),
                size=8,
                color=colors_1d.get(backend_name, "#808080"),
                line=dict(color='black', width=1)
            ),
            line=dict(
                color=colors_1d.get(backend_name, "#808080"),
                width=2,
                dash=linestyles_1d.get(backend_name, "solid")
            ),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                          'p: %{x}<br>' +
                          'r: %{y:.3f}<br>' +
                          '<extra></extra>'
        ))
    
    # Add random baseline
    if "random_baseline" in chain_results:
        y1 = chain_results["random_baseline"]["y1"]
        y2 = chain_results["random_baseline"]["y2"]
        
        fig_1d.add_trace(go.Scatter(
            x=[1, 100],
            y=[y1-y2, y1-y2],
            fill=None,
            mode='lines',
            line=dict(color='rgba(128,128,128,0)', width=0),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        fig_1d.add_trace(go.Scatter(
            x=[1, 100],
            y=[y1+y2, y1+y2],
            fill='tonexty',
            mode='lines',
            line=dict(color='rgba(128,128,128,0)', width=0),
            fillcolor='rgba(128,128,128,0.3)',
            name='random (3σ)',
            hovertemplate='Random baseline<br>r: %{y:.3f}<extra></extra>'
        ))
    
    fig_1d.update_layout(
        xaxis_title="QAOA Layers (p)",
        yaxis_title="Approximation Ratio (r)",
        height=600,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        template="plotly_white"
    )
    
    st.plotly_chart(fig_1d, use_container_width=True)
    
    # Statistics table
    st.subheader("Backend Performance Statistics (100 qubits)")
    stats_1d = []
    for backend_name in backend_order:
        if backend_name not in chain_results or backend_name == "random_baseline":
            continue
        data = chain_results[backend_name]
        stats_1d.append({
            "Backend": backend_name,
            "Max r": f"{max(data['rs']):.3f}",
            "Optimal p": data["ps"][data["rs"].index(max(data["rs"]))],
            "Min p tested": min(data["ps"]),
            "Max p tested": max(data["ps"])
        })
    
    if stats_1d:
        st.dataframe(pd.DataFrame(stats_1d), use_container_width=True, hide_index=True)


# Tab 2: Native Layout Experiments
with tab2:
    st.header("Native Layout Experiments")
    st.markdown("""
    Approximation ratio vs QAOA layers for hardware-native graph topologies.
    Testing large-scale Eagle and Heron processors with native connectivity.
    """)
    
    nl_data = load_nl_results()
    
    # Color definitions for native layout
    colors_nl = {
        "ibm_brisbane": "#bebada", "ibm_torino-v0": "#fdb462",
        "ibm_torino-v1": "#fdb462", "ibm_torino-f": "#fdb462",
        "ibm_fez": "#b3de69", "ibm_fez-f": "#b3de69",
        "ibm_marrakesh-f": "#ffed6f", "ibm_aachen-f": "#e41a1c",
        "ibm_kingston-f": "#377eb8", "ibm_boston-f": "#984ea3",
        "iqm_garnet": "#fb8072", "iqm_emerald": "#80b1d3",
        "rigetti_ankaa_3": "#fccde5"
    }
    
    markers_nl = {
        "ibm_brisbane": "diamond", "ibm_torino-v0": "circle",
        "ibm_torino-v1": "cross", "ibm_torino-f": "square",
        "ibm_fez": "triangle-up", "ibm_fez-f": "star",
        "ibm_marrakesh-f": "circle-open", "ibm_aachen-f": "triangle-down",
        "ibm_kingston-f": "triangle-down", "ibm_boston-f": "circle",
        "iqm_garnet": "diamond-open", "iqm_emerald": "circle",
        "rigetti_ankaa_3": "diamond-tall"
    }
    
    linestyles_nl = {
        "ibm_torino-v0": "dash", "ibm_torino-v1": "dash",
        "ibm_torino-f": "dash", "ibm_fez": "dash",
        "ibm_fez-f": "dash", "ibm_marrakesh-f": "dash",
        "ibm_aachen-f": "dash", "ibm_kingston-f": "dash",
        "ibm_boston-f": "dash"
    }
    
    fig_nl = go.Figure()
    
    backend_order_nl = [
        "iqm_garnet", "rigetti_ankaa_3", "iqm_emerald",
        "ibm_brisbane", "ibm_torino-v0", "ibm_torino-v1", "ibm_torino-f",
        "ibm_fez", "ibm_fez-f", "ibm_marrakesh-f",
        "ibm_kingston-f", "ibm_aachen-f", "ibm_boston-f"
    ]
    
    for backend_name in backend_order_nl:
        if backend_name not in nl_data:
            continue
        data = nl_data[backend_name]
        
        fig_nl.add_trace(go.Scatter(
            x=data["ps"],
            y=data["rs"],
            mode='lines+markers',
            name=backend_name,
            marker=dict(
                symbol=markers_nl.get(backend_name, "circle"),
                size=8,
                color=colors_nl.get(backend_name, "#808080"),
                line=dict(color='black', width=1)
            ),
            line=dict(
                color=colors_nl.get(backend_name, "#808080"),
                width=2,
                dash=linestyles_nl.get(backend_name, "solid")
            ),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                          'p: %{x}<br>' +
                          'r: %{y:.3f}<br>' +
                          '<extra></extra>'
        ))
        
        # Add random baseline line if available
        if data.get("has_random") and "random_r" in data:
            fig_nl.add_trace(go.Scatter(
                x=data["ps"],
                y=[data["random_r"]] * len(data["ps"]),
                mode='lines',
                line=dict(color=colors_nl.get(backend_name, "#808080"), dash="dot", width=1),
                showlegend=False,
                hoverinfo='skip'
            ))
    
    # Add legend for random baseline
    fig_nl.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='lines',
        line=dict(color='black', dash='dot', width=1),
        name='random',
        showlegend=True
    ))
    
    fig_nl.update_layout(
        xaxis_title="QAOA Layers (p)",
        yaxis_title="Approximation Ratio (r)",
        xaxis=dict(tickvals=[3, 10, 25, 50, 75, 100]),
        height=600,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        template="plotly_white"
    )
    
    st.plotly_chart(fig_nl, use_container_width=True)
    
    # Statistics table
    st.subheader("Backend Performance Statistics")
    stats_nl = []
    for backend_name in backend_order_nl:
        if backend_name not in nl_data:
            continue
        data = nl_data[backend_name]
        stats_nl.append({
            "Backend": backend_name,
            "Qubits": "20" if "garnet" in backend_name else "54" if "emerald" in backend_name else "82" if "ankaa" in backend_name else "127" if "brisbane" in backend_name else "133" if "torino" in backend_name else "156",
            "Max r": f"{max(data['rs']):.3f}",
            "Optimal p": data["ps"][data["rs"].index(max(data["rs"]))],
            "Min p": min(data["ps"]),
            "Max p": max(data["ps"])
        })
    
    if stats_nl:
        st.dataframe(pd.DataFrame(stats_nl), use_container_width=True, hide_index=True)


# Tab 3: Fully Connected Experiments
with tab3:
    st.header("Fully Connected Graph Experiments")
    st.markdown("""
    Effective approximation ratio vs number of qubits for fully connected graphs.
    Results are normalized against random sampling baseline (3σ threshold).
    """)
    
    r_data, backends = load_fc_results()
    
    # Define colors and markers
    colors_map = {
        "aqt_ibexq1": "#e41a1c", "ibm_boston": "#e41a1c", "ionq_forte": "#8dd3c7",
        "ibm_torino": "#fdb462", "ibm_brisbane": "#bebada", "H1-1E": "#fb8072",
        "qasm_simulator": "#80b1d3", "H2-1E": "#fdb462", "ibm_fez": "#b3de69",
        "H2-1": "#fccde5", "ionq_aria_2": "#d9d9d9", "ionq_harmony": "#bc80bd",
        "ionq_forte_enterprise": "#ccebc5", "ibm_marrakesh": "#ffed6f",
        "iqm_garnet": "#b3de69", "iqm_emerald": "#377eb8"
    }
    
    markers_map = {
        "aqt_ibexq1": "diamond-open", "ibm_boston": "circle", "ionq_forte": "star",
        "ibm_torino": "triangle-up", "ibm_brisbane": "diamond", "H1-1E": "cross",
        "qasm_simulator": "circle", "H2-1E": "x", "ibm_fez": "diamond-open",
        "H2-1": "triangle-right", "ionq_aria_2": "triangle-left", "ionq_harmony": "square",
        "ibm_marrakesh": "circle-open", "ionq_forte_enterprise": "triangle-down",
        "iqm_garnet": "square", "iqm_emerald": "triangle-up"
    }
    
    # Create Plotly figure
    fig = go.Figure()
    
    for backend_name in backends:
        if backend_name in r_data and len(r_data[backend_name]) > 0:
            nqs = list(r_data[backend_name].keys())
            r_values = list(r_data[backend_name].values())
            
            fig.add_trace(go.Scatter(
                x=nqs,
                y=r_values,
                mode='lines+markers',
                name=backend_name if backend_name != "ibm_torino" else "ibm_torino-v0",
                marker=dict(
                    symbol=markers_map.get(backend_name, "circle"),
                    size=12 if backend_name == "ionq_forte" else 10,
                    color=colors_map.get(backend_name, "#808080"),
                    line=dict(color='black', width=1)
                ),
                line=dict(color=colors_map.get(backend_name, "#808080"), width=2),
                hovertemplate='<b>%{fullData.name}</b><br>' +
                              'Qubits: %{x}<br>' +
                              'r_eff: %{y:.3f}<br>' +
                              '<extra></extra>'
            ))
    
    fig.update_layout(
        xaxis_title="Number of Qubits",
        yaxis_title="Effective Approximation Ratio (r_eff)",
        yaxis_type="log",
        xaxis=dict(tickvals=[5,10,15,20,25,30,40,50,56]),
        yaxis=dict(tickvals=[0.01, 0.1, 1], ticktext=["0.01", "0.1", "1"]),
        hovermode='closest',
        height=600,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        template="plotly_white"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Show statistics
    st.subheader("Backend Statistics")
    stats_data = []
    for backend_name in backends:
        if backend_name in r_data and len(r_data[backend_name]) > 0:
            nqs_list = sorted(r_data[backend_name].keys())
            r_values = [r_data[backend_name][nq] for nq in nqs_list]
            stats_data.append({
                "Backend": backend_name,
                "Qubit Range": f"{min(nqs_list)}-{max(nqs_list)}",
                "Data Points": len(nqs_list),
                "Max r_eff": f"{max(r_values):.3f}",
                "Min r_eff": f"{min(r_values):.3f}"
            })
    
    if stats_data:
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True, hide_index=True)

