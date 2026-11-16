# Deployment

The results are published as a static website, not as this Streamlit app:

**<https://alejomonbar.github.io/LR-QAOA-QPU-Benchmarking/>**

- The site's source is in [`site/`](../site), and its data is built from `Data/` by [`scripts/build_site_data.py`](../scripts/build_site_data.py).
- The [GitHub Actions workflow](../.github/workflows/site.yml) rebuilds and deploys it to GitHub Pages on every push to `main` that touches `Data/`, `site/` or the build script. No separate deployment step is needed.
- To publish a new result, commit its `.npy` file under `Data/<backend>/` and push. The steps are in the [Website section of the main README](../README.md#-website).

The Streamlit dashboard in this folder is only for local use; see [DASHBOARD_README.md](DASHBOARD_README.md).
