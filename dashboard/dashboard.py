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
tab1, tab2, tab3 = st.tabs(["📊 Fully Connected", "🔗 1D Chain", "🔷 Native Layout"])

# Tab 1: Fully Connected Experiments
with tab1:
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


# Tab 2: 1D Chain Experiments
with tab2:
    st.header("1D Chain Experiments")
    st.markdown("""
    QAOA benchmarking on 1D chain graph topologies.
    *Coming soon: Performance analysis for linear connectivity patterns.*
    """)
    st.info("📊 Data visualization for 1D chain experiments will be added here.")


# Tab 3: Native Layout Experiments
with tab3:
    st.header("Native Layout Experiments")
    st.markdown("""
    QAOA performance using hardware-native graph topologies.
    *Coming soon: Analysis of native connectivity layouts for different QPU architectures.*
    """)
    st.info("📊 Data visualization for native layout experiments will be added here.")
