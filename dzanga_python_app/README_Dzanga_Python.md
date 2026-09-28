# Dzanga-Sangha Simulation - Python Port

This is a runnable Python desktop port of `large_scale_sim_FINAL_ver_5_REAL.m`.

## Requirements

- Python 3.10 or newer recommended
- NumPy
- Tkinter (normally included with standard Windows/macOS Python installers)

Install the Python dependency:

```bash
python -m pip install -r requirements.txt
```

## Run the app

```bash
python dzanga_sim.py
```

Optional command-line settings:

```bash
python dzanga_sim.py --strategy 2 --mics 80
python dzanga_sim.py --strategy 4 --mics 120 --seed 1234
```

Strategies:

1. Uniform Global Spread
2. Targeted Fortress
3. Perimeter Defense
4. 50/50 Fortress + Perimeter

The app also lets you change the strategy and microphone count and then click **RESET**.

## Background image

The MATLAB program attempts to load `dzanga_sangha_updated_black.png`. The Python app does the same if that file is placed in the same directory as `dzanga_sim.py`. If it is not present, the simulation still runs using a dark-green background.

## Test without opening a GUI

```bash
python dzanga_sim.py --headless --steps 500 --seed 1
```

This initializes the complete simulation model and runs 500 update steps.

## Main preserved behaviors

- 20 elephants and 10 poachers
- Five village repulsion zones and one Bai attraction zone
- Real-world meter-to-pixel scaling
- Four microphone placement strategies
- Elephant and poacher microphone detection probabilities
- Four-hour elephant detection memory
- Ranger deployment and interception
- Poaching encounter probability and elephant fleeing behavior
- Time-lapse control and pause/play
- Live mission report and map legend

## Notes on the port

The core simulation equations and decision rules were retained. The MATLAB figure/uicontrol interface was replaced with Tkinter Canvas/widgets so MATLAB is not required. Small numerical guards were added for zero-length direction vectors so rare exact-coordinate collisions do not cause divide-by-zero errors.
