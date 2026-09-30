# Python port vs original MATLAB code — outcome comparison

The original `.m` batch script (ver_6) was executed in GNU Octave 8.4 and the Python port was run with identical settings. Random streams differ, so the two are compared statistically. p > 0.05 means no detectable difference.

## Uniform Spread — 3-day trials, 40 mics, dt = 250 s
MATLAB/Octave trials: **40**, Python trials: **400**

| Metric | MATLAB (Octave) | Python | test | p-value |
|---|---|---|---|---|
| Elephants poached per trial | 1.38 ± 1.05 | 1.40 ± 1.14 | Mann-Whitney | 0.84 |
| Poachers neutralized per trial | 2.45 ± 1.32 | 2.47 ± 1.37 | Mann-Whitney | 0.94 |
| Trials with ≥1 poach | 88% | 77% | Fisher | 0.16 |
| Days to 1st poach | 0.99 ± 0.81 | 1.15 ± 0.76 | Mann-Whitney | 0.13 |
| Trials with ≥1 neutralization | 92% | 95% | Fisher | 0.44 |
| Days to 1st neutralization | 0.90 ± 0.61 | 1.00 ± 0.76 | Mann-Whitney | 0.76 |

## Perimeter Defense — 3-day trials, 40 mics, dt = 250 s
MATLAB/Octave trials: **40**, Python trials: **400**

| Metric | MATLAB (Octave) | Python | test | p-value |
|---|---|---|---|---|
| Elephants poached per trial | 1.57 ± 1.01 | 1.63 ± 1.23 | Mann-Whitney | 0.94 |
| Poachers neutralized per trial | 0.50 ± 0.72 | 0.37 ± 0.57 | Mann-Whitney | 0.31 |
| Trials with ≥1 poach | 85% | 82% | Fisher | 0.83 |
| Days to 1st poach | 0.99 ± 0.78 | 1.19 ± 0.78 | Mann-Whitney | 0.12 |
| Trials with ≥1 neutralization | 40% | 33% | Fisher | 0.38 |
| Days to 1st neutralization | 1.26 ± 0.78 | 1.37 ± 0.89 | Mann-Whitney | 0.65 |

## Uniform Spread — 10-day trials, 40 mics, dt = 250 s
MATLAB/Octave trials: **5**, Python trials: **300**

| Metric | MATLAB (Octave) | Python | test | p-value |
|---|---|---|---|---|
| Elephants poached per trial | 4.00 ± 1.73 | 3.44 ± 1.83 | Mann-Whitney | 0.32 |
| Poachers neutralized per trial | 5.80 ± 1.92 | 6.07 ± 1.58 | Mann-Whitney | 0.81 |
| Trials with ≥1 poach | 100% | 98% | Fisher | 1.00 |
| Days to 1st poach | 0.59 ± 0.33 | 1.94 ± 1.94 | Mann-Whitney | 0.07 |
| Trials with ≥1 neutralization | 100% | 100% | Fisher | 1.00 |
| Days to 1st neutralization | 1.19 ± 0.94 | 1.06 ± 1.03 | Mann-Whitney | 0.56 |

## Perimeter Defense — 10-day trials, 40 mics, dt = 250 s
MATLAB/Octave trials: **5**, Python trials: **300**

| Metric | MATLAB (Octave) | Python | test | p-value |
|---|---|---|---|---|
| Elephants poached per trial | 5.80 ± 1.10 | 4.85 ± 1.86 | Mann-Whitney | 0.21 |
| Poachers neutralized per trial | 0.80 ± 0.84 | 0.90 ± 0.90 | Mann-Whitney | 0.89 |
| Trials with ≥1 poach | 100% | 99% | Fisher | 1.00 |
| Days to 1st poach | 1.86 ± 1.96 | 1.66 ± 1.54 | Mann-Whitney | 0.84 |
| Trials with ≥1 neutralization | 60% | 62% | Fisher | 1.00 |
| Days to 1st neutralization | 2.61 ± 1.74 | 3.18 ± 2.57 | Mann-Whitney | 0.94 |

