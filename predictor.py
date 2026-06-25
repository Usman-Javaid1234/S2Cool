import pandas as pd
import numpy as np
import joblib
import socket
import json
import time
import subprocess
import os

# ══════════════════════════════════════════════════════════════
#  BASE DIR — all paths relative to this file
# ══════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════════════════════════════════════════════
#  CONFIG — only change SYSTEM_PYTHON and INTERVAL
# ══════════════════════════════════════════════════════════════
SYSTEM_PYTHON  = r"C:\Users\usman\AppData\Local\Programs\Python\Python313\python.exe"
INTERVAL       = 1.0    # seconds per row
M_DOT          = 0.006362127
CP             = 1.02
P_ATM          = 101.325

OMNI_HOST      = "localhost"
OMNI_PORT      = 9997
HUM_PORT       = 9998
HX_PORT        = 9999

# ── All paths relative to BASE_DIR ────────────────────────────
EXCEL_PATH     = os.path.join(BASE_DIR, "model_inputs", "s2_model_inputs.xlsx")
SHEET_NAME     = "ModelInputs"

HUM_MODEL_PATH = os.path.join(BASE_DIR, "models", "xgboost_model.pkl")
HUM_SCALER_X   = os.path.join(BASE_DIR, "models", "scaler_X.pkl")
HUM_SCALER_Y   = os.path.join(BASE_DIR, "models", "scaler_y.pkl")

HX_MODEL_PATH  = os.path.join(BASE_DIR, "models", "dry_channel_model.joblib")

HUM_GRAPH      = os.path.join(BASE_DIR, "humidifier_graph.py")
HX_GRAPH       = os.path.join(BASE_DIR, "hx_graph.py")

print(f"📁 Base dir : {BASE_DIR}")
print(f"📊 Excel    : {EXCEL_PATH}")
print(f"🤖 Hum model: {HUM_MODEL_PATH}")
print(f"🤖 HX model : {HX_MODEL_PATH}")

# ══════════════════════════════════════════════════════════════
#  LOAD EXCEL
# ══════════════════════════════════════════════════════════════
print("\nLoading Excel...")
df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, engine='openpyxl')
df = df.sort_values('Time').reset_index(drop=True)
df = df.dropna(subset=['T_WA_in', 'T_wb', 'T_SA_in', 'T_SA_out']).reset_index(drop=True)

rows = []
for _, row in df.iterrows():
    rows.append((
        row['Time'],
        float(row['T_WA_in']),
        float(row['T_wb']),
        float(row['T_SA_in']),
        float(row['T_SA_out']),
    ))

print(f"✅ Loaded {len(rows)} rows.")
print(f"   First: T_WA_in={rows[0][1]:.3f}  T_wb={rows[0][2]:.3f}  "
      f"T_SA_in={rows[0][3]:.3f}  T_SA_out={rows[0][4]:.3f}")

# ══════════════════════════════════════════════════════════════
#  LOAD HUMIDIFIER MODEL
# ══════════════════════════════════════════════════════════════
print("\nLoading humidifier model...")
hum_model    = joblib.load(HUM_MODEL_PATH)
hum_scaler_x = joblib.load(HUM_SCALER_X)
hum_scaler_y = joblib.load(HUM_SCALER_Y)

def predict_humidifier(T_WA_in, T_wb):
    inp    = hum_scaler_x.transform([[T_WA_in, T_wb]])
    pred_s = hum_model.predict(inp)
    return float(hum_scaler_y.inverse_transform(pred_s.reshape(-1, 1))[0][0])

print(f"✅ Humidifier model loaded: {type(hum_model).__name__}")

# ══════════════════════════════════════════════════════════════
#  LOAD HX MODEL — single bundle dict
# ══════════════════════════════════════════════════════════════
print("Loading HX model...")
hx_bundle = joblib.load(HX_MODEL_PATH)
hx_model  = hx_bundle['model']
hx_scaler = hx_bundle['scaler']

def predict_hx(T_SA_in, T_WA_out):
    X = pd.DataFrame([[T_SA_in, T_WA_out]], columns=['T_SA_in', 'T_WA_in'])
    return float(hx_model.predict(hx_scaler.transform(X))[0])

print(f"✅ HX model loaded: {type(hx_model).__name__}")

# ══════════════════════════════════════════════════════════════
#  PSYCHROMETRIC HELPERS
# ══════════════════════════════════════════════════════════════
def psat(T):
    return 0.611 * np.exp(17.27 * T / (T + 237.3))

def compute_omega_out(T_WA_out):
    Ps = psat(T_WA_out)
    return 0.622 * Ps / (P_ATM - Ps)

def cooling_capacity(T_SA_in, T_SA_out):
    return M_DOT * CP * (T_SA_in - T_SA_out) * 1000

# ══════════════════════════════════════════════════════════════
#  CONNECT TO OMNIVERSE (retry loop)
# ══════════════════════════════════════════════════════════════
print(f"\n⏳ Connecting to Omniverse on port {OMNI_PORT}...")
omni_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connected = False
for attempt in range(30):
    try:
        omni_sock.connect((OMNI_HOST, OMNI_PORT))
        print(f"✅ Omniverse connected on port {OMNI_PORT}")
        connected = True
        break
    except ConnectionRefusedError:
        print(f"   Attempt {attempt+1}/30 — waiting for Omniverse...")
        time.sleep(1)

if not connected:
    print("❌ Could not connect to Omniverse after 30 attempts.")
    print("   Make sure main_connector.py is running in Omniverse first.")
    input("\nPress Enter to close...")
    exit(1)

# ══════════════════════════════════════════════════════════════
#  LAUNCH GRAPH WINDOWS
# ══════════════════════════════════════════════════════════════
print("\n⏳ Launching graph windows...")
subprocess.Popen([SYSTEM_PYTHON, HUM_GRAPH])
subprocess.Popen([SYSTEM_PYTHON, HX_GRAPH])
time.sleep(3)

# ══════════════════════════════════════════════════════════════
#  CONNECT TO GRAPH SOCKETS (retry loop)
# ══════════════════════════════════════════════════════════════
hum_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
for attempt in range(15):
    try:
        hum_sock.connect((OMNI_HOST, HUM_PORT))
        print(f"✅ Humidifier graph connected on port {HUM_PORT}")
        break
    except ConnectionRefusedError:
        print(f"   Humidifier attempt {attempt+1}/15...")
        time.sleep(1)

hx_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
for attempt in range(15):
    try:
        hx_sock.connect((OMNI_HOST, HX_PORT))
        print(f"✅ HX graph connected on port {HX_PORT}")
        break
    except ConnectionRefusedError:
        print(f"   HX attempt {attempt+1}/15...")
        time.sleep(1)

# ══════════════════════════════════════════════════════════════
#  MAIN FEED LOOP
# ══════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"  Feeding {len(rows)} rows at {INTERVAL}s interval")
print(f"{'='*60}\n")

for i, (time_val, T_WA_in, T_wb, T_SA_in, T_SA_out_true) in enumerate(rows):
    try:
        # Step 1: Humidifier prediction
        T_WA_out_pred = predict_humidifier(T_WA_in, T_wb)
        omega_out     = compute_omega_out(T_WA_out_pred)

        # Step 2: HX prediction
        T_SA_out_pred = predict_hx(T_SA_in, T_WA_out_pred)
        Q             = cooling_capacity(T_SA_in, T_SA_out_pred)

        # Step 3: Send to Omniverse
        omni_payload = json.dumps({
            "T_WA_in":       T_WA_in,
            "T_wb":          T_wb,
            "T_WA_out_pred": T_WA_out_pred,
            "omega_out":     omega_out,
            "T_SA_in":       T_SA_in,
            "T_SA_out_pred": T_SA_out_pred,
            "Q":             Q,
        }) + "\n"
        omni_sock.sendall(omni_payload.encode("utf-8"))

        # Step 4: Send to humidifier graph
        hum_payload = json.dumps({
            "i":         i,
            "time":      str(time_val),
            "T_WA_in":   T_WA_in,
            "T_WA_out":  T_WA_out_pred,
            "omega_out": omega_out,
        }) + "\n"
        hum_sock.sendall(hum_payload.encode("utf-8"))

        # Step 5: Send to HX graph
        hx_payload = json.dumps({
            "i":             i,
            "time":          str(time_val),
            "T_SA_in":       T_SA_in,
            "T_WA_out_pred": T_WA_out_pred,
            "T_SA_out_pred": T_SA_out_pred,
            "T_SA_out_true": T_SA_out_true,
            "Q":             Q,
        }) + "\n"
        hx_sock.sendall(hx_payload.encode("utf-8"))

        print(f"Row {i+1:>4}/{len(rows)} | "
              f"T_WA_in={T_WA_in:.3f}  "
              f"T_WA_out={T_WA_out_pred:.3f}  "
              f"T_SA_in={T_SA_in:.3f}  "
              f"Pred={T_SA_out_pred:.3f}  "
              f"True={T_SA_out_true:.3f}  "
              f"Q={Q:.2f}W")

        time.sleep(INTERVAL)

    except BrokenPipeError:
        print("⚠️  Socket disconnected — stopping feed.")
        break
    except Exception as e:
        print(f"⚠️  Row {i+1} error: {e}")
        continue

# ── Cleanup ───────────────────────────────────────────────────
hum_sock.close()
hx_sock.close()
omni_sock.close()
print("\n✅ Feed complete. All sockets closed.")
input("Press Enter to close...")