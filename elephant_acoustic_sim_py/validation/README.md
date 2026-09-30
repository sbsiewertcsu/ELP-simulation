# Validation against the original MATLAB code

Everything here is optional — it is how the Python port was verified. It needs
GNU Octave (`sudo apt install octave`, or `brew install octave`) and `pip install scipy`.

| Script | What it does | Result file |
|---|---|---|
| `make_octave_scripts.py` | Makes Octave-runnable copies of the original `.m` files (syntax patches only: local functions moved to the top, string `==` → `strcmp`, config from env vars) | `oct_*.m` |
| `compare_placement.py` | Park lookup grid + all mic layouts, Python vs original (exact) | printed |
| `lockstep_compare.py` | Runs original and Python in lock-step with the same deterministic "random" picks and compares 226 values every step | `LOCKSTEP_RESULTS.md` |
| `compare_outcomes.py` | Statistical comparison of batch results (Octave logs vs Python CSV) | `RESULTS.md` |
| `gui_smoke_test.py` | Drives the real interactive window (countdown, slider, pause/play) | printed |

Re-running the Octave batch comparison (slow — Octave takes ~1 min per 3-day trial):
```
cd validation && python make_octave_scripts.py && cd octave_out
RUNS=40 NMICS=40 DAYS=3 OUTDIR=. octave --no-gui --quiet ../oct_batch_s1.m > octave3d_log_s1.txt
cd ../.. && python run_batch.py --runs 400 --strategy 1 --mics 40 --days 3 --csv validation/python_ref_3d.csv
python validation/compare_outcomes.py
```
GUI test on a headless Linux box: `xvfb-run -a env MPLBACKEND=QtAgg python validation/gui_smoke_test.py`
