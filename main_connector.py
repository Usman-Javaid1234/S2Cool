import omni.usd
import asyncio
import omni.kit.app
import socket
import json
import subprocess
import os

# ══════════════════════════════════════════════════════════════
#  CONFIG — only change SYSTEM_PYTHON on a new machine
# ══════════════════════════════════════════════════════════════
SYSTEM_PYTHON = r"C:\Users\usman\AppData\Local\Programs\Python\Python313\python.exe"
OMNI_PORT     = 9997

# All paths relative to the .usd file location
stage    = omni.usd.get_context().get_stage()
usd_path = stage.GetRootLayer().realPath
BASE_DIR = os.path.dirname(usd_path)

PREDICTOR_PATH = os.path.join(BASE_DIR, "predictor.py")

print(f"📁 Base directory: {BASE_DIR}")
print(f"🐍 System Python:  {SYSTEM_PYTHON}")
print(f"📄 Predictor:      {PREDICTOR_PATH}")

# USD prim paths
PRIM_HUM_IN    = "/World/Humidifier/InletPort"
PRIM_HUM_OUT   = "/World/Humidifier/OutletPort"
PRIM_HX_OA_IN  = "/World/HeatExchanger/Ports/OutdoorAirIn"
PRIM_HX_WA_IN  = "/World/HeatExchanger/Ports/WorkingAirIn"
PRIM_HX_SA_OUT = "/World/HeatExchanger/Ports/SupplyAirOut"

# ══════════════════════════════════════════════════════════════
#  CONNECT TO STAGE
# ══════════════════════════════════════════════════════════════
hum_inlet  = stage.GetPrimAtPath(PRIM_HUM_IN)
hum_outlet = stage.GetPrimAtPath(PRIM_HUM_OUT)
hx_oa_in   = stage.GetPrimAtPath(PRIM_HX_OA_IN)
hx_wa_in   = stage.GetPrimAtPath(PRIM_HX_WA_IN)
hx_sa_out  = stage.GetPrimAtPath(PRIM_HX_SA_OUT)

for path, prim in [
    (PRIM_HUM_IN,    hum_inlet),
    (PRIM_HUM_OUT,   hum_outlet),
    (PRIM_HX_OA_IN,  hx_oa_in),
    (PRIM_HX_WA_IN,  hx_wa_in),
    (PRIM_HX_SA_OUT, hx_sa_out),
]:
    status = "✅" if prim.IsValid() else "⚠️  NOT FOUND:"
    print(f"  {status} {path}")

print("✅ Stage connected.")

# ══════════════════════════════════════════════════════════════
#  LAUNCH predictor.py IN SYSTEM PYTHON
# ══════════════════════════════════════════════════════════════
clean_env = {
    "PATH":        os.environ.get("PATH", ""),
    "SYSTEMROOT":  os.environ.get("SYSTEMROOT", "C:\\Windows"),
    "TEMP":        os.environ.get("TEMP",  "C:\\Temp"),
    "TMP":         os.environ.get("TMP",   "C:\\Temp"),
    "USERPROFILE": os.environ.get("USERPROFILE", ""),
    "APPDATA":     os.environ.get("APPDATA", ""),
}

subprocess.Popen(
    [SYSTEM_PYTHON, PREDICTOR_PATH],
    creationflags=subprocess.CREATE_NEW_CONSOLE,
    env=clean_env,
    cwd=BASE_DIR
)
print("✅ predictor.py launched in separate console.")

# ══════════════════════════════════════════════════════════════
#  SOCKET RECEIVER
# ══════════════════════════════════════════════════════════════
async def receive_and_write():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("localhost", OMNI_PORT))
    server.listen(1)
    server.setblocking(False)

    print(f"✅ Receiver listening on port {OMNI_PORT}...")

    app       = omni.kit.app.get_app()
    conn      = None
    buffer    = ""
    row_count = 0

    while True:
        await app.next_update_async()

        if conn is None:
            try:
                conn, addr = server.accept()
                conn.setblocking(False)
                print(f"✅ predictor.py connected from {addr}")
            except BlockingIOError:
                continue

        try:
            chunk = conn.recv(4096).decode("utf-8")
            if not chunk:
                print("✅ Feed complete — predictor disconnected.")
                break
            buffer += chunk

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Write Humidifier attrs
                if hum_inlet.IsValid():
                    hum_inlet.GetAttribute("T_WA_IN").Set(float(row["T_WA_in"]))
                    hum_inlet.GetAttribute("T_WB").Set(float(row["T_wb"]))
                if hum_outlet.IsValid():
                    hum_outlet.GetAttribute("T_WA_Out").Set(float(row["T_WA_out_pred"]))
                    hum_outlet.GetAttribute("omega_WA_out").Set(float(row["omega_out"]))

                # Write HX attrs
                if hx_oa_in.IsValid():
                    hx_oa_in.GetAttribute("T_SA_in").Set(float(row["T_SA_in"]))
                if hx_wa_in.IsValid():
                    hx_wa_in.GetAttribute("T_WA_in").Set(float(row["T_WA_out_pred"]))
                if hx_sa_out.IsValid():
                    hx_sa_out.GetAttribute("T_SA_out").Set(float(row["T_SA_out_pred"]))

                row_count += 1
                if row_count % 10 == 0:
                    print(f"  📥 Row {row_count} | "
                          f"T_WA_out={row['T_WA_out_pred']:.3f}  "
                          f"T_SA_out={row['T_SA_out_pred']:.3f}  "
                          f"Q={row['Q']:.2f}W")

        except BlockingIOError:
            pass
        except Exception as e:
            print(f"⚠️  Receiver error: {e}")
            break

    if conn:
        conn.close()
    server.close()
    print(f"✅ Receiver closed. Total rows written: {row_count}")

asyncio.ensure_future(receive_and_write())
print("✅ Omniverse receiver started.")