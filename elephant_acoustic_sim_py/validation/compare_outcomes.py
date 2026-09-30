"""Statistical comparison of trial outcomes:
ORIGINAL MATLAB code (run in GNU Octave; per-trial rows parsed from its log)
vs the Python port (per-trial CSV), with identical settings.

Two-sample tests: Mann-Whitney U for counts/times, Fisher exact for the
fraction of trials in which an event happened.  p > 0.05 = no detectable
difference.  Writes validation/RESULTS.md.
"""
import csv
import pathlib
import re

import numpy as np
from scipy.stats import fisher_exact, mannwhitneyu

HERE = pathlib.Path(__file__).parent
NAMES = {1: "Uniform Spread", 2: "Targeted Fortress", 3: "Perimeter Defense", 4: "50/50 Split"}
SETS = [  # (label, octave log pattern, python csv)
    ("3-day trials, 40 mics, dt = 250 s", "octave_out/octave3d_log_s{s}.txt", "python_ref_3d.csv"),
    ("10-day trials, 40 mics, dt = 250 s", "octave_out/octave10d_log_s{s}.txt", "python_ref.csv"),
]
ROW = re.compile(r"^(\d+)\s+(\d+) / (\d+)\s+(\d+) / (\d+)\s+(---|[\d.]+ days)\s+(---|[\d.]+ days)\s+([\d.]+) days")


def parse_octave(path):
    rows = []
    for line in open(path):
        m = ROW.match(line)
        if m:
            f = lambda s: float(s.split()[0]) if s != "---" else np.nan
            rows.append((int(m[2]), int(m[4]), f(m[6]), f(m[7])))
    return np.array(rows, float).reshape(-1, 4)


def load_python(path):
    out = {}
    for r in csv.DictReader(open(path)):
        tp = float(r["time_1st_poach_days"]) or np.nan
        tn = float(r["time_1st_neutral_days"]) or np.nan
        out.setdefault(int(r["strategy"]), []).append(
            (int(r["poached"]), int(r["neutralized"]), tp, tn))
    return {k: np.array(v, float) for k, v in out.items()}


def main():
    md = ["# Python port vs original MATLAB code — outcome comparison", "",
          "The original `.m` batch script (ver_6) was executed in GNU Octave 8.4 and the Python port "
          "was run with identical settings. Random streams differ, so the two are compared "
          "statistically. p > 0.05 means no detectable difference.", ""]
    for label, opat, pcsv in SETS:
        if not (HERE / pcsv).exists():
            continue
        py = load_python(HERE / pcsv)
        for s in sorted(py):
            of = HERE / opat.format(s=s)
            if not of.exists():
                continue
            o, p = parse_octave(of), py[s]
            if len(o) == 0:
                continue
            md += [f"## {NAMES[s]} — {label}",
                   f"MATLAB/Octave trials: **{len(o)}**, Python trials: **{len(p)}**", "",
                   "| Metric | MATLAB (Octave) | Python | test | p-value |", "|---|---|---|---|---|"]
            for i, name in [(0, "Elephants poached per trial"), (1, "Poachers neutralized per trial")]:
                pv = mannwhitneyu(o[:, i], p[:, i]).pvalue
                md.append(f"| {name} | {o[:, i].mean():.2f} ± {o[:, i].std(ddof=1):.2f} | "
                          f"{p[:, i].mean():.2f} ± {p[:, i].std(ddof=1):.2f} | Mann-Whitney | {pv:.2f} |")
            for i, name in [(2, "poach"), (3, "neutralization")]:
                oe, pe = ~np.isnan(o[:, i]), ~np.isnan(p[:, i])
                pv = fisher_exact([[oe.sum(), (~oe).sum()], [pe.sum(), (~pe).sum()]]).pvalue
                md.append(f"| Trials with ≥1 {name} | {oe.mean() * 100:.0f}% | {pe.mean() * 100:.0f}% | Fisher | {pv:.2f} |")
                if oe.sum() >= 2:
                    pv = mannwhitneyu(o[oe, i], p[pe, i]).pvalue
                    md.append(f"| Days to 1st {name} | {o[oe, i].mean():.2f} ± {o[oe, i].std(ddof=1):.2f} | "
                              f"{p[pe, i].mean():.2f} ± {p[pe, i].std(ddof=1):.2f} | Mann-Whitney | {pv:.2f} |")
            md.append("")
    text = "\n".join(md)
    (HERE / "RESULTS.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
