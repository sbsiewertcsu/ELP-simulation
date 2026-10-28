"""Tests for the random-mesh placement and the mic-count sweep runner."""
import csv
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from elephant_sim import Environment, SimConfig  # noqa: E402
from elephant_sim.mic_placement import place_mics, place_mics_random  # noqa: E402
from elephant_sim.sweep import COLUMNS, run_sweep  # noqa: E402


def test_random_mesh_valid_and_reproducible():
    env = Environment(SimConfig.batch())
    a = place_mics_random(env, 40, np.random.default_rng(1))
    b = place_mics_random(env, 40, np.random.default_rng(1))
    c = place_mics_random(env, 40, np.random.default_rng(2))
    assert a.shape == (40, 2)
    assert np.array_equal(a, b) and not np.array_equal(a, c)
    assert env.inside_setup(a[:, 0], a[:, 1]).all()
    assert len(np.unique(a, axis=0)) == 40                  # no duplicate sites
    assert place_mics(env, 5, 0).shape == (0, 2)
    assert place_mics_random(env, 0, np.random.default_rng(1)).shape == (0, 2)


def test_place_mics_rejects_unknown_strategy():
    env = Environment(SimConfig.batch())
    try:
        place_mics(env, 9, 10)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_sweep_rows_resume_and_pairing(tmp_path):
    out = str(tmp_path / "s.csv")
    kw = dict(runs=2, mic_min=10, mic_max=15, mic_step=5, strategies=(1, 5),
              max_days=0.5, dt=250.0, seed=3, workers=1, quiet=True)
    run_sweep(out, **kw)
    rows = list(csv.DictReader(open(out)))
    assert list(rows[0].keys()) == COLUMNS
    assert len(rows) == 2 + 2 * 2 * 2        # control + 2 counts x 2 strategies x 2 trials
    assert {r["strategy_name"] for r in rows} == {"No Mics", "Uniform Spread", "Random Mesh"}
    assert all(0 <= int(r["poached"]) <= 20 for r in rows)
    run_sweep(out, **kw)                      # resume: nothing new to run
    assert len(list(csv.DictReader(open(out)))) == len(rows)
    # same seeds -> reproducible results
    out2 = str(tmp_path / "s2.csv")
    run_sweep(out2, **kw)
    key = lambda r: (r["strategy"], r["num_mics"], r["trial"])
    a = {key(r): r["poached"] for r in rows}
    b = {key(r): r["poached"] for r in csv.DictReader(open(out2))}
    assert a == b
