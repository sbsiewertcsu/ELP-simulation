#!/usr/bin/env python3
"""Summarize a sweep CSV: mean elephants poached (95% CI) per strategy x mic count,
a chart, and the best setup per strategy.   python analyze_sweep.py sweep.csv"""
import csv
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

src = sys.argv[1] if len(sys.argv) > 1 else "sweep.csv"
png = sys.argv[2] if len(sys.argv) > 2 else "sweep.png"

data = defaultdict(dict)      # (strategy, n) -> {trial: (poached, all_neutralized)}
names = {}
for r in csv.DictReader(open(src)):
    k = (int(r["strategy"]), int(r["num_mics"]))
    data[k][int(r["trial"])] = (int(r["poached"]), int(r["all_neutralized"]))
    names[int(r["strategy"])] = r["strategy_name"]


def ci(x):
    x = np.asarray(x, float)
    return x.mean(), (1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0)


strategies = sorted(s for s in names if s != 0)
mics = sorted({n for (s, n) in data if s != 0})
fig, ax = plt.subplots(2, 1, figsize=(9, 9), sharex=True)
base = [v[0] for v in data.get((0, 0), {}).values()]
if base:
    m, h = ci(base)
    ax[0].axhline(m, color="k", ls="--", label=f"No mics ({m:.1f})")
print(f"{'strategy':<20}{'best N':>7}{'poached':>9}{'±95%CI':>8}{'caught-all':>12}")
best = {}
for s in strategies:
    ns = [n for n in mics if (s, n) in data]
    stats = [(n, *ci([v[0] for v in data[(s, n)].values()]),
              np.mean([v[1] for v in data[(s, n)].values()])) for n in ns]
    n_, m_, h_, f_ = zip(*stats)
    m_, h_ = np.array(m_), np.array(h_)
    ax[0].plot(n_, m_, label=names[s])
    ax[0].fill_between(n_, m_ - h_, m_ + h_, alpha=0.15)
    ax[1].plot(n_, np.array(f_) * 100, label=names[s])
    i = int(np.argmin(m_))
    best[s] = (n_[i], m_[i], h_[i], f_[i])
    print(f"{names[s]:<20}{n_[i]:>7}{m_[i]:>9.2f}{h_[i]:>8.2f}{f_[i] * 100:>11.0f}%")
ax[0].set_ylabel("Elephants poached (of 20)")
ax[0].set_title("Elephants poached by the time poachers are neutralized (or 30 days)")
ax[0].legend()
ax[1].set_ylabel("% trials where ALL poachers caught")
ax[1].set_xlabel("Number of microphones")
fig.tight_layout()
fig.savefig(png, dpi=130)
print("chart ->", png)

# paired comparison at each strategy's own best N vs the overall best (same trial = same world)
top = min(best, key=lambda s: best[s][1])
print(f"\nPaired difference vs best strategy ({names[top]}, N={best[top][0]}), same mic count where possible:")
for s in strategies:
    if s == top:
        continue
    n = best[top][0]
    if (s, n) not in data:
        continue
    t = sorted(set(data[(s, n)]) & set(data[(top, n)]))
    d = [data[(s, n)][i][0] - data[(top, n)][i][0] for i in t]
    m, h = ci(d)
    print(f"  {names[s]:<20} at N={n}: {m:+.2f} ± {h:.2f} elephants  (n={len(d)})")
