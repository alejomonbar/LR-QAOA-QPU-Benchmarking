import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from pathlib import Path
from collections import defaultdict
import json

# Set page configuration
# Prefer using bundled logo as page icon when available
logo_path = Path(__file__).parent / "Logo.png"
st.set_page_config(
    page_title="LR-QAOA QPU Benchmarking",
    page_icon=str(logo_path) if logo_path.exists() else "LR",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description with logo
col1, col2 = st.columns([1, 10])
with col1:
    if logo_path.exists():
        st.image(str(logo_path), width=100, use_column_width=False)
with col2:
    st.title("LR-QAOA QPU Benchmarking Dashboard")

st.markdown("""
### Benchmarking Linear Ramp QAOA on Quantum Processing Units

This dashboard uses LR-QAOA — a fixed-parameter, deterministic "Linear Ramp" variant of QAOA — to quantify a QPU's
ability to preserve coherent signal as circuit depth increases and to identify when performance becomes
statistically indistinguishable from random sampling. The protocol scales to large width and depth, enabling
cross-platform comparisons of algorithmic performance.

We apply LR-QAOA across 24 processors from six vendors, testing problems up to 156 qubits and circuits up to 10,000 layers
across 1D chains, native layouts, and fully connected topologies.

**Reference:** [*Evaluating the performance of quantum processing units at large width and depth*](https://arxiv.org/abs/2502.06471)

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

        debug_info.append(f"OK Loaded JSON data from {json_path.name}")
        
        # Extract r_eff values for each backend
        for backend_name in backends:
            if backend_name in fc_data:
                for nq_str, data in fc_data[backend_name].items():
                    nq = int(nq_str)
                    p_val = data["statistics"]["p_value"]
                    p_val_str = f"{p_val:.6f}" if p_val is not None else "N/A"
                    
                    if data["statistics"]["significant"]:
                        r[backend_name][nq] = data["r_eff"]
                        debug_info.append(f"OK {backend_name} nq={nq}: r_eff={data['r_eff']:.4f}, p-value={p_val_str}")
                    else:
                        debug_info.append(f"WARN {backend_name} nq={nq}: Failed significance test (p-value={p_val_str} >= 0.001)")
            else:
                debug_info.append(f"WARN {backend_name} not found in JSON data")
    
    except FileNotFoundError as e:
        debug_info.append(f"ERR JSON file not found: {str(e)}")
        fc_data = {}
    except Exception as e:
        debug_info.append(f"ERR Error loading JSON: {str(e)}")
        import traceback
        debug_info.append(f"ERR Traceback: {traceback.format_exc()}")
        fc_data = {}
    
    return r, backends, debug_info, fc_data


def compute_fc_interesting_facts(fc_data: dict) -> list[str]:
    """Compute compact dataset statistics from processed FC data"""
    if not fc_data:
        return []

    # Vendor mapping
    vendor_map = {
        "ibm_brisbane": "IBM", "ibm_fez": "IBM", "ibm_boston": "IBM", "ibm_torino": "IBM", "ibm_marrakesh": "IBM",
        "ionq_forte": "IonQ", "ionq_aria_2": "IonQ", "ionq_harmony": "IonQ", "ionq_forte_enterprise": "IonQ",
        "iqm_garnet": "IQM", "iqm_emerald": "IQM",
        "H1-1E": "Quantinuum", "H2-1": "Quantinuum", "H2-1E": "Quantinuum",
        "aqt_ibexq1": "AQT",
        "qasm_simulator": "Simulator"
    }

    num_qpus = 0
    max_depth = 0
    vendors = set()
    quantinuum_backends = []

    for backend_name, backend_entries in fc_data.items():
        if not isinstance(backend_entries, dict):
            continue
        
        # Count QPUs (exclude simulator)
        if backend_name != "qasm_simulator":
            num_qpus += 1
        
        # Track vendors
        vendor = vendor_map.get(backend_name, "Other")
        if vendor != "Simulator":
            vendors.add(vendor)
        
        # Track Quantinuum backends
        if vendor == "Quantinuum":
            quantinuum_backends.append(backend_name)
        
        # Find max depth
        for nq_str, record in backend_entries.items():
            if not isinstance(record, dict):
                continue
            
            r_vs_p = record.get("r_vs_p") or {}
            p_values = r_vs_p.get("p_values") or []
            if p_values:
                max_p = max(p_values)
                if max_p > max_depth:
                    max_depth = max_p

    facts = []
    facts.append(f"Quantum processors tested: {num_qpus}")
    facts.append(f"Vendors represented: {len(vendors)} ({', '.join(sorted(vendors))})")
    if max_depth > 0:
        facts.append(f"Largest experiment depth: {max_depth} QAOA layers")
    if quantinuum_backends:
        facts.append(f"Note: {', '.join(sorted(quantinuum_backends))} are Quantinuum systems")
    return facts


# Compact dataset snapshot (derived from the same processed JSON used by plots)
_r_tmp, _backends_tmp, _debug_tmp, _fc_data_tmp = load_fc_results()
_facts = compute_fc_interesting_facts(_fc_data_tmp)
if _facts:
    st.subheader("Interesting facts (from the plotted data)")
    st.caption("Quick snapshot from the processed dataset currently loaded by this dashboard.")
    st.markdown("\n".join([f"- {fact}" for fact in _facts]))
    st.markdown("---")

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
    st.subheader("QPU Capabilities Timeline")
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
                    size=14,
                    color=colors_map.get(item["backend"], "#808080"),
                    line=dict(color='black', width=2)
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
    with st.expander("Debug Information - Data Loading Status"):
        for info in debug_info:
            if info.startswith("OK "):
                st.success(info)
            elif info.startswith("WARN "):
                st.warning(info)
            elif info.startswith("ERR "):
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
    st.subheader("Scalability Analysis")
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
    st.subheader("Approximation Ratio vs Circuit Depth")
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
        st.header("1D Chain Experiments")
    
    st.markdown("""
    Approximation ratio vs QAOA layers (p) for 1D chain graphs at different scales.
    """)
    
    chain_results = load_1d_chain_results()
    
    # ========== 5 QUBIT EXPERIMENTS ==========
    st.subheader("5-Qubit Comparison")
    st.markdown("Comparing multiple QPUs on small-scale 1D chain problems.")
    
    results_5q = chain_results.get("5q", {})
    
    # Color and marker definitions for 5q
    colors_5q = {
        "originq_wukong": "#8dd3c7", "qasm_simulator": "#bebada", "iqm_emerald": "#fb8072",
        "iqm_garnet": "#80b1d3", "ibm_fez": "#b3de69", "ibm_marrakesh": "#ffed6f",
        "ibm_brisbane": "#fdb462", "rigetti_ankaa_2": "#fccde5", "rigetti_ankaa_3": "#bc80bd",
        "iqm_sirius": "#ccebc5"
    }
    
    markers_5q = {
        "originq_wukong": "star", "qasm_simulator": "cross", "iqm_emerald": "triangle-up",
        "iqm_garnet": "x", "ibm_fez": "diamond-tall", "ibm_marrakesh": "circle",
        "ibm_brisbane": "circle-open", "rigetti_ankaa_2": "hexagon", "rigetti_ankaa_3": "hexagon2",
        "iqm_sirius": "circle"
    }
    
    fig_5q = go.Figure()
    
    # Plot each 5q backend
    backend_order_5q = ["originq_wukong", "qasm_simulator", "iqm_emerald", "iqm_garnet", "iqm_sirius",
                        "ibm_fez", "ibm_marrakesh", "ibm_brisbane", 
                        "rigetti_ankaa_2", "rigetti_ankaa_3"]
    
    for backend_name in backend_order_5q:
        if backend_name not in results_5q:
            continue
        data = results_5q[backend_name]
        
        fig_5q.add_trace(go.Scatter(
            x=data["p_values"],
            y=data["r_values"],
            mode='lines+markers',
            name=backend_name,
            marker=dict(
                symbol=markers_5q.get(backend_name, "circle"),
                size=8,
                color=colors_5q.get(backend_name, "#808080"),
                line=dict(color='black', width=1)
            ),
            line=dict(
                color=colors_5q.get(backend_name, "#808080"),
                width=2
            ),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                          'p: %{x}<br>' +
                          'r: %{y:.3f}<br>' +
                          '<extra></extra>'
        ))
    
    # Add random baseline for 5q
    if results_5q and "qasm_simulator" in results_5q:
        random_baseline = results_5q["qasm_simulator"]["random_r"]
        y1 = random_baseline
        y2 = 0.02
        
        fig_5q.add_trace(go.Scatter(
            x=[1, 100],
            y=[y1-y2, y1-y2],
            fill=None,
            mode='lines',
            line=dict(color='rgba(128,128,128,0)', width=0),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        fig_5q.add_trace(go.Scatter(
            x=[1, 100],
            y=[y1+y2, y1+y2],
            fill='tonexty',
            mode='lines',
            line=dict(color='rgba(128,128,128,0)', width=0),
            fillcolor='rgba(128,128,128,0.3)',
            name='random baseline',
            hovertemplate='Random baseline<br>r: %{y:.3f}<extra></extra>'
        ))
    
    fig_5q.update_layout(
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
    
    st.plotly_chart(fig_5q, use_container_width=True)
    
    # Statistics table for 5q
    stats_5q = []
    for backend_name in backend_order_5q:
        if backend_name not in results_5q:
            continue
        data = results_5q[backend_name]
        stats_5q.append({
            "Backend": backend_name,
            "Qubits": data["qubits"],
            "Max r": f"{data['max_r']:.3f}",
            "Optimal p": data["optimal_p"],
            "p range": f"{min(data['p_values'])}-{max(data['p_values'])}"
        })
    
    if stats_5q:
        st.dataframe(pd.DataFrame(stats_5q), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ========== 100 QUBIT EXPERIMENTS ==========
    st.subheader("100-Qubit Comparison")
    st.markdown("Large-scale 1D chain experiments on IBM Eagle and Heron processors.")
    
    results_100q = chain_results.get("100q", {})
    
    # Color and marker definitions for 100q
    colors_100q = {
        "ibm_boston": "#e41a1c", "ibm_marrakesh": "#ffed6f", "ibm_fez": "#b3de69",
        "ibm_torino-v1": "#fdb462", "ibm_torino-v0": "#fda462", "ibm_brisbane": "#bebada",
        "ibm_sherbrooke": "#fb8072", "ibm_kyiv": "#d9d9d9", "ibm_nazca": "#80b1d3",
        "ibm_kyoto": "#bc80bd", "ibm_osaka": "#ccebc5", "ibm_brussels": "#fccde5",
        "ibm_strasbourg": "#ffffb3"
    }
    
    markers_100q = {
        "ibm_boston": "circle", "ibm_marrakesh": "circle-open", "ibm_fez": "diamond-tall",
        "ibm_torino-v1": "star", "ibm_torino-v0": "square", "ibm_brisbane": "diamond",
        "ibm_sherbrooke": "triangle-left", "ibm_kyiv": "x", "ibm_nazca": "circle",
        "ibm_kyoto": "cross", "ibm_osaka": "diamond", "ibm_brussels": "triangle-up",
        "ibm_strasbourg": "diamond-open"
    }
    
    linestyles_100q = {
        "ibm_torino-v1": "dash", "ibm_torino-v0": "dash", "ibm_fez": "dash"
    }
    
    fig_100q = go.Figure()
    
    # Plot each 100q backend
    backend_order_100q = ["ibm_boston", "ibm_marrakesh", "ibm_fez", "ibm_torino-v1", 
                         "ibm_torino-v0", "ibm_brisbane", "ibm_sherbrooke", "ibm_kyiv",
                         "ibm_nazca", "ibm_kyoto", "ibm_osaka", "ibm_brussels", "ibm_strasbourg"]
    
    for backend_name in backend_order_100q:
        if backend_name not in results_100q:
            continue
        data = results_100q[backend_name]
        
        fig_100q.add_trace(go.Scatter(
            x=data["p_values"],
            y=data["r_values"],
            mode='lines+markers',
            name=backend_name,
            marker=dict(
                symbol=markers_100q.get(backend_name, "circle"),
                size=8,
                color=colors_100q.get(backend_name, "#808080"),
                line=dict(color='black', width=1)
            ),
            line=dict(
                color=colors_100q.get(backend_name, "#808080"),
                width=2,
                dash=linestyles_100q.get(backend_name, "solid")
            ),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                          'p: %{x}<br>' +
                          'r: %{y:.3f}<br>' +
                          '<extra></extra>'
        ))
    
    # Add random baseline for 100q
    if results_100q:
        for backend_name in results_100q:
            if "random_r" in results_100q[backend_name]:
                random_baseline = results_100q[backend_name]["random_r"]
                y1 = random_baseline
                y2 = 0.02
                
                fig_100q.add_trace(go.Scatter(
                    x=[1, 100],
                    y=[y1-y2, y1-y2],
                    fill=None,
                    mode='lines',
                    line=dict(color='rgba(128,128,128,0)', width=0),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                fig_100q.add_trace(go.Scatter(
                    x=[1, 100],
                    y=[y1+y2, y1+y2],
                    fill='tonexty',
                    mode='lines',
                    line=dict(color='rgba(128,128,128,0)', width=0),
                    fillcolor='rgba(128,128,128,0.3)',
                    name='random baseline',
                    hovertemplate='Random baseline<br>r: %{y:.3f}<extra></extra>'
                ))
                break
    
    fig_100q.update_layout(
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
    
    st.plotly_chart(fig_100q, use_container_width=True)
    
    # Statistics table for 100q
    stats_100q = []
    for backend_name in backend_order_100q:
        if backend_name not in results_100q:
            continue
        data = results_100q[backend_name]
        stats_100q.append({
            "Backend": backend_name,
            "Qubits": data["qubits"],
            "Max r": f"{data['max_r']:.3f}",
            "Optimal p": data["optimal_p"],
            "p range": f"{min(data['p_values'])}-{max(data['p_values'])}"
        })
    
    if stats_100q:
        st.dataframe(pd.DataFrame(stats_100q), use_container_width=True, hide_index=True)


