#!/usr/bin/env python3
"""Compare the same seeded trials at three time steps (paired by trial).
python compare_dt.py [dt250.csv dt50.csv dt10.csv] [n_trials]"""
import csv
import sys

import numpy as np

d = "results/dt_study/"
f250, f50, f10 = (sys.argv[1:4] + [d + "dt250_sweep.csv", d + "dt50.csv", d + "dt10.csv"][len(sys.argv[1:4]):])[:3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 15


def load(p):
    return {(r["strategy_name"], int(r["num_mics"]), int(r["trial"])): (int(r["poached"]), int(r["all_neutralized"]))
            for r in csv.DictReader(open(p))}


A, B, C = load(f250), load(f50), load(f10)
print(f"{'strategy':<18}{'N':>4} | {'poached 250':>11}{'50':>7}{'10':>7} | {'50-10 paired ±95%CI':>20} | caught% 250/50/10")
for s, n in sorted({(s, n) for s, n, _ in C}, key=lambda k: (k[1], k[0])):
    ts = range(1, N + 1)
    g = lambda D: np.array([D[(s, n, t)][0] for t in ts])
    h = lambda D: np.mean([D[(s, n, t)][1] for t in ts]) * 100
    a, b, c = g(A), g(B), g(C)
    diff = b - c
    ci = 1.96 * diff.std(ddof=1) / np.sqrt(N)
    print(f"{s:<18}{n:>4} | {a.mean():>11.2f}{b.mean():>7.2f}{c.mean():>7.2f} | {diff.mean():>+10.2f} ±{ci:<7.2f}| {h(A):>4.0f}/{h(B):>3.0f}/{h(C):>3.0f}")
