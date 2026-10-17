"""
Mic-count x placement-strategy sweep.

For every (strategy, mic count) it runs many Monte-Carlo trials and writes ONE
CSV row per trial.  Score of interest: `poached` = elephants poached by the time
the poachers were neutralized (trial stops when all poachers are caught, all
elephants are poached, or max_days is reached - see `all_neutralized`).

    python run_sweep.py --runs 50 --workers 8 --out sweep.csv

Strategy 0 is the no-mics control.  Strategies 1-4 are deterministic layouts;
strategy 5 (random mesh) draws a fresh layout every trial.  Seeds depend only on
(base seed, mic count, trial) so every strategy sees the same random world
(common random numbers) and an interrupted sweep can be resumed.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from .batch import run_trial
from .config import BATCH_STRATEGY_NAMES, SimConfig
from .environment import Environment
from .mic_placement import place_mics

NAMES = {0: "No Mics", **BATCH_STRATEGY_NAMES}
COLUMNS = ["strategy", "strategy_name", "num_mics", "trial", "poached", "neutralized",
           "all_neutralized", "time_1st_poach_days", "time_1st_neutral_days",
           "total_time_days"]

_W = {}   # per-process state: env is built once per worker


def _init(cfg, pools, max_days, dt):
    _W.update(cfg=cfg, env=Environment(cfg), pools=pools, max_days=max_days, dt=dt, layouts={})


def _layout(strategy, n, base_seed, trial):
    if strategy == 0 or n == 0:
        return np.zeros((0, 2))
    if strategy == 5:   # fresh random layout per trial
        rng = np.random.default_rng(np.random.SeedSequence([base_seed, n, trial, 99]))
        return place_mics(_W["env"], 5, n, rng)
    key = (strategy, n)
    if key not in _W["layouts"]:
        _W["layouts"][key] = place_mics(_W["env"], strategy, n)
    return _W["layouts"][key]


def _task(args):
    strategy, n, trial, base_seed = args
    cfg = _W["cfg"]
    seed = np.random.SeedSequence([base_seed, n, trial])
    r = run_trial(cfg, _W["env"], _W["pools"], _layout(strategy, n, base_seed, trial),
                  seed, _W["max_days"], _W["dt"], trial)
    return [strategy, NAMES[strategy], n, trial, r.poached, r.neutralized,
            int(r.neutralized == cfg.num_poachers), f"{r.time_1st_poach:.6f}",
            f"{r.time_1st_neutral:.6f}", f"{r.total_time:.6f}"]


def _done_keys(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="") as f:
        return {(int(r["strategy"]), int(r["num_mics"]), int(r["trial"])) for r in csv.DictReader(f)}


def run_sweep(out, runs=50, mic_min=10, mic_max=160, mic_step=5, strategies=(1, 2, 3, 4, 5),
              control=True, max_days=30.0, dt=250.0, seed=0, workers=1, quiet=False):
    cfg = SimConfig.batch()
    env = Environment(cfg)
    pools = env.build_pools(np.random.default_rng(np.random.SeedSequence([seed, 7])))
    grid = [(s, n) for n in range(mic_min, mic_max + 1, mic_step) for s in strategies]
    if control:
        grid.insert(0, (0, 0))
    done = _done_keys(out)
    tasks = [(s, n, t, seed) for s, n in grid for t in range(1, runs + 1)
             if (s, n, t) not in done]
    if not quiet:
        print(f"{len(tasks)} trials to run ({len(done)} already in {out})", flush=True)
    new = not os.path.exists(out)
    t0 = time.perf_counter()
    with open(out, "a", newline="") as f, \
            ProcessPoolExecutor(max_workers=max(1, workers), initializer=_init,
                                initargs=(cfg, pools, max_days, dt)) as ex:
        w = csv.writer(f)
        if new:
            w.writerow(COLUMNS)
        for i, row in enumerate(ex.map(_task, tasks, chunksize=4), 1):
            w.writerow(row)
            if i % 50 == 0:
                f.flush()
                if not quiet:
                    print(f"  {i}/{len(tasks)}  ({time.perf_counter() - t0:.0f}s)", flush=True)
    if not quiet:
        print(f"Done in {time.perf_counter() - t0:.0f}s -> {out}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mic count x strategy sweep (one CSV row per trial).")
    ap.add_argument("--runs", type=int, default=50, help="trials per (strategy, mic count)")
    ap.add_argument("--mics-min", type=int, default=10)
    ap.add_argument("--mics-max", type=int, default=160)
    ap.add_argument("--mics-step", type=int, default=5)
    ap.add_argument("--strategies", type=int, nargs="+", default=[1, 2, 3, 4, 5],
                    choices=[1, 2, 3, 4, 5])
    ap.add_argument("--no-control", action="store_true", help="skip the 0-mic baseline")
    ap.add_argument("--days", type=float, default=30.0)
    ap.add_argument("--dt", type=float, default=250.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default="sweep.csv", help="CSV to append to (resumes if it exists)")
    a = ap.parse_args(argv)
    run_sweep(a.out, a.runs, a.mics_min, a.mics_max, a.mics_step, tuple(a.strategies),
              not a.no_control, a.days, a.dt, a.seed, a.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
