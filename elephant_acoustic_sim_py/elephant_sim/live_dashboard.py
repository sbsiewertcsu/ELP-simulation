"""
Interactive dashboard - Python port of large_scale_sim_FINAL_ver_5_REAL.m

Recreates the MATLAB figure with matplotlib:
  * park map background + dashed boundary, red zones (villages), green zone (Bai)
  * elephants, poachers, rangers, threat lines, mics with detection rings
  * LIVE MISSION REPORT sidebar + LEGEND panel
  * Time-Lapse slider (1x - 5000x) and PLAY/PAUSE toggle (space bar also works)
  * 10-second "STARTING IN n..." countdown

    python run_live.py --strategy 1 --mics 80
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

from .config import STRATEGY_NAMES, SimConfig
from .simulation import Simulation

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMAGE = os.path.join(os.path.dirname(HERE), "assets", "dzanga_sangha_updated_black.png")

FIG_BG = (0.15, 0.15, 0.15)
MIC_IDLE = (0, 0, 1)
MIC_DETECT = (1, 1, 1)
MIC_MEMORY = (0.9, 0.4, 0)
MIC_MISSED = (0.8, 0, 0)


class Dashboard:
    def __init__(self, sim: Simulation, image_path=DEFAULT_IMAGE, speed=1000.0,
                 countdown=10, max_frame_dt=0.5, interactive=True):
        import matplotlib
        if not interactive:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import PatchCollection
        from matplotlib.patches import Circle, Rectangle
        from matplotlib.widgets import Button, Slider

        self.plt = plt
        self.sim = sim
        c = sim.cfg
        env = sim.env
        z = env.zones
        W, H = c.width, c.height
        SIDEBAR_W = 240
        FW, FH = W + SIDEBAR_W + 50, H + 120
        self.W, self.H = W, H
        self.countdown = countdown
        self.max_frame_dt = max_frame_dt
        self.paused = False
        self.frame_count = 0
        self.multiplier = float(speed)

        def px(x, y, w, h):          # MATLAB pixel rect -> figure fraction
            return [x / FW, y / FH, w / FW, h / FH]

        dpi = 100
        self.fig = fig = plt.figure(figsize=(FW / dpi, FH / dpi), dpi=dpi, facecolor=FIG_BG)
        try:
            fig.canvas.manager.set_window_title("Dzanga Simulation Dashboard")
        except Exception:
            pass

        # ---------------- main map axes ----------------
        self.ax = ax = fig.add_axes(px(25, 70, W, H))
        ax.set_xlim(0, W)
        ax.set_ylim(H, 0)                         # YDir reverse
        ax.set_xticks([]); ax.set_yticks([])
        try:
            import matplotlib.image as mpimg
            img = mpimg.imread(image_path)
            if img.ndim == 3 and img.shape[2] == 4:
                img = img[..., :3]                # MATLAB imread drops alpha
            ax.imshow(img, extent=(0, W, H, 0), origin="upper", aspect="auto", zorder=0)
        except Exception:
            ax.set_facecolor((0.1, 0.2, 0.1))
        ax.plot(np.r_[env.boundary_x, env.boundary_x[0]], np.r_[env.boundary_y, env.boundary_y[0]],
                "w--", lw=1, zorder=1)
        ax.text(350, 560, "Dzanga-Sangha National Park", color="w", fontsize=10, fontweight="bold")
        ax.text(350, 580, "Area monitored: 4900 sq. Km", color=(0.7, 0.85, 1), fontsize=10)

        # zones
        for rx, ry, rr, name in zip(z.rep_x, z.rep_y, z.rep_r, z.rep_names):
            ax.add_patch(Circle((rx, ry), rr, facecolor=(1, 0, 0, 0.3), edgecolor="none", zorder=2))
            ax.text(rx, ry, name, color="w", fontsize=9, ha="center", va="center",
                    fontweight="bold", zorder=6)
        ax.add_patch(Circle((z.att_x, z.att_y), z.att_r, facecolor=(0, 1, 0, 0.3),
                            edgecolor="g", lw=2, zorder=2))

        # mics + rings (static positions)
        mx, my = sim.mx, sim.my
        self.mic_coll = PatchCollection(
            [Rectangle((x - 3, y - 3), 6, 6) for x, y in zip(mx, my)],
            facecolor=MIC_IDLE, edgecolor="w", lw=0.5, zorder=3)
        ax.add_collection(self.mic_coll)
        ax.add_collection(PatchCollection(
            [Circle((x, y), sim.range_e) for x, y in zip(mx, my)],
            facecolor="none", edgecolor=(0, 1, 1, 0.4), linestyle="--", lw=1.2, zorder=3))
        ax.add_collection(PatchCollection(
            [Circle((x, y), sim.range_p) for x, y in zip(mx, my)],
            facecolor="none", edgecolor=(1, 0.8, 0, 0.5), lw=1.2, zorder=3))

        # dynamic agents
        ms_e = max(3, 8 * c.sf_x)
        self.h_threat, = ax.plot([], [], "r-.", lw=2, zorder=4)
        self.h_eleph = ax.scatter([], [], s=(ms_e * 1.25) ** 2, marker="o", edgecolors="w",
                                  linewidths=0.6, zorder=5)
        self.h_poached, = ax.plot([], [], "x", color="r", ms=12, mew=2, ls="none", zorder=5)
        self.h_poach, = ax.plot([], [], "o", mfc="m", mec="w", ms=6, ls="none", zorder=5)
        self.h_caught, = ax.plot([], [], "*", mfc="g", mec="g", ms=14, ls="none", zorder=5)
        self.h_rangers, = ax.plot([], [], "s", mfc="w", mec="w", ms=6, ls="none", zorder=5)
        self.h_status = ax.text(W / 2, 50, "", fontsize=20, fontweight="bold", ha="center",
                                va="center", color="w", zorder=10,
                                bbox=dict(facecolor=(0, 0, 0, 0.6), edgecolor="none"))
        self.h_status.set_visible(False)

        # ---------------- UI controls ----------------
        self.ax_slider_lbl = fig.add_axes(px(W / 2 - 120, 45, 180, 20)); self.ax_slider_lbl.axis("off")
        self.h_slider_label = self.ax_slider_lbl.text(0.5, 0.5, f"Time Lapse: {speed:.0f}x",
                                                      color="w", fontsize=10, fontweight="bold",
                                                      ha="center", va="center")
        ax_sl = fig.add_axes(px(W / 2 - 120, 20, 180, 20), facecolor=(0.3, 0.3, 0.3))
        self.slider = Slider(ax_sl, "", 1, 5000, valinit=speed, color=(0.55, 0.55, 0.55))
        self.slider.valtext.set_visible(False)
        if getattr(self.slider, "vline", None) is not None:
            self.slider.vline.set_visible(False)      # hide the 'initial value' tick
        self.slider.on_changed(self._on_slider)

        ax_btn = fig.add_axes(px(W / 2 + 80, 20, 80, 25))
        self.btn = Button(ax_btn, "PAUSE ||", color=(0.8, 0.2, 0.2), hovercolor=(0.9, 0.3, 0.3))
        self.btn.label.set_color("w"); self.btn.label.set_fontweight("bold")
        self.btn.on_clicked(self._toggle_pause)
        fig.canvas.mpl_connect("key_press_event",
                               lambda e: self._toggle_pause() if e.key == " " else None)

        # ---------------- LIVE REPORT sidebar ----------------
        ax_rep = fig.add_axes(px(W + 35, 350, SIDEBAR_W - 10, 350), facecolor="k")
        ax_rep.set_xticks([]); ax_rep.set_yticks([])
        for s in ax_rep.spines.values():
            s.set_color("w")
        ax_rep.set_title(" LIVE MISSION REPORT ", color="w", fontsize=11, fontweight="bold",
                         loc="left", pad=3)
        self.strat_name = STRATEGY_NAMES[c.mic_strategy]
        self.h_report = ax_rep.text(0.05, 0.95, "Initializing...", color="w", fontsize=10,
                                    va="top", ha="left", transform=ax_rep.transAxes,
                                    family="DejaVu Sans", wrap=True)

        # ---------------- LEGEND panel ----------------
        ax_leg = fig.add_axes(px(W + 35, 70, SIDEBAR_W - 10, 270), facecolor="k")
        ax_leg.set_xlim(0, 1); ax_leg.set_ylim(0, 1)
        ax_leg.set_xticks([]); ax_leg.set_yticks([])
        for s in ax_leg.spines.values():
            s.set_color("w")
        ax_leg.set_title(" LEGEND ", color="w", fontsize=11, fontweight="bold", loc="left", pad=3)
        items = [
            (0.91, dict(marker="o", mfc="b", mec="w", ms=8), "Safe Elephant"),
            (0.82, dict(marker="o", mfc=(1, 1, 0), mec="w", ms=8), "Threatened Elephant"),
            (0.73, dict(marker="x", color="r", mew=2, ms=10), "Poached Elephant"),
            (0.64, dict(marker="o", mfc="m", mec="w", ms=6), "Active Poacher"),
            (0.55, dict(marker="s", mfc="w", mec="w", ms=6), "Active Ranger"),
            (0.46, dict(marker="*", mfc="g", mec="g", ms=12), "Neutralized Poacher"),
        ]
        for yv, style, label in items:
            ax_leg.plot(0.1, yv, ls="none", **style)
            ax_leg.text(0.25, yv, label, color="w", fontsize=9, fontweight="bold", va="center")
        for yv, col, label in [(0.37, MIC_IDLE, "Mic (Idle)"), (0.28, MIC_DETECT, "Mic (Detected)"),
                               (0.19, MIC_MEMORY, "Mic (Memory)"), (0.10, MIC_MISSED, "Mic (Missed)")]:
            ax_leg.add_patch(Rectangle((0.07, yv), 0.06, 0.04, facecolor=col, edgecolor="w"))
            ax_leg.text(0.25, yv + 0.02, label, color="w", fontsize=9, fontweight="bold", va="center")

        self.update_artists()
        self._update_report()

    # ------------------------------------------------------------------
    def _on_slider(self, val):
        self.multiplier = float(val)
        self.h_slider_label.set_text(f"Time Lapse: {val:.0f}x")

    def _toggle_pause(self, _event=None):
        self.paused = not self.paused
        if self.paused:
            self.btn.label.set_text("PLAY ►")
            self.btn.color, self.btn.hovercolor = (0.2, 0.8, 0.2), (0.3, 0.9, 0.3)
        else:
            self.btn.label.set_text("PAUSE ||")
            self.btn.color, self.btn.hovercolor = (0.8, 0.2, 0.2), (0.9, 0.3, 0.3)
        self.btn.ax.set_facecolor(self.btn.color)
        self.fig.canvas.draw_idle()

    def _set_status(self, text, color):
        self.h_status.set_text(text)
        self.h_status.set_color(color)
        self.h_status.set_visible(bool(text))

    # ------------------------------------------------------------------
    def update_artists(self):
        s = self.sim
        # elephants
        alive = ~s.e_poached
        self.h_eleph.set_offsets(np.column_stack([s.ex[alive], s.ey[alive]]) if alive.any()
                                 else np.empty((0, 2)))
        cols = np.where(s.e_threatened[alive, None], [[1, 1, 0]], [[0, 0, 1]])
        self.h_eleph.set_facecolors(cols)
        self.h_poached.set_data(s.ex[s.e_poached], s.ey[s.e_poached])
        # poachers & rangers
        act = ~s.p_caught
        self.h_poach.set_data(s.px[act], s.py[act])
        self.h_caught.set_data(s.px[s.p_caught], s.py[s.p_caught])
        r = act & s.p_targeted
        self.h_rangers.set_data(s.rx[r], s.ry[r])
        # threat lines  base -> ranger -> poacher
        if r.any():
            n = int(r.sum())
            lx = np.column_stack([s.base_x[r], s.rx[r], s.px[r], np.full(n, np.nan)]).ravel()
            ly = np.column_stack([s.base_y[r], s.ry[r], s.py[r], np.full(n, np.nan)]).ravel()
            self.h_threat.set_data(lx, ly)
        else:
            self.h_threat.set_data([], [])
        # mics
        if s.num_mics:
            col = np.tile(np.array(MIC_IDLE, float), (s.num_mics, 1))
            col[s.m_active_p | s.m_active_e] = MIC_DETECT
            col[s.m_has_memory] = MIC_MEMORY
            col[s.m_missed] = MIC_MISSED
            self.mic_coll.set_facecolor(col)
        # alert banner
        if s.show_poached_alert():
            self._set_status("POACHED!", (1, 0.2, 0.2))
        elif s.show_caught_alert():
            self._set_status("THREAT NEUTRALIZED!", (0.2, 1, 0.2))
        else:
            self._set_status("", "w")

    def _update_report(self):
        s, c = self.sim, self.sim.cfg
        poached = s.poached_count
        caught = s.caught_count
        days = int(s.t // 86400)
        hours = int((s.t % 86400) // 3600)
        self.h_report.set_text(
            f"STRATEGY: {self.strat_name}\n"
            "--------------\n"
            "TIME ELAPSED\n"
            "--------------\n"
            f"{days} Days, {hours:02d} Hrs\n\n"
            "ELEPHANTS\n"
            "--------------\n"
            f"Total: {c.num_elephants}\n"
            f"Safe/Active: {c.num_elephants - poached}\n"
            f"Poached: {poached}\n\n"
            "POACHERS\n"
            "--------------\n"
            f"Total: {c.num_poachers}\n"
            f"Active: {c.num_poachers - caught}\n"
            f"Neutralized: {caught}")

    # ------------------------------------------------------------------
    def _frame(self, _i):
        now = time.perf_counter()
        if self._start is None:
            self._start = now
            self._last = now
        # countdown
        remaining = self.countdown - (now - self._start)
        if remaining > 0:
            self._set_status(f"STARTING IN {int(np.ceil(remaining))}...", (1, 1, 0))
            self._last = now
            return
        real_dt = min(now - self._last, self.max_frame_dt)
        self._last = now
        self.frame_count += 1
        if self.paused:
            return
        self.sim.step(real_dt * self.multiplier)
        self.update_artists()
        if self.frame_count % 15 == 0:
            self._update_report()

    def run(self):
        from matplotlib.animation import FuncAnimation
        self._start = None
        self._last = None
        self.anim = FuncAnimation(self.fig, self._frame, interval=30,
                                  cache_frame_data=False, blit=False)
        self.plt.show()

    def snapshot(self, path, sim_hours, fps=30.0):
        """Headless: advance the simulation as the live loop would at the current
        time-lapse setting (fixed 1/fps real seconds per frame) and save a PNG."""
        target = sim_hours * 3600.0
        dt = self.multiplier / fps
        frames = 0
        while self.sim.t < target:
            self.sim.step(dt)
            frames += 1
        self.update_artists()
        self._update_report()
        self.fig.savefig(path, facecolor=self.fig.get_facecolor())
        return frames


def main(argv=None):
    ap = argparse.ArgumentParser(description="Live dashboard of the Dzanga-Sangha elephant acoustic simulation.")
    ap.add_argument("--strategy", type=int, default=1, choices=[1, 2, 3, 4],
                    help="mic placement: 1=Uniform 2=Fortress 3=Perimeter 4=50/50 (default 1)")
    ap.add_argument("--mics", type=int, default=80, help="number of microphones (default 80)")
    ap.add_argument("--elephants", type=int, default=20)
    ap.add_argument("--poachers", type=int, default=10)
    ap.add_argument("--speed", type=float, default=1000, help="initial time-lapse multiplier 1-5000 (default 1000)")
    ap.add_argument("--countdown", type=int, default=10, help="start-up countdown in seconds (default 10, 0 = none)")
    ap.add_argument("--seed", type=int, default=None, help="random seed (default: random each run)")
    ap.add_argument("--image", default=DEFAULT_IMAGE, help="background map PNG")
    ap.add_argument("--snapshot", metavar="PNG", default=None,
                    help="no window: run headless and save a picture of the dashboard")
    ap.add_argument("--snapshot-hours", type=float, default=24.0,
                    help="sim-hours to advance before taking --snapshot (default 24)")
    args = ap.parse_args(argv)

    cfg = SimConfig.live(mic_strategy=args.strategy, num_mics=args.mics,
                         num_elephants=args.elephants, num_poachers=args.poachers)
    sim = Simulation(cfg, seed=args.seed)
    dash = Dashboard(sim, image_path=args.image, speed=args.speed, countdown=args.countdown,
                     interactive=args.snapshot is None)
    if args.snapshot:
        frames = dash.snapshot(args.snapshot, args.snapshot_hours)
        print(f"Saved {args.snapshot} after {sim.t / 3600:.1f} sim-hours ({frames} frames): "
              f"{sim.poached_count} poached, {sim.caught_count} poachers neutralized")
        return 0
    dash.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
