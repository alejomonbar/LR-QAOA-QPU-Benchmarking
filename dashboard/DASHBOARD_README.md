# LR-QAOA QPU Benchmarking Dashboard (legacy)

> **The public results now live on the website: <https://alejomonbar.github.io/LR-QAOA-QPU-Benchmarking/>.**
> It is a static page rebuilt by GitHub Actions on every push to `main`, so it never needs waking up. See the [Website section of the main README](../README.md#-website).

This folder keeps the earlier Streamlit dashboard for local, interactive exploration of the same `Data/` files.

## Run it locally

```bash
pip install -r requirements.txt
cd dashboard
streamlit run dashboard.py      # opens http://localhost:8501
```

## Features

- Interactive Plotly charts: zoom, pan, and hover for details
- Filters by backend, number of qubits and QAOA layers
- Views: performance vs QAOA layers, backend comparison, optimal-solution probability, and a raw data table with CSV export
- Reads new `.npy` files from `Data/` on refresh

## Data structure

The dashboard expects `.npy` files with this structure:

```python
{
    'nq': int,        # number of qubits
    'ps': list,       # QAOA layers tested
    'postprocessing': {
        delta: {
            p: {
                'r': float,            # approximation ratio
                'probability': float,  # probability of the optimal solution
                ...
            }
        }
    }
}
```

## Resources

- [Streamlit documentation](https://docs.streamlit.io)
- [Plotly documentation](https://plotly.com/python/)
