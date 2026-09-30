"""Compare Python park grid + mic layouts against the Octave run of the original MATLAB."""
import sys, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from elephant_sim import SimConfig, Environment
from elephant_sim.mic_placement import PLACERS

OUT = pathlib.Path(__file__).parent / "octave_out"
ok_all = True
env_b = Environment(SimConfig.batch())
env_l = Environment(SimConfig.live())
g = (np.loadtxt(OUT / "park_grid.csv", delimiter=",").astype(bool) if (OUT / "park_grid.csv").exists()
     else np.load(pathlib.Path(__file__).parents[1] / "tests/reference/park_grid_octave.npz")["grid"])
diff = (g != env_b.park_grid).sum()
print(f"park_grid: {g.sum()} inside cells (octave) vs {env_b.park_grid.sum()} (python); mismatched cells = {diff}")
ok_all &= diff == 0
for kind, env in (("grid", env_b), ("poly", env_l)):
    for S in (1, 2, 3, 4):
        for N in (40, 80, 600):
            o = np.loadtxt(OUT / f"mics_{kind}_s{S}_n{N}.csv", delimiter=",").reshape(-1, 2)
            p = PLACERS[S](env, N)
            same_n = len(o) == len(p)
            err = np.abs(o - p).max() if same_n else float("inf")
            ok = same_n and err < 1e-9
            ok_all &= ok
            print(f"  {kind} strategy {S} N={N:3d}: octave {len(o):3d} mics, python {len(p):3d}, max |diff| = {err:.2e}  {'OK' if ok else 'MISMATCH'}")
print("ALL MATCH" if ok_all else "SOME MISMATCHES")
