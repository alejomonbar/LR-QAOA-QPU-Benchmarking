import streamlit as st
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import os
from pathlib import Path
import networkx as nx

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
Interactive dashboard for comparing QAOA performance across different quantum processors.
Click on data points to see detailed information, zoom in/out, and filter by backend.
""")

# Function to load all results from Data directory
@st.cache_data
def load_all_results():
    """Load all benchmark results from the Data directory"""
    data_dir = Path("../Data")
    results_dict = {}
    
    # Scan all subdirectories for .npy files
    for backend_dir in data_dir.iterdir():
        if backend_dir.is_dir() and backend_dir.name != "__pycache__":
            backend_name = backend_dir.name
            results_dict[backend_name] = {}
            
            # Load all .npy files in this backend directory
            for npy_file in backend_dir.glob("*.npy"):
                try:
                    result = np.load(npy_file, allow_pickle=True).item()
                    # Extract number of qubits from filename or result
                    nq = result.get('nq', npy_file.stem.split('_')[0])
                    experiment_type = npy_file.stem
                    results_dict[backend_name][experiment_type] = result
                except Exception as e:
                    st.sidebar.warning(f"Could not load {npy_file}: {e}")
    
    return results_dict

# Function to extract approximation ratios
def extract_metrics(results_dict):
    """Extract key metrics from all results for easy plotting"""
    metrics_list = []
    
    for backend_name, experiments in results_dict.items():
        for exp_name, result in experiments.items():
            if 'postprocessing' not in result or 'ps' not in result:
                continue
                
            nq = result.get('nq', 0)
            ps = result.get('ps', [])
            
            # Handle different delta structures
            postproc = result['postprocessing']
            
            for delta in postproc.keys():
                for p in ps:
                    if p in postproc[delta]:
                        p_result = postproc[delta][p]
                        
                        # Handle different result structures
                        if isinstance(p_result, dict):
                            if 'r' in p_result:  # Single result
                                r = p_result['r']
                                prob = p_result.get('probability', 0)
                            elif isinstance(list(p_result.values())[0], dict):  # Multiple sections
                                # Average over sections
                                r_values = [p_result[sec]['r'] for sec in p_result if isinstance(p_result[sec], dict) and 'r' in p_result[sec]]
                                r = np.mean(r_values) if r_values else 0
                                prob_values = [p_result[sec].get('probability', 0) for sec in p_result if isinstance(p_result[sec], dict)]
                                prob = np.mean(prob_values) if prob_values else 0
                            else:
                                continue
                        else:
                            continue
                        
                        metrics_list.append({
                            'backend': backend_name,
                            'experiment': exp_name,
                            'n_qubits': nq,
                            'p_layers': p,
                            'delta': delta,
                            'approximation_ratio': r,
                            'optimal_probability': prob
                        })
    
    return pd.DataFrame(metrics_list)

# Load data
with st.spinner("Loading benchmark results..."):
    results_dict = load_all_results()
    df_metrics = extract_metrics(results_dict)

# Sidebar filters
st.sidebar.header("🔧 Filters")

# Backend filter
available_backends = sorted(df_metrics['backend'].unique())
selected_backends = st.sidebar.multiselect(
    "Select Backends",
    available_backends,
    default=available_backends[:min(5, len(available_backends))]
)

# Qubit range filter
if len(df_metrics) > 0:
    min_qubits = int(df_metrics['n_qubits'].min())
    max_qubits = int(df_metrics['n_qubits'].max())
    qubit_range = st.sidebar.slider(
        "Number of Qubits",
        min_qubits, max_qubits,
        (min_qubits, max_qubits)
    )
else:
    qubit_range = (0, 100)

# P-layers range filter
if len(df_metrics) > 0:
    min_p = int(df_metrics['p_layers'].min())
    max_p = int(df_metrics['p_layers'].max())
    p_range = st.sidebar.slider(
        "QAOA Layers (p)",
        min_p, max_p,
        (min_p, max_p)
    )
else:
    p_range = (0, 100)

# Apply filters
df_filtered = df_metrics[
    (df_metrics['backend'].isin(selected_backends)) &
    (df_metrics['n_qubits'] >= qubit_range[0]) &
    (df_metrics['n_qubits'] <= qubit_range[1]) &
    (df_metrics['p_layers'] >= p_range[0]) &
    (df_metrics['p_layers'] <= p_range[1])
]

# Display summary statistics
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Summary")
st.sidebar.metric("Total Experiments", len(df_filtered))
st.sidebar.metric("Backends", len(selected_backends))
st.sidebar.metric("Avg. Approx. Ratio", f"{df_filtered['approximation_ratio'].mean():.3f}" if len(df_filtered) > 0 else "N/A")

# Main content area
tab1, tab2, tab3, tab4 = st.tabs(["📈 Performance vs Layers", "🔬 Backend Comparison", "🎯 Optimal Probability", "📋 Data Table"])

with tab1:
    st.subheader("Approximation Ratio vs QAOA Layers")
    
    if len(df_filtered) > 0:
        # Create interactive plot
        fig = go.Figure()
        
        # Group by backend and n_qubits
        for backend in selected_backends:
            backend_data = df_filtered[df_filtered['backend'] == backend]
            
            for nq in backend_data['n_qubits'].unique():
                nq_data = backend_data[backend_data['n_qubits'] == nq]
                
                # Sort by p_layers
                nq_data = nq_data.sort_values('p_layers')
                
                fig.add_trace(go.Scatter(
                    x=nq_data['p_layers'],
                    y=nq_data['approximation_ratio'],
                    mode='lines+markers',
                    name=f"{backend} (n={nq})",
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>" +
                        "QAOA Layers: %{x}<br>" +
                        "Approx. Ratio: %{y:.4f}<br>" +
                        "<extra></extra>"
                    ),
                    marker=dict(size=8),
                    line=dict(width=2)
                ))
        
        fig.update_layout(
            xaxis_title="QAOA Layers (p)",
            yaxis_title="Approximation Ratio",
            hovermode='closest',
            height=600,
            template="plotly_white",
            legend=dict(
                yanchor="bottom",
                y=0.01,
                xanchor="right",
                x=0.99
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for selected filters.")

with tab2:
    st.subheader("Backend Performance Comparison")
    
    if len(df_filtered) > 0:
        # Create box plot for backend comparison
        fig = px.box(
            df_filtered,
            x='backend',
            y='approximation_ratio',
            color='backend',
            points='all',
            hover_data=['n_qubits', 'p_layers', 'experiment'],
            labels={
                'approximation_ratio': 'Approximation Ratio',
                'backend': 'Backend'
            }
        )
        
        fig.update_layout(
            height=600,
            showlegend=False,
            template="plotly_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Summary statistics table
        st.subheader("Backend Statistics")
        stats = df_filtered.groupby('backend')['approximation_ratio'].agg([
            ('Mean', 'mean'),
            ('Median', 'median'),
            ('Std Dev', 'std'),
            ('Min', 'min'),
            ('Max', 'max'),
            ('Count', 'count')
        ]).round(4)
        st.dataframe(stats, use_container_width=True)
    else:
        st.info("No data available for selected filters.")

with tab3:
    st.subheader("Probability of Finding Optimal Solution")
    
    if len(df_filtered) > 0:
        # Create scatter plot with size based on probability
        fig = go.Figure()
        
        for backend in selected_backends:
            backend_data = df_filtered[df_filtered['backend'] == backend]
            
            for nq in backend_data['n_qubits'].unique():
                nq_data = backend_data[backend_data['n_qubits'] == nq]
                nq_data = nq_data.sort_values('p_layers')
                
                fig.add_trace(go.Scatter(
                    x=nq_data['p_layers'],
                    y=nq_data['optimal_probability'],
                    mode='lines+markers',
                    name=f"{backend} (n={nq})",
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>" +
                        "QAOA Layers: %{x}<br>" +
                        "Probability: %{y:.4f}<br>" +
                        "<extra></extra>"
                    ),
                    marker=dict(size=8),
                    line=dict(width=2)
                ))
        
        fig.update_layout(
            xaxis_title="QAOA Layers (p)",
            yaxis_title="Probability of Optimal Solution",
            hovermode='closest',
            height=600,
            template="plotly_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for selected filters.")

with tab4:
    st.subheader("Raw Data Table")
    
    if len(df_filtered) > 0:
        # Display options
        col1, col2 = st.columns(2)
        with col1:
            sort_by = st.selectbox(
                "Sort by",
                ['approximation_ratio', 'backend', 'n_qubits', 'p_layers', 'optimal_probability']
            )
        with col2:
            ascending = st.checkbox("Ascending", value=False)
        
        # Display table
        display_df = df_filtered.sort_values(sort_by, ascending=ascending)
        st.dataframe(
            display_df.style.format({
                'approximation_ratio': '{:.4f}',
                'optimal_probability': '{:.4f}'
            }),
            use_container_width=True,
            height=600
        )
        
        # Download button
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="qaoa_benchmarks.csv",
            mime="text/csv"
        )
    else:
        st.info("No data available for selected filters.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>LR-QAOA QPU Benchmarking Dashboard | Built with Streamlit & Plotly</p>
    <p style='font-size: 0.8em'>Update: Add new .npy files to the Data directory and refresh the page</p>
</div>
""", unsafe_allow_html=True)
