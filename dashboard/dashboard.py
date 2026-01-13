import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from pathlib import Path
from collections import defaultdict
import json

# Function to load 1D chain results
@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_1d_chain_results():
    """Load 1D chain experiment results for 5q and 100q comparisons from JSON"""
    data_dir = Path(__file__).parent.parent / "Data"
    
    try:
        json_path = data_dir / "1d_chain_processed.json"
        # Add file timestamp to force cache invalidation when file changes
        file_mtime = json_path.stat().st_mtime
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Verify data structure
        if not data.get("5q") and not data.get("100q"):
            st.warning("⚠️ Loaded empty data structure")
        
        return data
    except Exception as e:
        st.error(f"Error loading 1D chain data: {str(e)}")
        return {"5q": {}, "100q": {}}


# Function to load native layout results
@st.cache_data(ttl=600)
def load_nl_results():
    """Load native layout experiment results from JSON"""
    data_dir = Path(__file__).parent.parent / "Data"
    
    try:
        json_path = data_dir / "native_layout_processed.json"
        # Add file timestamp to force cache invalidation when file changes
        file_mtime = json_path.stat().st_mtime
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Verify data loaded
        if not data:
            st.warning("⚠️ Loaded empty native layout data")
        
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


def compute_dataset_insights():
    """Compute combined statistics from all processed datasets"""
    # Use st.cache_data for speed
    @st.cache_data(ttl=600)
    def _get_stats():
        try:
            # Current file is in dashboard/, Data/ is in root
            data_dir = Path(__file__).parent.parent / "Data"
            
            unique_qpus = set()
            vendors = set()
            max_depth = 0
            
            vendor_map = {
                "ibm": "IBM", "ionq": "IonQ", "iqm": "IQM", 
                "h1": "Quantinuum", "h2": "Quantinuum", 
                "aqt": "AQT", "rigetti": "Rigetti", "origin": "OriginQ"
            }
            
            def get_vendor(name):
                name_lower = name.lower()
                for k, v in vendor_map.items():
                    if k in name_lower:
                        return v
                return "Other"

            def get_base_name(name):
                return name.replace("-f", "").replace("-v0", "").replace("-v1", "").replace("_NL", "")

            # 1. Process FC Data
            fc_path = data_dir / "fc_processed.json"
            if fc_path.exists():
                with open(fc_path, "r") as f:
                    fc_data = json.load(f)
                for b_name, entries in fc_data.items():
                    if b_name == "qasm_simulator" or not isinstance(entries, dict):
                        continue
                    unique_qpus.add(get_base_name(b_name))
                    vendors.add(get_vendor(b_name))
                    for nq_data in entries.values():
                        if isinstance(nq_data, dict):
                            r_vs_p = nq_data.get("r_vs_p", {})
                            if isinstance(r_vs_p, dict) and r_vs_p:
                                ps = r_vs_p.get("p_values", [])
                                if ps:
                                    max_depth = max(max_depth, max(ps))

            # 2. Process NL Data
            nl_path = data_dir / "native_layout_processed.json"
            if nl_path.exists():
                with open(nl_path, "r") as f:
                    nl_data = json.load(f)
                for b_name, entries in nl_data.items():
                    if "simulator" in b_name.lower() or not isinstance(entries, dict):
                        continue
                    unique_qpus.add(get_base_name(b_name))
                    vendors.add(get_vendor(b_name))
                    ps = entries.get("p_values", [])
                    if ps:
                        max_depth = max(max_depth, max(ps))

            # 3. Process 1D Data
            one_d_path = data_dir / "1d_chain_processed.json"
            if one_d_path.exists():
                with open(one_d_path, "r") as f:
                    one_d_data = json.load(f)
                for q_key in ["5q", "100q"]:
                    q_data = one_d_data.get(q_key, {})
                    for b_name in q_data.keys():
                        if "simulator" in b_name.lower():
                            continue
                        unique_qpus.add(get_base_name(b_name))
                        vendors.add(get_vendor(b_name))

            if not unique_qpus:
                return None
                
            return {
                "qpus": len(unique_qpus),
                "vendors": len(vendors),
                "vendor_list": ", ".join(sorted(vendors)),
                "max_depth": max_depth
            }
        except Exception:
            return None
            
    return _get_stats()


# Set page configuration
logo_path = Path(__file__).parent / "Logo.png"
fc_logo = Path(__file__).parent / "FC-logo.png"
nl_logo = Path(__file__).parent / "NL-logo.png"
one_d_logo = Path(__file__).parent / "1D-logo.png"

st.set_page_config(
    page_title="LR-QAOA QPU Benchmarking",
    page_icon=str(logo_path) if logo_path.exists() else "🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for improved tab styling
st.markdown("""
<style>
    /* Sidebar styling - enhanced */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
        border-right: 2px solid #dee2e6;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 2rem;
    }
    
    /* Sidebar section styling */
    [data-testid="stSidebar"] .element-container {
        background-color: transparent;
    }
    
    [data-testid="stSidebar"] h3 {
        color: #495057;
        font-weight: 700;
        font-size: 1.1rem;
        margin-top: 1rem;
        padding: 8px 12px;
        background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
    
    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, #dee2e6, transparent);
    }
    
    [data-testid="stSidebar"] a {
        color: #667eea;
        font-weight: 500;
        text-decoration: none;
        transition: all 0.2s ease;
    }
    
    [data-testid="stSidebar"] a:hover {
        color: #764ba2;
        text-decoration: underline;
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        font-size: 0.95rem;
        line-height: 1.6;
    }
    
    /* Tab styling - centered and evenly distributed */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 12px;
        display: flex;
        justify-content: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    .stTabs [data-baseweb="tab"] {
        flex: 1;
        height: 55px;
        background-color: white;
        border-radius: 8px;
        padding: 0px 32px;
        font-weight: 600;
        font-size: 1.05rem;
        border: 2px solid #e0e0e0;
        transition: all 0.3s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        border-color: #667eea;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: 2px solid #667eea !important;
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4) !important;
    }
    
    /* Main content styling */
    .main .block-container {
        padding-top: 2rem;
        max-width: 100%;
    }
    
    /* Card-like sections */
    div[data-testid="stExpander"] {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Main content area with title
st.markdown("""
    <div style="
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 20px;
        padding: 40px 30px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.3);
    ">
        <h1 style="
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 700;
            font-size: 3rem;
            margin: 0;
            letter-spacing: -0.5px;
        ">LR-QAOA QPU Benchmarking Results</h1>
        <p style="
            text-align: center;
            color: #64748b;
            font-size: 1.1rem;
            margin-top: 12px;
            margin-bottom: 0;
        ">Large-scale quantum processor performance evaluation</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar with description and summary
with st.sidebar:
    # Title first
    # Title first with logo as background
    st.markdown(f"""
        <div style="
            background-image: url('https://raw.githubusercontent.com/alejomonbar/LR-QAOA-QPU-Benchmarking/main/dashboard/Logo.png');
            background-size: contain;
            background-position: center;
            background-repeat: no-repeat;
            padding: 60px 20px;
            border-radius: 12px;
            margin: 1rem 0;
        ">
            <h1 style="
                text-align: center;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-weight: 700;
                font-size: 1.8rem;
                margin: 0;
                letter-spacing: -0.3px;
                text-shadow: 0 0 20px rgba(255, 255, 255, 0.8);
            ">LR-QAOA QPU Benchmarking</h1>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("""
    ### About
    
    This dashboard benchmarks **Linear Ramp QAOA (LR-QAOA)** — a fixed-parameter, deterministic variant of QAOA 
    that quantifies a QPU's ability to preserve coherent signal as circuit depth increases.
    
    The protocol scales to large width and depth, enabling cross-platform comparisons of algorithmic performance.
    """)
    
    st.markdown("---")
    
    # Get dataset insights
    insights = compute_dataset_insights()
    
    if insights:
        vendors_text = f"{insights['vendors']} vendors ({insights['vendor_list']})"
        qpus_text = f"{insights['qpus']} quantum processors"
    else:
        vendors_text = "7 vendors (AQT, IBM, IonQ, IQM, OriginQ, Quantinuum, Rigetti)"
        qpus_text = "29 quantum processors"
    
    st.markdown(f"""
    ### Key Features
    
    - 🔬 **{qpus_text}** from **{vendors_text}**
    - 📊 **QPUs with up to 156 qubits** tested
    - 📈 **Up to 10,000 QAOA layers** in depth scaling
    - 🌐 **3 topologies**: 1D chains, native layouts, fully connected
    - 🏆 **Best performers**: Quantinuum H1-1E (FC), IBM Boston (NL/1D)
    """)
    
    st.markdown("---")
    
    st.markdown("""
    ### Reference
    
    📄 [*Evaluating the performance of quantum processing units at large width and depth*](https://arxiv.org/abs/2502.06471)
    """)
    
    st.markdown("---")

    st.caption("Developed by Alejandro Montanez-Barrera")
    st.caption("Institute for Advanced Simulation (IAS), Jülich Supercomputing Centre (JSC), Forschungszentrum Jülich")
    st.caption("Website: [alejomonbar.github.io](https://alejomonbar.github.io)")
    st.caption("LR-QAOA • Quantum optimization • QPU benchmarking")

# Create tabs with icons
tab1, tab2, tab3 = st.tabs(["Fully Connected", "Native Layout", "1D Chain"])

# Tab 1: Fully Connected Experiments
with tab1:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 20px; padding: 20px 0;">
            <img src="https://raw.githubusercontent.com/alejomonbar/LR-QAOA-QPU-Benchmarking/main/dashboard/FC-logo.png" width="80" style="border-radius: 10px;">
            <h1 style="margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-weight: 700;">Fully Connected Graph Experiments</h1>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    Effective approximation ratio vs number of qubits for fully connected graphs.
    Results are normalized against random sampling baseline (3σ threshold).
    """)
    
    r_data, backends, debug_info, fc_data = load_fc_results()

    # Define colors and markers
    colors_map = {
        "aqt_ibexq1": "#e41a1c", "ibm_boston": "#e41a1c", "ionq_forte": "#8dd3c7",
        "ibm_torino": "#fdb462", "ibm_brisbane": "#bebada", "H1-1E": "#fb8072",
        "qasm_simulator": "#8A2BE2", "H2-1E": "#fdb462", "ibm_fez": "#b3de69",
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
        # Define vendor color palette
        vendor_colors = {
            "aqt": "#FF4500",      # Vibrant orange-red
            "ibm": "#00A8E1",      # Bright cyan-blue
            "ionq": "#9D4EDD",     # Vivid purple
            "quantinuum": "#06D6A0", # Bright teal-green
            "iqm": "#EF476F",      # Hot pink-red
            "rigetti": "#7209B7",  # Deep vibrant purple
            "originq": "#FFB627"   # Golden yellow
        }
        
        def get_vendor_name(backend_name):
            """Extract vendor from backend name"""
            # Special case for qasm_simulator - it's not a vendor
            if backend_name == "qasm_simulator":
                return "simulator"
            for vendor in vendor_colors:
                if backend_name.lower().startswith(vendor):
                    return vendor
                if vendor in backend_name.lower().replace("_", "").replace("-", ""):
                    return vendor
            return "other"
        
        def get_vendor_color(backend_name):
            """Extract vendor from backend name and return color"""
            # Special case for qasm_simulator
            if backend_name == "qasm_simulator":
                return "#FFD700"  # Gold/yellow - distinct from all vendor colors
            vendor = get_vendor_name(backend_name)
            return vendor_colors.get(vendor, "#808080")
        
        # Calculate max qubits per vendor for sorting
        vendor_max_qubits = {}
        for item in timeline_data:
            vendor = get_vendor_name(item["backend"])
            if vendor not in vendor_max_qubits:
                vendor_max_qubits[vendor] = item["max_qubits"]
            else:
                vendor_max_qubits[vendor] = max(vendor_max_qubits[vendor], item["max_qubits"])
        
        # Sort timeline data by vendor's max qubits (descending), then by backend name
        timeline_data_sorted = sorted(timeline_data, key=lambda x: (-vendor_max_qubits.get(get_vendor_name(x["backend"]), 0), x["backend"]))
        
        # Group data by vendor for connecting lines
        vendor_groups = {}
        for item in timeline_data_sorted:
            vendor = get_vendor_name(item["backend"])
            if vendor not in vendor_groups:
                vendor_groups[vendor] = []
            vendor_groups[vendor].append(item)
        
        # Create timeline plot
        fig_timeline = go.Figure()
        
        # Add subtle connecting lines for each vendor
        for vendor, items in vendor_groups.items():
            if len(items) > 1:  # Only add line if vendor has multiple devices
                items_sorted = sorted(items, key=lambda x: x["date"])
                vendor_color = get_vendor_color(items[0]["backend"])
                fig_timeline.add_trace(go.Scatter(
                    x=[item["date"] for item in items_sorted],
                    y=[item["max_qubits"] for item in items_sorted],
                    mode='lines',
                    line=dict(color=vendor_color, width=2, dash='dash'),
                    opacity=0.5,
                    showlegend=False,
                    hoverinfo='skip'
                ))
        
        # Add markers for each backend
        for item in timeline_data_sorted:
            vendor_color = get_vendor_color(item["backend"])
            fig_timeline.add_trace(go.Scatter(
                x=[item["date"]],
                y=[item["max_qubits"]],
                mode='markers',
                name=item["backend"],
                marker=dict(
                    symbol=markers_map.get(item["backend"], "circle"),
                    size=14,
                    color=vendor_color,
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
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 20px; padding: 20px 0;">
            <img src="https://raw.githubusercontent.com/alejomonbar/LR-QAOA-QPU-Benchmarking/main/dashboard/NL-logo.png" width="80" style="border-radius: 10px;">
            <h1 style="margin: 0; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-weight: 700;">Native Layout Experiments</h1>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    Approximation ratio vs QAOA layers for hardware-native graph topologies.
    Testing large-scale IBM Eagle and Heron processors with native connectivity.
    """)
    
    nl_data = load_nl_results()
    
    if not nl_data:
        st.warning("⚠️ No native layout data loaded. Please check if Data/native_layout_processed.json exists.")
    else:
        st.caption(f"📊 Loaded {len(nl_data)} backends for native layout comparison")
    
    # Color definitions for native layout
    colors_nl = {
        # 127q Eagle (shades of purple/lavender)
        "ibm_brisbane": "#bebada", "ibm_brussels": "#c8b8e0",
        "ibm_kyiv": "#d4c4e6", "ibm_kyoto": "#e0d0ec",
        "ibm_nazca": "#a89fcc", "ibm_osaka": "#bdb4d8", 
        "ibm_sherbrooke": "#cab9e2", "ibm_strasbourg": "#d2cae4",
        # 133q Heron-r1 (shades of orange)
        "ibm_torino-v0": "#fdb462", "ibm_torino-v1": "#fdb462", "ibm_torino-f": "#fdb462",
        # 156q Heron-r2 (various colors)
        "ibm_fez": "#b3de69", "ibm_fez-f": "#b3de69",
        "ibm_marrakesh-f": "#ffed6f",
        "ibm_marrakesh-f": "#ffed6f", "ibm_aachen-f": "#e41a1c",
        "ibm_kingston-f": "#377eb8", "ibm_boston-f": "#984ea3",
        # IQM devices
        "iqm_garnet": "#fb8072", "iqm_emerald": "#80b1d3", "iqm_emerald_NL": "#377eb8",
        # Rigetti and IonQ and OriginQ
        "rigetti_ankaa_3": "#fccde5", "ionq_forte_enterprise": "#ccebc5", "originq_wukong": "#ffed6f"
    }
    
    markers_nl = {
        # 127q devices - diamond variants
        "ibm_brisbane": "diamond", "ibm_brussels": "diamond-open",
        "ibm_kyiv": "diamond-tall", "ibm_kyoto": "diamond-wide",
        "ibm_osaka": "diamond-cross", "ibm_strasbourg": "diamond",
        # 133q devices
        "ibm_torino-v0": "circle", "ibm_torino-v1": "cross", "ibm_torino-f": "square",
        # 156q devices
        "ibm_fez": "triangle-up", "ibm_fez-f": "star",
        "ibm_marrakesh-f": "circle-open", "ibm_aachen-f": "triangle-down",
        "ibm_kingston-f": "triangle-down", "ibm_boston-f": "circle",
        # IQM, Rigetti, IonQ, OriginQ
        "iqm_garnet": "diamond-open", "iqm_emerald": "circle", "iqm_emerald_NL": "triangle-up",
        "rigetti_ankaa_3": "diamond-tall", "ionq_forte_enterprise": "triangle-down",
        "originq_wukong": "star"
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
        "iqm_garnet", "rigetti_ankaa_3", "iqm_emerald", "iqm_emerald_NL", "ionq_forte_enterprise", "originq_wukong",
        # 127q Eagle devices
        "ibm_brisbane", "ibm_brussels", "ibm_kyiv", "ibm_kyoto", "ibm_nazca", "ibm_osaka", "ibm_sherbrooke", "ibm_strasbourg",
        # 133q Heron-r1 devices
        "ibm_torino-v0", "ibm_torino-v1", "ibm_torino-f",
        # 156q Heron-r2 devices
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
    
    # ========== IBM DEVICES COMPARISON ==========
    st.markdown("---")
    st.subheader("IBM Quantum Processors Comparison")
    st.markdown("Comparing IBM Eagle and Heron processors across different configurations on native layout problems.")
    
    # Filter for IBM devices only
    ibm_backends = [b for b in backend_order_nl if b.startswith("ibm_")]
    
    # Enhanced color scheme for IBM devices
    colors_ibm = {
        # 127q Eagle (shades of purple/lavender)
        "ibm_brisbane": "#bebada", "ibm_brussels": "#c8b8e0",
        "ibm_kyiv": "#d4c4e6", "ibm_kyoto": "#e0d0ec",
        "ibm_nazca": "#a89fcc", "ibm_osaka": "#bdb4d8", 
        "ibm_sherbrooke": "#cab9e2", "ibm_strasbourg": "#d2cae4",
        # 133q Heron-r1 (shades of orange)
        "ibm_torino-v0": "#fdb462", "ibm_torino-v1": "#fb8072", "ibm_torino-f": "#ff7f00",
        # 156q Heron-r2
        "ibm_fez": "#b3de69", "ibm_fez-f": "#8dd3c7",
        "ibm_marrakesh-f": "#ffed6f", 
        "ibm_aachen-f": "#e41a1c", "ibm_kingston-f": "#377eb8", 
        "ibm_boston-f": "#984ea3"
    }
    
    markers_ibm = {
        # 127q devices - diamond variants
        "ibm_brisbane": "diamond", "ibm_brussels": "diamond-open",
        "ibm_kyiv": "diamond-tall", "ibm_kyoto": "diamond-wide",
        "ibm_nazca": "diamond-tall-open", "ibm_osaka": "diamond-cross", 
        "ibm_sherbrooke": "diamond-wide-open", "ibm_strasbourg": "diamond",
        # 133q and 156q devices
        "ibm_torino-v0": "circle", "ibm_torino-v1": "cross", "ibm_torino-f": "square",
        "ibm_fez": "triangle-up", "ibm_fez-f": "star",
        "ibm_marrakesh-f": "circle-open", 
        "ibm_aachen-f": "triangle-down", "ibm_kingston-f": "x",
        "ibm_boston-f": "pentagon"
    }
    
    linestyles_ibm = {
        "ibm_torino-v0": "dash", "ibm_torino-v1": "dash", "ibm_torino-f": "dash",
        "ibm_fez": "solid", "ibm_fez-f": "dash",
        "ibm_marrakesh-f": "dash", "ibm_aachen-f": "dash", 
        "ibm_kingston-f": "dash", "ibm_boston-f": "dash"
    }
    
    fig_ibm = go.Figure()
    
    for backend_name in ibm_backends:
        if backend_name not in nl_data:
            continue
        data = nl_data[backend_name]
        
        fig_ibm.add_trace(go.Scatter(
            x=data["p_values"],
            y=data["r_values"],
            mode='lines+markers',
            name=backend_name,
            marker=dict(
                symbol=markers_ibm.get(backend_name, "circle"),
                size=8,
                color=colors_ibm.get(backend_name, "#808080"),
                line=dict(color='black', width=1)
            ),
            line=dict(
                color=colors_ibm.get(backend_name, "#808080"),
                width=2,
                dash=linestyles_ibm.get(backend_name, "solid")
            ),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                          f'Qubits: {data["qubits"]}<br>' +
                          'p: %{x}<br>' +
                          'r: %{y:.3f}<br>' +
                          '<extra></extra>'
        ))
        
        # Add random baseline line if available
        if data.get("has_random") and "random_r" in data:
            fig_ibm.add_trace(go.Scatter(
                x=data["p_values"],
                y=[data["random_r"]] * len(data["p_values"]),
                mode='lines',
                line=dict(color=colors_ibm.get(backend_name, "#808080"), dash="dot", width=1),
                showlegend=False,
                hoverinfo='skip'
            ))
    
    # Add legend for random baseline
    fig_ibm.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='lines',
        line=dict(color='black', dash='dot', width=1),
        name='random baseline',
        showlegend=True
    ))
    
    fig_ibm.update_layout(
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
    
    st.plotly_chart(fig_ibm, use_container_width=True, key="nl_ibm_comparison_plot")
    
    # IBM Statistics table
    st.subheader("IBM Processor Statistics")
    stats_ibm = []
    for backend_name in ibm_backends:
        if backend_name not in nl_data:
            continue
        data = nl_data[backend_name]
        
        # Determine processor type
        if "brisbane" in backend_name or "brussels" in backend_name or "kyiv" in backend_name or "kyoto" in backend_name or "nazca" in backend_name or "osaka" in backend_name or "sherbrooke" in backend_name or "strasbourg" in backend_name:
            proc_type = "Eagle (127q)"
        elif "torino" in backend_name:
            proc_type = "Heron-r1 (133q)"
        elif "fez" in backend_name or "marrakesh" in backend_name or "aachen" in backend_name or "kingston" in backend_name or "boston" in backend_name or "pittsburgh" in backend_name:
            proc_type = "Heron-r2 (156q)"
        else:
            proc_type = "Unknown"
        
        stats_ibm.append({
            "Backend": backend_name,
            "Processor": proc_type,
            "Qubits Used": data["qubits"],
            "Max r": f"{data['max_r']:.3f}",
            "Optimal p": data["optimal_p"],
            "p Range": f"{min(data['p_values'])}-{max(data['p_values'])}"
        })
    
    if stats_ibm:
        st.dataframe(pd.DataFrame(stats_ibm), use_container_width=True, hide_index=True)


# Tab 3: 1D Chain Experiments
with tab3:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 20px; padding: 20px 0;">
            <img src="https://raw.githubusercontent.com/alejomonbar/LR-QAOA-QPU-Benchmarking/main/dashboard/1D-logo.png" width="80" style="border-radius: 10px;">
            <h1 style="margin: 0; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-weight: 700;">1D Chain Experiments</h1>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    Approximation ratio vs QAOA layers (p) for 1D chain graphs at different scales.
    """)
    
    chain_results = load_1d_chain_results()
    
    # Debug: Show what was loaded
    if not chain_results or (not chain_results.get("5q") and not chain_results.get("100q")):
        st.warning("⚠️ No 1D chain data loaded. Please check if Data/1d_chain_processed.json exists.")
    
    # ========== 5 QUBIT EXPERIMENTS ==========
    st.subheader("5-Qubit Comparison")
    st.markdown("Comparing multiple QPUs on small-scale 1D chain problems.")
    
    results_5q = chain_results.get("5q", {})
    
    if not results_5q:
        st.info("No 5-qubit data available.")
    else:
        st.caption(f"📊 Loaded {len(results_5q)} backends for 5-qubit comparison")
    
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
    
    st.plotly_chart(fig_5q, use_container_width=True, key="1d_chain_5q_plot")
    
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
    
    if not results_100q:
        st.info("No 100-qubit data available.")
    else:
        st.caption(f"📊 Loaded {len(results_100q)} backends for 100-qubit comparison")
    
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
    
    st.plotly_chart(fig_100q, use_container_width=True, key="1d_chain_100q_plot")
    
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


