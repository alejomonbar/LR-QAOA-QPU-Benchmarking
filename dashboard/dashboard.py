import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from pathlib import Path
from collections import defaultdict
import json

# Set page configuration
st.set_page_config(
    page_title="LR-QAOA QPU Benchmarking",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description with logo
col1, col2 = st.columns([1, 10])
with col1:
    logo_path = Path(__file__).parent / "Logo.png"
    if logo_path.exists():
        st.image(str(logo_path), width=100, use_column_width=False)
with col2:
    st.title("LR-QAOA QPU Benchmarking Dashboard")

st.markdown("""
### Benchmarking Linear Ramp QAOA on Quantum Processing Units

This dashboard presents comprehensive benchmarking results of the **Linear Ramp Quantum Approximate Optimization Algorithm (LR-QAOA)** 
across multiple quantum processors from leading quantum computing providers including IBM, IonQ, Rigetti, IQM, and AQT.

**What is LR-QAOA?** LR-QAOA is a variant of QAOA that uses a linear ramp scheduling approach for the mixing and 
problem Hamiltonians. This method enables efficient implementation of optimization problems on quantum hardware and 
improves performance on near-term quantum devices.

**Key Features:**
- 📊 **Fully Connected Graphs**: Up to 56 qubits tested across multiple QPUs
- 🔷 **Native Layout Problems**: Hardware-native graph structures (up to 156 qubits)
- 🔗 **1D Chain Graphs**: 100-qubit comparisons across IBM Eagle and Heron processors

**Reference:** For detailed methodology and results, see our paper:  
[*Evaluating the performance of quantum processing units at large width and depth*](https://arxiv.org/abs/2502.06471) (arXiv:2502.06471)

---
""")

# Function to load 1D chain results
@st.cache_data
def load_1d_chain_results():
    """Load 1D chain experiment results for nq=100 comparison from JSON"""
    data_dir = Path(__file__).parent.parent / "Data"
    
    try:
        json_path = data_dir / "1d_chain_processed.json"
        with open(json_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Error loading 1D chain data: {str(e)}")
        return {}


# Function to load native layout results
@st.cache_data
def load_nl_results():
    """Load native layout experiment results from JSON"""
    data_dir = Path(__file__).parent.parent / "Data"
    
    try:
        json_path = data_dir / "native_layout_processed.json"
        with open(json_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Error loading native layout data: {str(e)}")
        return {}


# Function to load fully connected results
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_fc_results():
    """Load fully connected experiment results from JSON"""
    data_dir = Path(__file__).parent.parent / "Data"
    
    backends = [
        "aqt_ibexq1", "ibm_brisbane", "ibm_fez", "ibm_boston",
        "H1-1E", "qasm_simulator", "H2-1E", "H2-1",
        "ionq_forte", "ionq_aria_2", "ionq_harmony", "ibm_torino",
        "ionq_forte_enterprise", "ibm_marrakesh", "iqm_garnet", "iqm_emerald"
    ]
    
    r = defaultdict(dict)
    debug_info = []
    
    try:
        # Load processed JSON data
        json_path = data_dir / "fc_processed.json"
        with open(json_path, 'r') as f:
            fc_data = json.load(f)
        
        debug_info.append(f"✅ Loaded JSON data from {json_path.name}")
        
        # Extract r_eff values for each backend
        for backend_name in backends:
            if backend_name in fc_data:
                for nq_str, data in fc_data[backend_name].items():
                    nq = int(nq_str)
                    p_val = data["statistics"]["p_value"]
                    p_val_str = f"{p_val:.6f}" if p_val is not None else "N/A"
                    
                    if data["statistics"]["significant"]:
                        r[backend_name][nq] = data["r_eff"]
                        debug_info.append(f"✅ {backend_name} nq={nq}: r_eff={data['r_eff']:.4f}, p-value={p_val_str}")
                    else:
                        debug_info.append(f"❌ {backend_name} nq={nq}: Failed significance test (p-value={p_val_str} >= 0.001)")
            else:
                debug_info.append(f"⚠️ {backend_name} not found in JSON data")
    
    except FileNotFoundError as e:
        debug_info.append(f"🔴 JSON file not found: {str(e)}")
        fc_data = {}
    except Exception as e:
        debug_info.append(f"🔴 Error loading JSON: {str(e)}")
        import traceback
        debug_info.append(f"🔴 Traceback: {traceback.format_exc()}")
        fc_data = {}
    
    return r, backends, debug_info, fc_data


# Create tabs
tab1, tab2, tab3 = st.tabs(["Fully Connected", "Native Layout", "1D Chain"])

# Tab 1: Fully Connected Experiments
with tab1:
    # Add logo for FC experiments
    col_logo, col_header = st.columns([1, 10])
    with col_logo:
        fc_logo_path = Path(__file__).parent / "FC-logo.png"
        if fc_logo_path.exists():
            st.image(str(fc_logo_path), width=120, use_column_width=False)
    with col_header:
        st.header("Fully Connected Graph Experiments")
    
    st.markdown("""
    Effective approximation ratio vs number of qubits for fully connected graphs.
    Results are normalized against random sampling baseline (3σ threshold).
    """)
    
    r_data, backends, debug_info, fc_data = load_fc_results()

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

    # Show QPU capabilities over time
    st.subheader("📅 QPU Capabilities Timeline")
    st.markdown("Maximum qubit count per backend and when experiments were conducted.")
    
    # Collect max qubits and file dates for each backend from JSON
    timeline_data = []
    
    for backend_name in backends:
        if backend_name in fc_data:
            # Find the entry with maximum qubits
            max_nq = 0
            max_date = None
            for nq_str, data in fc_data[backend_name].items():
                nq = int(nq_str)
                if nq > max_nq and data["statistics"]["significant"]:
                    max_nq = nq
                    if "file_created" in data:
                        max_date = data["file_created"]
            
            if max_nq > 0 and max_date:
                import datetime
                timeline_data.append({
                    "backend": backend_name,
                    "max_qubits": max_nq,
                    "date": datetime.datetime.strptime(max_date, "%Y-%m-%d")
                })
    
    if timeline_data:
        # Create timeline plot
        fig_timeline = go.Figure()
        
        for item in timeline_data:
            fig_timeline.add_trace(go.Scatter(
                x=[item["date"]],
                y=[item["max_qubits"]],
                mode='markers',
                name=item["backend"],
                marker=dict(
                    symbol=markers_map.get(item["backend"], "circle"),
                    size=12,
                    color=colors_map.get(item["backend"], "#808080"),
                    line=dict(color='white', width=2)
                ),
                hovertemplate='<b>%{fullData.name}</b><br>' +
                              'Date: %{x|%Y-%m-%d}<br>' +
                              'Max Qubits: %{y}<br>' +
                              '<extra></extra>'
            ))
        
        fig_timeline.update_layout(
            xaxis_title="Experiment Date",
            yaxis_title="Maximum Number of Qubits",
            hovermode='closest',
            height=600,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=10)
            ),
            template="plotly_white",
            yaxis=dict(tickvals=[5, 10, 15, 20, 25, 30, 40, 50, 56]),
            margin=dict(r=150)
        )
        
        st.plotly_chart(fig_timeline, use_container_width=True)
    

    
    # Add debug expander
    with st.expander("🔍 Debug Information - Data Loading Status"):
        for info in debug_info:
            if "✅" in info:
                st.success(info)
            elif "❌" in info:
                st.warning(info)
            elif "🔴" in info:
                st.error(info)
            else:
                st.info(info)
        
        # Show what backends have data
        st.write("---")
        st.write("**Backends with loaded data:**")
        for backend in backends:
            if backend in r_data and len(r_data[backend]) > 0:
                st.write(f"✓ {backend}: {len(r_data[backend])} datapoints - qubits: {sorted(r_data[backend].keys())}")
            else:
                st.write(f"✗ {backend}: No data")
    
    # Main plot: Effective Approximation Ratio vs Number of Qubits
    st.markdown("---")
    st.subheader("📊 Scalability Analysis")
    st.markdown("Effective approximation ratio across different qubit counts.")
    
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
    
    # Add interactive plot for specific qubit count
    st.markdown("---")
    st.subheader("📈 Approximation Ratio vs Circuit Depth")
    st.markdown("Select a qubit count to see how different backends performed across circuit depths.")
    
    # Get all unique qubit counts across all backends
    all_qubits = set()
    for backend_name in backends:
        if backend_name in r_data:
            all_qubits.update(r_data[backend_name].keys())
    
    if all_qubits:
        all_qubits_sorted = sorted(all_qubits)
        selected_nq = st.selectbox("Select number of qubits:", all_qubits_sorted, index=all_qubits_sorted.index(15) if 15 in all_qubits_sorted else 0)
        
        # Load detailed data for selected qubit count
        data_dir = Path(__file__).parent.parent / "Data"
        fig_detail = go.Figure()
        case = ""
        
        # Find which backends have this qubit count
        available_backends = [b for b in backends if b in fc_data and str(selected_nq) in fc_data[b]]
        
        for backend_name in available_backends:
            try:
                data = fc_data[backend_name][str(selected_nq)]
                
                # Check if r_vs_p data exists
                if "r_vs_p" not in data:
                    continue
                    
                r_vs_p = data["r_vs_p"]
                ps = r_vs_p["p_values"]
                yp = r_vs_p["r_values"]
                
                # Filter out zero or negative values
                ps_filtered = [ps[i] for i in range(len(yp)) if yp[i] > 0]
                yp_filtered = [yi for yi in yp if yi > 0]
                
                if ps_filtered:
                    fig_detail.add_trace(go.Scatter(
                        x=ps_filtered,
                        y=yp_filtered,
                        mode='markers',
                        name=backend_name,
                        marker=dict(
                            symbol=markers_map.get(backend_name, "circle"),
                            size=12 if backend_name == "ionq_forte" else 10,
                            color=colors_map.get(backend_name, "#808080"),
                            line=dict(color='black', width=1)
                        ),
                        hovertemplate='<b>%{fullData.name}</b><br>' +
                                      'Depth (p): %{x}<br>' +
                                      'r: %{y:.4f}<br>' +
                                      '<extra></extra>'
                    ))
            except Exception as e:
                st.warning(f"Could not load detailed data for {backend_name} at {selected_nq} qubits: {str(e)}")
        
        # Add random baseline shaded region from JSON
        if available_backends:
            try:
                # Use the first available backend to get random baseline
                baseline = fc_data[available_backends[0]][str(selected_nq)]["random_baseline"]
                y1 = baseline["mean"]
                y2 = baseline["std_3sigma"]
                
                # Find max p value
                max_p = max([max(fc_data[b][str(selected_nq)]["r_vs_p"]["p_values"]) 
                            for b in available_backends 
                            if "r_vs_p" in fc_data[b][str(selected_nq)]])
                
                # Add shaded region
                fig_detail.add_trace(go.Scatter(
                    x=[0, max_p],
                    y=[y1 + y2, y1 + y2],
                    fill=None,
                    mode='lines',
                    line=dict(color='rgba(128,128,128,0)'),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                fig_detail.add_trace(go.Scatter(
                    x=[0, max_p],
                    y=[y1 - y2, y1 - y2],
                    fill='tonexty',
                    mode='lines',
                    line=dict(color='rgba(128,128,128,0)'),
                    fillcolor='rgba(128,128,128,0.4)',
                    name='Random baseline (μ ± 3σ)',
                    hovertemplate='Random: %{y:.4f}<extra></extra>'
                ))
            except Exception as e:
                st.warning(f"Could not add random baseline: {str(e)}")
        
        fig_detail.update_layout(
            xaxis_title="Circuit Depth (p)",
            yaxis_title="Approximation Ratio (r)",
            hovermode='closest',
            height=500,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="right",
                x=1
            ),
            template="plotly_white"
        )
        
        st.plotly_chart(fig_detail, use_container_width=True)
        
        if not available_backends:
            st.info(f"No backends have data for {selected_nq} qubits.")
    
    # Show statistics
    st.markdown("---")
    st.subheader("Backend Statistics")
    
    stats_data = []
    for backend_name in backends:
        if backend_name in r_data and len(r_data[backend_name]) > 0:
            nqs_list = sorted(r_data[backend_name].keys())
            r_values = [r_data[backend_name][nq] for nq in nqs_list]
            
            # Get creation date for max qubit experiment from JSON
            max_nq = max(nqs_list)
            exp_date = "N/A"
            if backend_name in fc_data and str(max_nq) in fc_data[backend_name]:
                exp_date = fc_data[backend_name][str(max_nq)].get("file_created", "N/A")
            
            stats_data.append({
                "Backend": backend_name,
                "Max Qubits": max_nq,
                "Experiment Date": exp_date,
                "Qubit Range": f"{min(nqs_list)}-{max(nqs_list)}",
                "Data Points": len(nqs_list),
                "Max r_eff": f"{max(r_values):.3f}",
                "Min r_eff": f"{min(r_values):.3f}"
            })
    
    if stats_data:
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True, hide_index=True)

# Tab 2: Native Layout Experiments
with tab2:
    # Add logo for NL experiments
    col_logo, col_header = st.columns([1, 10])
    with col_logo:
        nl_logo_path = Path(__file__).parent / "NL-logo.png"
        if nl_logo_path.exists():
            st.image(str(nl_logo_path), width=120, use_column_width=False)
    with col_header:
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
            x=data["p_values"],
            y=data["r_values"],
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
                x=data["p_values"],
                y=[data["random_r"]] * len(data["p_values"]),
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
            "Qubits": data["qubits"],
            "Max r": f"{data['max_r']:.3f}",
            "Optimal p": data["optimal_p"],
            "Min p": min(data["p_values"]),
            "Max p": max(data["p_values"])
        })
    
    if stats_nl:
        st.dataframe(pd.DataFrame(stats_nl), use_container_width=True, hide_index=True)


# Tab 3: 1D Chain Experiments
with tab3:
    # Add logo for 1D Chain experiments
    col_logo, col_header = st.columns([1, 10])
    with col_logo:
        chain_logo_path = Path(__file__).parent / "1D-logo.png"
        if chain_logo_path.exists():
            st.image(str(chain_logo_path), width=120, use_column_width=False)
    with col_header:
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
            x=data["p_values"],
            y=data["r_values"],
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
    
    # Add random baseline from first backend that has it
    random_baseline = None
    for backend_name in chain_results:
        if "random_r" in chain_results[backend_name]:
            # Calculate baseline range (mock 3sigma for visualization)
            random_baseline = chain_results[backend_name]["random_r"]
            break
    
    if random_baseline:
        y1 = random_baseline
        y2 = 0.02  # Mock sigma for visualization
        
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
            name='random baseline',
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
        if backend_name not in chain_results:
            continue
        data = chain_results[backend_name]
        stats_1d.append({
            "Backend": backend_name,
            "Max r": f"{data['max_r']:.3f}",
            "Optimal p": data["optimal_p"],
            "Min p tested": min(data["p_values"]),
            "Max p tested": max(data["p_values"])
        })
    
    if stats_1d:
        st.dataframe(pd.DataFrame(stats_1d), use_container_width=True, hide_index=True)


