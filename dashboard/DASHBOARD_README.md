# LR-QAOA QPU Benchmarking Dashboard

Interactive web dashboard for visualizing and comparing QAOA performance across different quantum processors.

## 🌐 **View Online (Recommended)**

**No installation needed!** Visit the live dashboard at:
👉 **[Your Dashboard URL will be here after deployment]**

## 🚀 Quick Start (Local Development)

### Run Locally

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the dashboard:
```bash
cd dashboard
streamlit run dashboard.py
```

3. Open your browser to `http://localhost:8501`

## 📊 Features

- **Interactive Plots**: Zoom, pan, and click on data points to see detailed information
- **Real-time Filtering**: Filter by backend, number of qubits, and QAOA layers
- **Multiple Views**:
  - Performance vs QAOA Layers
  - Backend Comparison (box plots)
  - Optimal Solution Probability
  - Raw Data Table with CSV export
- **Easy Updates**: Just add new `.npy` files to the `Data/` directory and refresh

## 🌐 Deploy to Streamlit Cloud (Free)

**Make your dashboard publicly accessible in 5 minutes:**

### Step 1: Push to GitHub

Make sure your code is pushed to GitHub:
```bash
cd /path/to/LR-QAOA-QPU-Benchmarking
git add dashboard/
git add Data/  # Include your results
git commit -m "Add interactive dashboard"
git push
```

### Step 2: Deploy on Streamlit Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io)**
2. Click **"New app"**
3. Sign in with GitHub
4. Fill in the deployment form:
   - **Repository**: `your-username/LR-QAOA-QPU-Benchmarking`
   - **Branch**: `main` (or your branch name)
   - **Main file path**: `dashboard/dashboard.py`
   - **App URL** (optional): `qaoa-benchmarks` or your preferred name
5. Click **"Deploy!"**

### Step 3: Share Your Dashboard 🎉

Your dashboard will be live at:
```
https://[your-app-name].streamlit.app
```

**Features:**
- ✅ Free hosting forever
- ✅ Automatic updates when you push to GitHub
- ✅ No server management needed
- ✅ HTTPS by default
- ✅ Share with anyone via URL

### Alternative: Make Repository Private

If your data is sensitive:
1. Make GitHub repo private
2. Deploy to Streamlit Cloud (it works with private repos)
3. Only people you share the URL with can access it
4. Optional: Add password protection (see below)

## 📝 Adding New Results

To add new benchmark results:

1. Run your experiments and save results as `.npy` files
2. Place them in the appropriate `../Data/backend_name/` directory (parent folder)
3. Refresh the dashboard (it will automatically detect and load new data)

## 🎨 Customization

Edit `dashboard.py` to:
- Add new visualization types
- Change color schemes
- Add more metrics
- Customize hover information
- Add authentication (for private data)

## 📦 Data Structure

The dashboard expects `.npy` files with this structure:
```python
{
    'nq': int,  # Number of qubits
    'ps': list,  # QAOA layers tested
    'postprocessing': {
        delta: {
            p: {
                'r': float,  # Approximation ratio
                'probability': float,  # Probability of optimal
                ...
            }
        }
    }
}
```

## 🔒 Making it Private

To password-protect your dashboard, add to the top of `dashboard.py`:

```python
import streamlit as st

def check_password():
    def password_entered():
        if st.session_state["password"] == "YOUR_PASSWORD":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

if not check_password():
    st.stop()
```

## 📚 Resources

- [Streamlit Documentation](https://docs.streamlit.io)
- [Plotly Documentation](https://plotly.com/python/)
- [Streamlit Cloud Deployment](https://docs.streamlit.io/streamlit-community-cloud/get-started)
