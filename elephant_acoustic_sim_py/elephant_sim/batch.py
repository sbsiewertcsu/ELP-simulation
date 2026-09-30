"""
Batch / Monte-Carlo mode - Python port of large_scale_sim_FINAL_ver_6_DEBUG_ONLY.m

No graphics.  Runs N trials of one (or every) mic strategy and prints the same
per-trial table and summary statistics as the MATLAB script.  Optionally
writes every trial to a CSV file.

    python run_batch.py --runs 50 --strategy 1 --mics 600 --days 30 --dt 250
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np

from .config import BATCH_STRATEGY_NAMES, SimConfig
from .environment import Environment
from .mic_placement import place_mics
from .simulation import Simulation


@dataclass
class TrialResult:
    run: int
    poached: int
    neutralized: int
    time_1st_poach: float     # days, 0 = never (same convention as MATLAB)
    time_1st_neutral: float   # days, 0 = never
    total_time: float         # days
    first_poach_done: bool
    first_neutral_done: bool


def run_trial(cfg: SimConfig, env: Environment, pools, mic_layout, seed,
              max_days: float, sim_dt: float, run: int = 1) -> TrialResult:
    sim = Simulation(cfg, seed=seed, env=env, mic_layout=mic_layout, pools=pools)
    max_t = max_days * 86400.0
    while sim.t < max_t:
        sim.step(sim_dt)
        if sim.finished():
            break
    fp = sim.time_first_poach
    fn = sim.time_first_neutral
    return TrialResult(
        run=run,
        poached=sim.poached_count,
        neutralized=sim.caught_count,
        time_1st_poach=(fp / 86400.0) if fp is not None else 0.0,
        time_1st_neutral=(fn / 86400.0) if fn is not None else 0.0,
        total_time=sim.t / 86400.0,
        first_poach_done=fp is not None,
        first_neutral_done=fn is not None,
    )


# worker-process globals (so the environment is built once per process)
_W = {}


def _worker_init(cfg, pools, mic_layout, max_days, sim_dt):
    _W.update(cfg=cfg, env=Environment(cfg), pools=pools, mic_layout=mic_layout,
              max_days=max_days, sim_dt=sim_dt)


def _worker_run(args):
    run, seed = args
    return run_trial(_W["cfg"], _W["env"], _W["pools"], _W["mic_layout"], seed,
                     _W["max_days"], _W["sim_dt"], run)


def _fmt_row(r: TrialResult, nE, nP):
    fp = f"{r.time_1st_poach:.2f} days" if r.first_poach_done else "---"
    fn = f"{r.time_1st_neutral:.2f} days" if r.first_neutral_done else "---"
    return "%-6d %-12s %-12s %-18s %-18s %-16s" % (
        r.run, f"{r.poached} / {nE}", f"{r.neutralized} / {nP}", fp, fn,
        f"{r.total_time:.2f} days")


def _std(a):
    a = np.asarray(a, dtype=float)
    return float(np.std(a, ddof=1)) if a.size > 1 else 0.0   # MATLAB std (N-1)


def summarize(results, cfg: SimConfig, num_mics_placed: int, num_runs: int, out=print):
    nE, nP = cfg.num_elephants, cfg.num_poachers
    name = BATCH_STRATEGY_NAMES[cfg.mic_strategy]
    poached = np.array([r.poached for r in results], float)
    neutral = np.array([r.neutralized for r in results], float)
    t_poach = np.array([r.time_1st_poach for r in results], float)
    t_neut = np.array([r.time_1st_neutral for r in results], float)
    total = np.array([r.total_time for r in results], float)

    out("\n" + "=" * 84)
    out(f"  SUMMARY — {name}  |  {num_mics_placed} Mics  |  {num_runs} Trials")
    out("=" * 84)
    out("  Elephants poached    — Mean: %.1f%%  |  Std: %.1f%%  |  Min: %.0f%%  |  Max: %.0f%%" % (
        poached.mean() / nE * 100, _std(poached) / nE * 100,
        poached.min() / nE * 100, poached.max() / nE * 100))
    out("  Poachers neutralized — Mean: %.1f%%  |  Std: %.1f%%  |  Min: %.0f%%  |  Max: %.0f%%" % (
        neutral.mean() / nP * 100, _std(neutral) / nP * 100,
        neutral.min() / nP * 100, neutral.max() / nP * 100))
    vp = t_poach[t_poach > 0]
    vn = t_neut[t_neut > 0]
    if vp.size:
        out("  Time to 1st poach    — Mean: %.2f days  |  Std: %.2f  |  Min: %.2f  |  Max: %.2f  (%d/%d trials)" % (
            vp.mean(), _std(vp), vp.min(), vp.max(), vp.size, num_runs))
    else:
        out("  Time to 1st poach    — No poaching events occurred")
    if vn.size:
        out("  Time to 1st neutral  — Mean: %.2f days  |  Std: %.2f  |  Min: %.2f  |  Max: %.2f  (%d/%d trials)" % (
            vn.mean(), _std(vn), vn.min(), vn.max(), vn.size, num_runs))
    else:
        out("  Time to 1st neutral  — No neutralizations occurred")
    out("  Total sim-time       — Mean: %.2f days  |  Std: %.2f  |  Min: %.2f  |  Max: %.2f" % (
        total.mean(), _std(total), total.min(), total.max()))
    out("=" * 84 + "\n")
    return dict(strategy=cfg.mic_strategy, name=name,
                poached_pct=poached.mean() / nE * 100,
                neutral_pct=neutral.mean() / nP * 100,
                t_poach=vp.mean() if vp.size else float("nan"),
                t_neut=vn.mean() if vn.size else float("nan"),
                total=total.mean())


def run_batch(num_runs=50, strategy=1, num_mics=600, max_days=30.0, sim_dt=250.0,
              seed=None, workers=1, csv_path=None, cfg_overrides=None, quiet=False):
    out = (lambda *a, **k: None) if quiet else (lambda s="": print(s, flush=True))
    cfg = SimConfig.batch(mic_strategy=strategy, num_mics=num_mics, **(cfg_overrides or {}))
    name = BATCH_STRATEGY_NAMES[strategy]
    ss = np.random.SeedSequence(seed)
    setup_seed, trial_ss = ss.spawn(2)
    setup_rng = np.random.default_rng(setup_seed)

    env = Environment(cfg)
    out("Pre-computing position pools...")
    pools = env.build_pools(setup_rng)
    out(f"Placing microphones (Strategy {strategy}: {name}, N={num_mics})...")
    mic_layout = place_mics(env, strategy, num_mics)
    n_placed = len(mic_layout)

    out("\n========================================================")
    out("  BATCH SIMULATION — DEBUG MODE")
    out("========================================================")
    out(f"  Strategy    : {name}")
    out(f"  Elephants   : {cfg.num_elephants}")
    out(f"  Poachers    : {cfg.num_poachers}")
    out(f"  Microphones : {num_mics} (placed: {n_placed})")
    out(f"  Trials      : {num_runs}")
    out(f"  Max sim-days: {max_days:g}")
    out(f"  SIM_DT      : {sim_dt:.1f} sim-seconds/step")
    out(f"  Poach prob  : {cfg.poach_probability:.2f}  |  Detect prob: {cfg.detection_probability:.2f}")
    out("========================================================\n")
    out("%-6s %-12s %-12s %-18s %-18s %-16s" % (
        "Trial", "Poached", "Neutralized", "Time 1st Poach", "Time 1st Neutral", "Total Time"))
    out("-" * 84)

    seeds = trial_ss.spawn(num_runs)
    results = []
    t0 = time.perf_counter()
    if workers and workers > 1:
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init,
                                 initargs=(cfg, pools, mic_layout, max_days, sim_dt)) as ex:
            for r in ex.map(_worker_run, [(i + 1, s) for i, s in enumerate(seeds)]):
                results.append(r)
                out(_fmt_row(r, cfg.num_elephants, cfg.num_poachers))
    else:
        for i, s in enumerate(seeds):
            r = run_trial(cfg, env, pools, mic_layout, s, max_days, sim_dt, i + 1)
            results.append(r)
            out(_fmt_row(r, cfg.num_elephants, cfg.num_poachers))
    elapsed = time.perf_counter() - t0

    summary = summarize(results, cfg, n_placed, num_runs, out)
    out(f"(wall-clock: {elapsed:.1f} s)")

    if csv_path:
        new = not os.path.exists(csv_path)
        with open(csv_path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["strategy", "strategy_name", "num_mics", "trial", "poached",
                            "neutralized", "time_1st_poach_days", "time_1st_neutral_days",
                            "total_time_days"])
            for r in results:
                w.writerow([strategy, name, n_placed, r.run, r.poached, r.neutralized,
                            f"{r.time_1st_poach:.6f}", f"{r.time_1st_neutral:.6f}",
                            f"{r.total_time:.6f}"])
        out(f"Per-trial results appended to {csv_path}")
    return results, summary


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Batch (Monte-Carlo) mode of the Dzanga-Sangha elephant acoustic simulation.")
    ap.add_argument("--runs", type=int, default=50, help="Monte-Carlo trials per strategy (default 50)")
    ap.add_argument("--strategy", type=int, default=1, choices=[1, 2, 3, 4],
                    help="1=Uniform 2=Fortress 3=Perimeter 4=50/50 (default 1)")
    ap.add_argument("--all-strategies", action="store_true",
                    help="run strategies 1-4 back to back and print a comparison table")
    ap.add_argument("--mics", type=int, default=600, help="number of microphones (default 600)")
    ap.add_argument("--days", type=float, default=30, help="max sim-days per trial (default 30)")
    ap.add_argument("--dt", type=float, default=250.0, help="sim-seconds per physics step (default 250)")
    ap.add_argument("--seed", type=int, default=None, help="random seed for reproducible results")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel processes (e.g. 4). Default 1 = sequential")
    ap.add_argument("--csv", default=None, help="append per-trial results to this CSV file")
    args = ap.parse_args(argv)

    strategies = [1, 2, 3, 4] if args.all_strategies else [args.strategy]
    summaries = []
    for s in strategies:
        _, summ = run_batch(args.runs, s, args.mics, args.days, args.dt, args.seed,
                            args.workers, args.csv)
        summaries.append(summ)
    if len(summaries) > 1:
        print("\nSTRATEGY COMPARISON (%d mics, %d trials each)" % (args.mics, args.runs))
        print("%-20s %12s %14s %16s %16s" % ("Strategy", "Poached %", "Neutralized %",
                                           "1st poach (d)", "1st neutral (d)"))
        print("-" * 82)
        for s in summaries:
            print("%-20s %12.1f %14.1f %16.2f %16.2f" % (
                s["name"], s["poached_pct"], s["neutral_pct"], s["t_poach"], s["t_neut"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
