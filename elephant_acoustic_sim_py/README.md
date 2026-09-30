# Elephant Acoustic Simulation — Python version

A full Python rebuild of the MATLAB simulation *"Acoustic Detection of Elephants
to Prevent Poaching at Dzanga-Sangha National Park"* (original author: Abhirath
Koushik). It needs no MATLAB licence, only Python, NumPy and Matplotlib.

The MATLAB project had two scripts, and each one has a Python equivalent:

| Original MATLAB file | Python equivalent | What it does |
|---|---|---|
| `large_scale_sim_FINAL_ver_5_REAL.m` | `python run_live.py` | Live animated dashboard: map, agents, mics, sidebar, legend, time-lapse slider, play/pause |
| `large_scale_sim_FINAL_ver_6_DEBUG_ONLY.m` | `python run_batch.py` | Batch/Monte-Carlo mode with no graphics. It prints the same per-trial table and summary |
| `large_scale_sim_FINAL_ver_5_REAL.asv` | `python run_live.py --strategy 4 --mics 40` | MATLAB autosave file. It only differs in those two settings |

---

## Step-by-step: how to run it

### Step 1 — Install Python (one time)
You need **Python 3.9 or newer**. To check, open a terminal and type:
```
python --version
```
* **Windows:** install from <https://www.python.org/downloads/>. On the first installer
  screen, tick **"Add python.exe to PATH"**. Then open **Command Prompt** or **PowerShell**.
* **macOS:** `brew install python`, or use the python.org installer. Use the **Terminal** app.
  On macOS the command may be `python3` instead of `python`.
* **Linux:** Python is usually already installed. If it isn't: `sudo apt install python3 python3-pip python3-venv python3-tk`.

### Step 2 — Unzip the project and open a terminal inside it
```
cd path/to/elephant_acoustic_sim_py
```
This folder contains `run_live.py`, `run_batch.py`, `requirements.txt` and so on.

### Step 3 — Create a virtual environment (recommended) and install the libraries
```
python -m venv .venv
```
Activate it:
* Windows (PowerShell): `.venv\Scripts\Activate.ps1`   (Command Prompt: `.venv\Scripts\activate.bat`)
* macOS / Linux: `source .venv/bin/activate`

Then install:
```
pip install -r requirements.txt
```

### Step 4 — Run the live dashboard (the MATLAB ver_5 simulation)
```
python run_live.py
```
A window opens and counts down *"STARTING IN 10…"* before the simulation begins.
* **Time-lapse slider** (bottom): drag it to set the speed from 1× to 5000× real time (starts at 1000×).
* **PAUSE || / PLAY ►** button: freezes and resumes the physics. The **space bar** does the same.
* The **LIVE MISSION REPORT** sidebar shows the elapsed time and the elephant and poacher counts.
* Close the window to stop.

Common variations:
```
python run_live.py --strategy 2 --mics 80      # Targeted Fortress
python run_live.py --strategy 3                # Perimeter Defense
python run_live.py --strategy 4 --mics 40      # 50/50 Fortress + Perimeter
python run_live.py --countdown 0 --speed 3000  # start immediately at 3000x
python run_live.py --seed 7                    # reproducible run
```

| Option | Default | Meaning |
|---|---|---|
| `--strategy` | 1 | 1 = Uniform Spread, 2 = Targeted Fortress, 3 = Perimeter Defense, 4 = Fortress + Perimeter |
| `--mics` | 80 | number of microphones |
| `--elephants` / `--poachers` | 20 / 10 | number of agents |
| `--speed` | 1000 | initial time-lapse multiplier |
| `--countdown` | 10 | start-up countdown in seconds |
| `--seed` | random | random seed. Omit it for a different run every time (same as MATLAB `rng('shuffle')`) |
| `--snapshot out.png` | — | no window: run headless and save a picture of the dashboard |
| `--snapshot-hours` | 24 | sim-hours to advance before the snapshot is taken |

### Step 5 — Run the batch statistics (the MATLAB ver_6 simulation)
With the same defaults as the MATLAB file (50 trials, strategy 1, 600 mics, 30 days, dt = 250 s):
```
python run_batch.py
```
Other examples:
```
python run_batch.py --strategy 3 --runs 100 --mics 200
python run_batch.py --all-strategies --runs 50 --workers 4 --csv results.csv
python run_batch.py --seed 123            # reproducible
```

| Option | Default | Meaning |
|---|---|---|
| `--runs` | 50 | Monte-Carlo trials per strategy (`NUM_RUNS`) |
| `--strategy` | 1 | mic strategy (`MIC_STRATEGY`) |
| `--all-strategies` | off | run strategies 1–4 and print a comparison table |
| `--mics` | 600 | `NUM_MICS` |
| `--days` | 30 | `MAX_SIM_DAYS` |
| `--dt` | 250 | `SIM_DT`, sim-seconds per physics step |
| `--seed` | random | reproducible results |
| `--workers` | 1 | run trials in parallel on several CPU cores |
| `--csv FILE` | — | append every trial's results to a CSV file (for Excel, pandas and so on) |

Each trial stops when all elephants are poached, when all poachers are neutralized, or when `--days` is reached, exactly as in MATLAB.
The output looks like this:
```
Trial  Poached      Neutralized  Time 1st Poach     Time 1st Neutral   Total Time
------------------------------------------------------------------------------------
1      1 / 20       10 / 10      0.29 days          0.10 days          1.88 days
...
  SUMMARY — Uniform Spread  |  600 Mics  |  50 Trials
  Elephants poached    — Mean: 3.3%  |  Std: 2.9%  |  Min: 0%  |  Max: 5%
  ...
```

### Step 6 (optional) — Run the tests
```
python -m pytest -q
```
There are 31 tests. They include checks that the park geometry and all mic
layouts are identical to the output of the original MATLAB code.

### Using it from your own Python code / Jupyter
```python
from elephant_sim import SimConfig, Simulation
sim = Simulation(SimConfig.batch(mic_strategy=2, num_mics=300), seed=1)
while sim.t < 10 * 86400 and not sim.finished():
    sim.step(250)                       # 250 sim-seconds per step
print(sim.poached_count, sim.caught_count, sim.time_first_neutral / 86400)
```
Every parameter in the MATLAB code (speeds, ranges, probabilities, zone radii, mic
memory time and so on) is a field of `SimConfig` in `elephant_sim/config.py`. You can
override any of them, for example `SimConfig.batch(detection_probability=0.8)`.

---

## Project layout
```
elephant_acoustic_sim_py/
├── run_live.py                 # entry point: live dashboard (ver_5)
├── run_batch.py                # entry point: batch statistics (ver_6)
├── requirements.txt
├── assets/dzanga_sangha_updated_black.png   # map background (from the MATLAB repo)
├── elephant_sim/
│   ├── config.py               # all constants + real-world scaling (MATLAB section 1/1.5)
│   ├── environment.py          # park polygon, inpolygon, villages, Bai, lookup grid, pools
│   ├── mic_placement.py        # the 4 placement strategies (MATLAB place_mics_* functions)
│   ├── simulation.py           # physics engine: movement, mics, rangers, poaching (main loop)
│   ├── live_dashboard.py       # matplotlib GUI
│   └── batch.py                # Monte-Carlo runner + summary statistics
├── tests/                      # pytest suite + reference data produced by the MATLAB code
└── validation/                 # scripts used to cross-check against the original MATLAB code
```

## How it was checked against the original MATLAB code
The original `.m` code was run in GNU Octave 8.4 with its logic unchanged.
`validation/make_octave_scripts.py` applies only the syntax patches Octave needs.
1. **Deterministic parts are identical.** The park lookup grid (140,362 inside cells) matches, and so does
   every microphone layout (4 strategies × 40/80/600 mics × both boundary-test variants), to within 1e-12 px.
2. **Lock-step trace comparison** (`validation/lockstep_compare.py` → `validation/LOCKSTEP_RESULTS.md`).
   Both codes were started from the same initial state, with the random picks replaced by the same
   deterministic function. Every step compared 226 values: all positions, targets, ranger positions,
   poached/caught/targeted flags, elephant states and mic counts. Across 4 scenarios (every strategy,
   poaching, escapes, ranger captures, about 3,800 steps in total), the largest position difference was
   5e-8 px and there were **zero** mismatches in any discrete value.
3. **Random outcomes agree statistically.** Batch runs of the original and the Python version were compared
   with the same settings; no metric differs significantly (p > 0.05). See `validation/RESULTS.md`.
4. **The GUI was driven for real** (`validation/gui_smoke_test.py`, Qt backend): the countdown, the slider
   changing the speed, PAUSE freezing sim-time and PLAY resuming it.

## Differences from the MATLAB version (all minor)
1. **Random numbers.** Python's generator is not MATLAB's, so a given run won't replay
   MATLAB's run step for step. The statistics are the same. `--seed` makes Python runs reproducible.
2. **Vectorised with NumPy.** The logic and the order of operations are unchanged, and it is much faster.
   A full-length 600-mic, 30-day trial takes a few seconds, and trials that end early take under a second.
   Use `--workers N` to spread trials over CPU cores.
3. **Live mode caps each frame at 0.5 real seconds.** MATLAB had no cap, so dragging or stalling the window
   could make agents jump a large distance in one frame.
4. **Divide-by-zero guards.** MATLAB would have produced NaN if an agent landed exactly on its target or on a zone
   centre.
5. The neutralized-poacher marker is a star (`*`) because matplotlib has no pentagram marker.
6. **The ver_5 and ver_6 differences are kept as they were.** The Dzanga Bai radius is 500 m in the live script
   and 400 m in the batch script, and start positions and initial targets are drawn slightly differently.
   `SimConfig.live()` and `SimConfig.batch()` reproduce each script.

### Behaviours of the original model that were kept as-is (worth knowing for the paper)
* An elephant in the `WAITING` state at the Bai has a desired velocity of zero. However, the blended
  velocity is re-normalised to unit length, so it keeps moving at full speed while "waiting".
* When an elephant switches from `WAITING` to `ROAMING`, the distance used for that step still refers
  to its old target, as in MATLAB.
* A mic alert sends a ranger to **every** untargeted poacher within 200 m of that mic, not only the
  poachers that were actually detected.
