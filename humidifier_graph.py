import socket
import json
import threading
from collections import deque
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation

HOST = "localhost"
PORT = 9998

WINDOW = 1000   # max points kept / shown on screen

x_data      = deque(maxlen=WINDOW)
y_twa_in    = deque(maxlen=WINDOW)
y_twa_out   = deque(maxlen=WINDOW)
y_omega_out = deque(maxlen=WINDOW)
lock        = threading.Lock()

def listen():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"✅ Humidifier graph listening on {HOST}:{PORT}")
    conn, addr = server.accept()
    print(f"✅ Connected: {addr}")
    buffer = ""
    while True:
        try:
            chunk = conn.recv(4096).decode("utf-8")
            if not chunk:
                break
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    with lock:
                        x_data.append(row["i"])
                        y_twa_in.append(row["T_WA_in"])
                        y_twa_out.append(row["T_WA_out"])
                        y_omega_out.append(row["omega_out"])
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Socket error: {e}")
            break
    conn.close()
    server.close()

threading.Thread(target=listen, daemon=True).start()

# ── Figure: 2 subplots — temperature + omega ──────────────────
fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(13, 8),
    gridspec_kw={"height_ratios": [3, 1]},
    sharex=True
)
fig.patch.set_facecolor("#1e1e1e")
fig.suptitle("Humidifier — XGBoost Model Output",
             color="white", fontsize=13, fontweight="bold")

ax1.set_facecolor("#2b2b2b")
ax1.set_ylabel("Temperature (°C)", color="white", fontsize=11)
ax1.set_ylim(0, 50)
ax1.tick_params(colors="white")
ax1.grid(True, color="#3a3a3a", linestyle="--", linewidth=0.5)
for spine in ax1.spines.values():
    spine.set_color("#555")

line_in,  = ax1.plot([], [], color="#DDFF00", linewidth=1.5,
                      linestyle=":", label="T_WA_in (Inlet)")
line_out, = ax1.plot([], [], color="#BB88FF", linewidth=2,
                      label="T_WA_out (XGBoost Prediction)")

ax1.legend(facecolor="#333", edgecolor="#555", labelcolor="white", fontsize=9)

info_text = ax1.text(
    0.02, 0.95, "", transform=ax1.transAxes,
    color="white", fontsize=9, verticalalignment="top",
    bbox=dict(boxstyle="round", facecolor="#333", alpha=0.8),
    animated=True
)

ax2.set_facecolor("#2b2b2b")
ax2.set_ylabel("ω_out (kg/kg)", color="#00CCFF", fontsize=10)
ax2.set_xlabel("Timestep", color="white", fontsize=11)
ax2.tick_params(colors="white")
ax2.grid(True, color="#3a3a3a", linestyle="--", linewidth=0.5)
for spine in ax2.spines.values():
    spine.set_color("#555")

line_omega, = ax2.plot([], [], color="#00CCFF", linewidth=1.5,
                        label="ω_WA_out (Humidity Ratio)")
ax2.legend(facecolor="#333", edgecolor="#555", labelcolor="white", fontsize=9)
ax2.set_ylim(0, 1)   # placeholder; rescaled once on first data

plt.tight_layout()

def update(frame):
    with lock:
        if len(x_data) < 2:
            return line_in, line_out, line_omega, info_text
        xs      = list(x_data)
        t_in    = list(y_twa_in)
        t_out   = list(y_twa_out)
        omega   = list(y_omega_out)

    line_in.set_data(xs,    t_in)
    line_out.set_data(xs,   t_out)
    line_omega.set_data(xs, omega)

    # sliding x-window (y on ax1 stays fixed at 0–50)
    ax1.set_xlim(xs[0], xs[-1])

    # stats over the current window (cheap — capped at WINDOW)
    arr_in  = np.asarray(t_in)
    arr_out = np.asarray(t_out)
    delta   = arr_in - arr_out
    info_text.set_text(
        f"n = {len(xs)} pts (window)\n"
        f"Avg T_WA_in  = {arr_in.mean():.3f}°C\n"
        f"Avg T_WA_out = {arr_out.mean():.3f}°C\n"
        f"Avg ΔT       = {delta.mean():.3f}°C\n"
        f"Avg ω_out    = {np.asarray(omega).mean():.6f} kg/kg"
    )

    return line_in, line_out, line_omega, info_text


def rescale_omega(frame):
    """Refit the bottom (omega) axis ~2x/sec — can't be blitted, so full draw here."""
    with lock:
        if len(y_omega_out) < 2:
            return
        lo, hi = min(y_omega_out), max(y_omega_out)
    if hi == lo:
        hi = lo + 1e-6
    pad = (hi - lo) * 0.1
    ax2.set_ylim(lo - pad, hi + pad)
    fig.canvas.draw_idle()

ani = animation.FuncAnimation(fig, update, interval=33,
                               blit=True, cache_frame_data=False)
ani_scale = animation.FuncAnimation(fig, rescale_omega, interval=500,
                                     blit=False, cache_frame_data=False)
plt.show()