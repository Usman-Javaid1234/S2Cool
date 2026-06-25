# S2Cool Digital Twin — IEC System Visualization

An NVIDIA Omniverse digital twin of the S2Cool Indirect Evaporative Cooling (IEC) system.
Real-time ML predictions from the humidifier and dry channel models are fed into a 3D USD scene,
with live graphs showing model vs experimental performance.

---

## System Overview

```
Excel Data (steady-state)
        │
        ▼
predictor.py  (System Python)
    ├── XGBoost → T_WA_out_pred    (Humidifier model)
    └── Lasso   → T_SA_out_pred    (Dry channel model)
        │
        ├──→ port 9997 → Omniverse USD Stage  (live attr updates)
        ├──→ port 9998 → humidifier_graph.py  (live plot)
        └──→ port 9999 → hx_graph.py          (live plot)
```

---

## Prerequisites

### Hardware
- NVIDIA RTX GPU (RTX 3070 or better recommended)
- Windows 10/11

### Software
- Git
- Python 3.9+ (system Python — **not** Omniverse's bundled Python)
- NVIDIA Omniverse USD Composer (via Kit App Template)

---

## Step 1 — Install Omniverse USD Composer

Clone the Kit App Template and build the USD Composer application:

```bash
git clone https://github.com/NVIDIA-Omniverse/kit-app-template.git
cd kit-app-template
```

**Windows:**
```bat
.\repo.bat template new
```

Follow the prompts:
- Select: **Application**
- Select template: **USD Composer**
- Set name, display name, version as desired

Then build and launch:

```bat
.\repo.bat build
.\repo.bat launch
```

> The first launch may take 5–8 minutes for shader compilation.

---

## Step 2 — Clone the S2Cool Repository

```bash
git clone https://github.com/Usman-Javaid1234/S2Cool.git
cd S2Cool
```

---

## Step 3 — Install Python Dependencies

Install required packages into your **system Python** (not Omniverse):

```bash
pip install -r requirements.txt
```

Contents of `requirements.txt`:
```
pandas>=1.5.0
numpy>=1.23.0
openpyxl>=3.0.10
scikit-learn>=1.1.0
xgboost>=1.7.0
joblib>=1.2.0
matplotlib>=3.6.0
```

---

## Step 4 — Set Up Folder Structure

Ensure the project folder looks like this:

```
S2Cool/
├── s2cool v2.usd              ← Omniverse stage file
├── main_connector.py          ← run in Script Editor
├── predictor.py               ← auto-launched
├── humidifier_graph.py        ← auto-launched
├── hx_graph.py                ← auto-launched
├── requirements.txt
├── models/
│   ├── xgboost_model.pkl
│   ├── scaler_X.pkl
│   ├── scaler_y.pkl
│   └── dry_channel_model.joblib
└── model_inputs/
    └── s2_model_inputs.xlsx
```

---

## Step 5 — Configure System Python Path

Open `main_connector.py` and `predictor.py` and update the **one line** that changes per machine:

```python
# In main_connector.py — line 8
SYSTEM_PYTHON = r"C:\Users\<your-username>\AppData\Local\Programs\Python\Python313\python.exe"

# In predictor.py — line 14
SYSTEM_PYTHON = r"C:\Users\<your-username>\AppData\Local\Programs\Python\Python313\python.exe"
```

To find your Python path, open a Windows terminal and run:
```bat
where python
```

All other paths are **relative to the .usd file location** — no other changes needed.

---

## Step 6 — Open the Stage in USD Composer

1. Launch USD Composer from the Kit App Template
2. Go to **File → Open**
3. Navigate to the cloned `S2Cool` folder
4. Open **`s2cool v2.usd`**

---

## Step 7 — Open the Script Editor

In USD Composer:

```
Developer → Script Editor
```

Or use the menu: **Window → Script Editor**

---

## Step 8 — Run the System

1. In the Script Editor, click **File → Open**
2. Navigate to your S2Cool folder
3. Open **`main_connector.py`**
4. Click **Run** (or press `Ctrl + Enter`)

This will automatically:
- Start the Omniverse receiver on port `9997`
- Launch `predictor.py` in a separate console window
- Launch `humidifier_graph.py` (port `9998`)
- Launch `hx_graph.py` (port `9999`)
- Begin feeding data into the USD stage and live graphs

---

## What You Will See

| Window | Description |
|--------|-------------|
| USD Composer viewport | 3D humidifier + heat exchanger with live attribute updates |
| Humidifier graph | T_WA_in vs T_WA_out (XGBoost prediction) + humidity ratio |
| HX graph | T_SA_in, T_WA_out_pred, T_SA_out pred vs true + Q_cooling |
| Predictor console | Row-by-row feed log with predictions |

---
## Adjusting Speed

To slow down or speed up the data feed, change `INTERVAL` in `predictor.py`:

```python
INTERVAL = 1.0   # seconds per row — increase to slow down
```

And match the graph redraw rate in both graph files:

```python
ani = animation.FuncAnimation(fig, update, interval=1000, ...)
# interval is in milliseconds — should equal INTERVAL × 1000
```

## Changing the Input Data File

To use a different session or Excel file, update this line in `predictor.py`:

```python
EXCEL_PATH = os.path.join(BASE_DIR, "model_inputs", "s2_model_inputs.xlsx")
```

Replace `s2_model_inputs.xlsx` with your file name, for example:

```python
EXCEL_PATH = os.path.join(BASE_DIR, "model_inputs", "s7_model_inputs.xlsx")
```

The file must be placed in the `model_inputs/` folder and have the sheet name `ModelInputs` with columns `Time`, `T_WA_in`, `T_wb`, `T_SA_in`, `T_SA_out`.
---

## Ports Used

| Port | Purpose |
|------|---------|
| `9997` | Omniverse USD stage receiver |
| `9998` | Humidifier live graph |
| `9999` | Heat exchanger live graph |

Make sure no other applications are using these ports before running.

---

## Troubleshooting

**Predictor console closes immediately**
- Check that `SYSTEM_PYTHON` points to the correct Python executable
- Run `where python` in a terminal to verify the path

**`ModuleNotFoundError: No module named 'joblib'`**
- The wrong Python is being used — verify `SYSTEM_PYTHON` path in both files

**`Connection refused` on port 9997**
- Make sure `main_connector.py` is running in Omniverse **before** predictor tries to connect
- Predictor retries 30 times — check the console for retry messages

**Graph window doesn't appear**
- Verify `humidifier_graph.py` and `hx_graph.py` are in the same folder as `predictor.py`
- Check `SYSTEM_PYTHON` path has `matplotlib` installed

**Omniverse attributes not updating**
- Check the Script Editor console for prim path errors
- Verify the `.usd` file has the correct prim structure by running the debug script

---

## Repository Structure

```
S2Cool/
├── main_connector.py          Omniverse receiver + predictor launcher
├── predictor.py               ML inference + socket feed
├── humidifier_graph.py        Live humidifier visualization
├── hx_graph.py                Live heat exchanger visualization
├── requirements.txt           System Python dependencies
├── s2cool v2.usd              Omniverse USD stage
├── models/                    Trained ML model files
└── model_inputs/              Preprocessed steady-state Excel data
```

---

## Links

- [NVIDIA Kit App Template](https://github.com/NVIDIA-Omniverse/kit-app-template)
- [S2Cool Repository](https://github.com/Usman-Javaid1234/S2Cool)
- [Omniverse Kit SDK Docs](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)
