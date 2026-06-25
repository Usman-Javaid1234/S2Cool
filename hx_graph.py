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
PORT = 9999

WINDOW = 1000   # max points kept / shown on screen

x_data        = deque(maxlen=WINDOW)
y_SA_in       = deque(maxlen=WINDOW)
y_WA_out_pred = deque(maxlen=WINDOW)
y_SA_out_pred = deque(maxlen=WINDOW)
y_SA_out_true = deque(maxlen=WINDOW)
y_Q           = deque(maxlen=WINDOW)
lock          = threading.Lock()

def listen():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"✅ HX graph listening on {HOST}:{PORT}")
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
                        y_SA_in.append(row["T_SA_in"])
                        y_WA_out_pred.append(row["T_WA_out_pred"])
                        y_SA_out_pred.append(row["T_SA_out_pred"])
                        y_SA_out_true.append(row["T_SA_out_true"])
                        y_Q.append(row["Q"])
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Socket error: {e}")
            break
    conn.close()
    server.close()

threading.Thread(target=listen, daemon=True).start()

# ── Figure: 2 subplots — temperatures + Q_cooling ─────────────
fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(14, 8),
    gridspec_kw={"height_ratios": [3, 1]},
    sharex=True
)
fig.patch.set_facecolor("#1e1e1e")
fig.suptitle("Heat Exchanger — ExtraTrees Model vs Ground Truth",
             color="white", fontsize=13, fontweight="bold")

ax1.set_facecolor("#2b2b2b")
ax1.set_ylabel("Temperature (°C)", color="white", fontsize=11)
ax1.set_ylim(0, 50)
ax1.tick_params(colors="white")
ax1.grid(True, color="#3a3a3a", linestyle="--", linewidth=0.5)
for spine in ax1.spines.values():
    spine.set_color("#555")

line_SA_in,   = ax1.plot([], [], color="#DDFF00", linewidth=1.5,
                          linestyle=":", label="T_SA_in (Outdoor Air Inlet)")
line_WA_out,  = ax1.plot([], [], color="#BB88FF", linewidth=1.5,
                          linestyle=":", label="T_WA_out (From Humidifier)")
line_SA_pred, = ax1.plot([], [], color="#00FF99", linewidth=2,
                          linestyle="--", label="T_SA_out Pred (ExtraTrees)")
line_SA_true, = ax1.plot([], [], color="#FF6600", linewidth=2, linestyle=":",
                          label="T_SA_out True (Ground Truth)")

ax1.legend(facecolor="#333", edgecolor="#555", labelcolor="white",
           fontsize=9, loc="upper right")

info_text = ax1.text(
    0.02, 0.95, "", transform=ax1.transAxes,
    color="white", fontsize=9, verticalalignment="top",
    bbox=dict(boxstyle="round", facecolor="#333", alpha=0.8),
    animated=True
)

ax2.set_facecolor("#2b2b2b")
ax2.set_ylabel("Q_cool (W)", color="#00CCFF", fontsize=10)
ax2.set_xlabel("Timestep", color="white", fontsize=11)
ax2.tick_params(colors="white")
ax2.grid(True, color="#3a3a3a", linestyle="--", linewidth=0.5)
for spine in ax2.spines.values():
    spine.set_color("#555")

line_Q, = ax2.plot([], [], color="#00CCFF", linewidth=1.5,
                    label="Q_cooling (W)")
ax2.legend(facecolor="#333", edgecolor="#555", labelcolor="white", fontsize=9)
ax2.set_ylim(0, 1)   # placeholder; rescaled once on first data

plt.tight_layout()

def update(frame):
    with lock:
        if len(x_data) < 2:
            return line_SA_in, line_WA_out, line_SA_pred, line_SA_true, line_Q, info_text
        xs       = list(x_data)
        sa_in    = list(y_SA_in)
        wa_out   = list(y_WA_out_pred)
        sa_pred  = list(y_SA_out_pred)
        sa_true  = list(y_SA_out_true)
        q_cool   = list(y_Q)

    line_SA_in.set_data(xs,   sa_in)
    line_WA_out.set_data(xs,  wa_out)
    line_SA_pred.set_data(xs, sa_pred)
    line_SA_true.set_data(xs, sa_true)
    line_Q.set_data(xs,       q_cool)

    # sliding x-window (y on ax1 stays fixed at 0–50)
    ax1.set_xlim(xs[0], xs[-1])

    # stats over the current window (cheap — capped at WINDOW)
    arr_pred = np.asarray(sa_pred)
    arr_true = np.asarray(sa_true)
    err      = arr_pred - arr_true
    rmse     = np.sqrt(np.mean(err**2))
    mae      = np.mean(np.abs(err))
    max_err  = np.max(np.abs(err))

    info_text.set_text(
        f"ExtraTrees  |  n={len(xs)} pts (window)\n"
        f"RMSE    = {rmse:.4f}°C\n"
        f"MAE     = {mae:.4f}°C\n"
        f"Max Err = {max_err:.4f}°C\n"
        f"Q_cool  = {q_cool[-1]:.4f} W"
    )

    return line_SA_in, line_WA_out, line_SA_pred, line_SA_true, line_Q, info_text


def rescale_q(frame):
    """Refit the bottom (Q) axis ~2x/sec — can't be blitted, so full draw here."""
    with lock:
        if len(y_Q) < 2:
            return
        lo, hi = min(y_Q), max(y_Q)
    if hi == lo:
        hi = lo + 1
    pad = (hi - lo) * 0.1
    ax2.set_ylim(lo - pad, hi + pad)
    fig.canvas.draw_idle()

ani = animation.FuncAnimation(fig, update, interval=33,
                               blit=True, cache_frame_data=False)
# refit Q axis ~2x/sec, off the blit hot path
ani_scale = animation.FuncAnimation(fig, rescale_q, interval=500,
                                     blit=False, cache_frame_data=False)
plt.show()