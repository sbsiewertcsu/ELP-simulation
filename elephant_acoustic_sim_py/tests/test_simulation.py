"""
Automated tests for the Python port.

Reference data in tests/reference/ was produced by running the ORIGINAL MATLAB
code (ver_6) in GNU Octave 8.4 - see validation/.

    python -m pytest -q
"""
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from elephant_sim import Environment, SimConfig, Simulation, inpolygon  # noqa: E402
from elephant_sim.batch import run_batch, run_trial  # noqa: E402
from elephant_sim.config import ROAMING, SEEKING, WAITING  # noqa: E402
from elephant_sim.mic_placement import PLACERS  # noqa: E402

REF = ROOT / "tests" / "reference"


# ---------------------------------------------------------------- geometry
def test_inpolygon_square_and_edges():
    sq_x, sq_y = [0, 10, 10, 0, 0], [0, 0, 10, 10, 0]
    assert inpolygon(5, 5, sq_x, sq_y)
    assert not inpolygon(15, 5, sq_x, sq_y)
    assert inpolygon(10, 5, sq_x, sq_y)      # on edge counts as inside (MATLAB)
    assert inpolygon(0, 0, sq_x, sq_y)       # vertex
    assert not inpolygon(-0.001, 5, sq_x, sq_y)


def test_park_grid_matches_original_matlab():
    env = Environment(SimConfig.batch())
    ref = np.load(REF / "park_grid_octave.npz")["grid"]
    assert ref.shape == env.park_grid.shape == (601, 601)
    assert np.array_equal(ref, env.park_grid)


def test_scaling_constants():
    c = SimConfig.live()
    assert c.sf_x == 0.6 and c.sf_y == 0.6
    assert c.m2px(158) == pytest.approx(1.0)
    env = Environment(c)
    assert env.zones.rep_names == ["Nola", "Salo", "Bayanga", "Lidjombo", "Mossipa"]
    assert env.zones.att_r == pytest.approx(500 / 158)
    assert Environment(SimConfig.batch()).zones.att_r == pytest.approx(400 / 158)


# ----------------------------------------------------------- mic placement
@pytest.mark.parametrize("strategy", [1, 2, 3, 4])
@pytest.mark.parametrize("n", [80, 600])
@pytest.mark.parametrize("kind", ["grid", "poly"])
def test_mic_layout_matches_original_matlab(strategy, n, kind):
    cfg = SimConfig.batch() if kind == "grid" else SimConfig.live()
    env = Environment(cfg)
    ref = np.loadtxt(REF / f"mics_{kind}_s{strategy}_n{n}.csv", delimiter=",").reshape(-1, 2)
    got = PLACERS[strategy](env, n)
    assert got.shape == ref.shape
    assert np.allclose(got, ref, atol=1e-9, rtol=0)


@pytest.mark.parametrize("strategy", [1, 2])
def test_fps_mics_are_inside_park(strategy):
    env = Environment(SimConfig.batch())
    m = PLACERS[strategy](env, 120)
    assert env.inside_grid(m[:, 0], m[:, 1]).all()


# -------------------------------------------------------------- simulation
def _sim(seed=0, **kw):
    return Simulation(SimConfig.batch(num_mics=kw.pop("num_mics", 80), **kw), seed=seed)


def test_initial_state():
    s = _sim(1)
    env = s.env
    assert len(s.ex) == 20 and len(s.px) == 10
    assert env.valid_elephant(s.ex, s.ey).all()         # outside red zones, in park
    assert (s.e_state == ROAMING).all()
    assert not s.e_poached.any() and not s.p_caught.any()
    assert len(s.pool_general) == len(s.pool_elephant) == len(s.pool_deep) == 2000


def test_same_seed_is_reproducible_and_different_seed_differs():
    a, b, c = _sim(42), _sim(42), _sim(43)
    for _ in range(300):
        a.step(250); b.step(250); c.step(250)
    assert np.array_equal(a.ex, b.ex) and np.array_equal(a.p_caught, b.p_caught)
    assert not np.array_equal(a.ex, c.ex)


def test_agents_move_at_real_world_speed_and_stay_in_park():
    s = _sim(3)
    dt = 250.0
    step_e = 1.11 * dt / 158
    step_p = 0.55 * dt / 158
    for _ in range(400):
        ex, ey, px, py = s.ex.copy(), s.ey.copy(), s.px.copy(), s.py.copy()
        s.step(dt)
        de = np.hypot(s.ex - ex, s.ey - ey)
        dp = np.hypot(s.px - px, s.py - py)
        assert (de <= step_e + 1e-9).all()
        assert (dp <= step_p + 1e-9).all()
        # every live elephant that moved is inside the park
        assert s.env.inside_grid(s.ex[~s.e_poached], s.ey[~s.e_poached]).all()


def test_counts_are_monotonic_and_first_times_recorded():
    s = _sim(5, num_mics=600)
    prev_p = prev_c = 0
    for _ in range(3000):
        s.step(250)
        assert s.poached_count >= prev_p and s.caught_count >= prev_c
        prev_p, prev_c = s.poached_count, s.caught_count
        if s.finished():
            break
    if s.poached_count:
        assert s.time_first_poach is not None
    if s.caught_count:
        assert s.time_first_neutral is not None
        assert s.p_targeted[s.p_caught].all()      # only rangers neutralize poachers


def test_elephant_state_machine_visits_bai():
    s = _sim(11)
    seen = set()
    for _ in range(4000):
        s.step(250)
        seen.update(np.unique(s.e_state).tolist())
    assert {ROAMING, SEEKING, WAITING} <= seen


def test_ranger_dispatch_and_capture():
    """Put a poacher and elephant right on top of a mic: with detection prob 1
    the mic must alert, a ranger must start from the nearest village and
    eventually neutralize the poacher."""
    cfg = SimConfig.batch(num_mics=1, detection_probability=1.0, poach_probability=0.0,
                          num_elephants=1, num_poachers=1)
    s = Simulation(cfg, seed=0, mic_layout=np.array([[300.0, 300.0]]))
    s.ex[:] = 300.0 + 5; s.ey[:] = 300.0            # well inside 3950 m elephant range
    s.px[:] = 300.0; s.py[:] = 300.0                # inside 200 m poacher range
    s.pvx[:] = s.pvy[:] = 0
    s.t = 10.0                                      # scan interval (1 s) has elapsed
    s._scan_mics()
    assert s.m_active_e[0] and s.m_active_p[0] and s.m_threat[0]
    assert s.p_targeted[0]
    z = s.env.zones
    nearest = np.argmin(np.hypot(300 - z.rep_x, 300 - z.rep_y))
    assert (s.base_x[0], s.base_y[0]) == (z.rep_x[nearest], z.rep_y[nearest])
    for _ in range(2000):
        s.step(60)
        if s.p_caught[0]:
            break
    assert s.p_caught[0]


def test_poaching_roll_happens_once_per_encounter():
    cfg = SimConfig.batch(num_mics=0, poach_probability=1.0, num_elephants=1, num_poachers=1)
    s = Simulation(cfg, seed=0, mic_layout=np.zeros((0, 2)))
    s.ex[:] = 200.0; s.ey[:] = 200.0
    s.px[:] = 200.3; s.py[:] = 200.0                # < 100 m (0.63 px)
    s._poaching_check()
    assert s.e_poached[0] and s.time_first_poach is not None

    cfg = SimConfig.batch(num_mics=0, poach_probability=0.0, num_elephants=1, num_poachers=1)
    s = Simulation(cfg, seed=0, mic_layout=np.zeros((0, 2)))
    s.ex[:] = 200.0; s.ey[:] = 200.0
    s.px[:] = 200.3; s.py[:] = 200.0
    s._poaching_check()
    assert not s.e_poached[0] and s.e_rolled[0] and s.e_threatened[0]
    # escape: elephant's new target is directly away from the poacher
    assert s.etx[0] < s.ex[0]


# ------------------------------------------------------------------ batch
def test_batch_runs_and_summarises():
    results, summary = run_batch(num_runs=3, strategy=4, num_mics=100, max_days=2,
                                 sim_dt=250, seed=1, quiet=True)
    assert len(results) == 3
    for r in results:
        assert 0 <= r.poached <= 20 and 0 <= r.neutralized <= 10
        assert 0 < r.total_time <= 2 + 250 / 86400
    assert set(summary) >= {"poached_pct", "neutral_pct"}


def test_batch_parallel_equals_sequential():
    a, _ = run_batch(num_runs=2, strategy=1, num_mics=60, max_days=1, seed=9, quiet=True)
    b, _ = run_batch(num_runs=2, strategy=1, num_mics=60, max_days=1, seed=9, quiet=True, workers=2)
    assert [(r.poached, r.neutralized, r.total_time) for r in a] == \
           [(r.poached, r.neutralized, r.total_time) for r in b]


# -------------------------------------------------------------- dashboard
def test_dashboard_snapshot(tmp_path):
    from elephant_sim.live_dashboard import main
    out = tmp_path / "snap.png"
    assert main(["--seed", "2", "--snapshot", str(out), "--snapshot-hours", "2",
                 "--strategy", "4", "--mics", "40"]) == 0
    assert out.exists() and out.stat().st_size > 50_000
