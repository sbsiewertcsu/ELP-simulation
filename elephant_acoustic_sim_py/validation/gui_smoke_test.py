"""Drives the REAL interactive window (not the headless snapshot path):
countdown -> running -> slider change -> click PAUSE (sim time must freeze)
-> click PLAY (sim time must advance) -> close.  Run under a display, e.g.
    xvfb-run -a env MPLBACKEND=QtAgg python validation/gui_smoke_test.py"""
import json, sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backend_bases import MouseEvent
from elephant_sim import SimConfig, Simulation
from elephant_sim.live_dashboard import Dashboard

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "gui_smoke.png")
sim = Simulation(SimConfig.live(mic_strategy=2), seed=4)
d = Dashboard(sim, countdown=3, speed=1000)
log = {"backend": matplotlib.get_backend()}

def click(ax):
    fig = d.fig
    x, y = ax.transAxes.transform((0.5, 0.5))
    for name in ("button_press_event", "button_release_event"):
        fig.canvas.callbacks.process(name, MouseEvent(name, fig.canvas, x, y, button=1))

plan = [
    (2.0, lambda: log.update(during_countdown_t=sim.t, status=d.h_status.get_text())),
    (5.0, lambda: log.update(running_t=sim.t)),
    (5.1, lambda: d.slider.set_val(4000)),
    (7.0, lambda: log.update(after_slider_t=sim.t, label=d.h_slider_label.get_text())),
    (7.1, lambda: click(d.btn.ax)),
    (7.3, lambda: log.update(paused=d.paused, btn=d.btn.label.get_text(), t_pause=sim.t)),
    (9.3, lambda: log.update(t_after_2s_paused=sim.t)),
    (9.4, lambda: click(d.btn.ax)),
    (11.5, lambda: log.update(resumed=not d.paused, t_resumed=sim.t,
                              report=d.h_report.get_text().splitlines()[4])),
    (11.6, lambda: d.fig.savefig(out, facecolor=d.fig.get_facecolor())),
    (12.0, lambda: plt.close(d.fig)),
]
t0 = time.perf_counter()
def tick():
    now = time.perf_counter() - t0
    while plan and plan[0][0] <= now:
        plan.pop(0)[1]()
timer = d.fig.canvas.new_timer(interval=50); timer.add_callback(tick); timer.start()
d.run()
ok = (log["during_countdown_t"] == 0 and log["running_t"] > 0
      and log["label"] == "Time Lapse: 4000x" and log["paused"] and log["btn"].startswith("PLAY")
      and log["t_after_2s_paused"] == log["t_pause"] and log["t_resumed"] > log["t_pause"])
log["PASS"] = bool(ok)
print(json.dumps(log, indent=1, default=str))
sys.exit(0 if ok else 1)
