"""
The four microphone placement strategies (MATLAB functions
place_mics_uniform / place_mics_fortress / place_mics_perimeter /
place_mics_optimized_web).  All are deterministic.

Each function returns an (N, 2) float array of mic (x, y) positions in map
pixels, in the same order MATLAB would produce them.
"""
from __future__ import annotations

import numpy as np

from .config import SimConfig
from .environment import Environment


def _candidate_grid(width, height, inside, step=10):
    """Dense grid of valid positions.  MATLAB loops gx outer, gy inner, so the
    candidate order (which matters for tie-breaking in max()) is preserved."""
    gx = np.arange(step, width + 1, step, dtype=float)
    gy = np.arange(step, height + 1, step, dtype=float)
    GX, GY = np.meshgrid(gx, gy, indexing="ij")      # gx outer, gy inner
    cx, cy = GX.ravel(), GY.ravel()
    ok = np.asarray(inside(cx, cy), dtype=bool)
    return np.column_stack([cx[ok], cy[ok]])


def _fps_fill(candidates, placed, num_mics):
    """Farthest Point Sampling: keep adding the candidate farthest from every
    mic placed so far until num_mics are placed."""
    placed = list(map(tuple, placed))
    if len(candidates) == 0:
        return np.array(placed, dtype=float).reshape(-1, 2)
    min_d = np.full(len(candidates), np.inf)
    for (mx, my) in placed:
        min_d = np.minimum(min_d, np.hypot(candidates[:, 0] - mx, candidates[:, 1] - my))
    while len(placed) < num_mics:
        best = int(np.argmax(min_d))            # first index on ties, like MATLAB max
        bx, by = candidates[best]
        placed.append((bx, by))
        min_d = np.minimum(min_d, np.hypot(candidates[:, 0] - bx, candidates[:, 1] - by))
    return np.array(placed, dtype=float).reshape(-1, 2)


def _village_rings(env: Environment, inside, per_village, cap, range_p):
    z = env.zones
    placed = []
    for r in range(len(z.rep_x)):
        ring = z.rep_r[r] + range_p
        for i in range(1, per_village + 1):
            ang = (i / per_village) * 2 * np.pi
            mx = z.rep_x[r] + ring * np.cos(ang)
            my = z.rep_y[r] + ring * np.sin(ang)
            if bool(inside(mx, my)) and len(placed) < cap:
                placed.append((mx, my))
    return placed


def _perimeter(bx, by, range_p, spacing, start_count, num_mics):
    placed = []
    count = start_count
    curr = 0.0
    seg = 0
    n = len(bx)
    while count < num_mics and seg < n - 1:
        p1 = np.array([bx[seg], by[seg]])
        p2 = np.array([bx[seg + 1], by[seg + 1]])
        seg_len = float(np.hypot(*(p2 - p1)))
        while curr + spacing <= seg_len and count < num_mics:
            curr += spacing
            ratio = curr / seg_len
            mx = p1[0] + ratio * (p2[0] - p1[0])
            my = p1[1] + ratio * (p2[1] - p1[1])
            d = (p2 - p1) / seg_len
            normal = np.array([-d[1], d[0]])
            mx += normal[0] * range_p * 0.5
            my += normal[1] * range_p * 0.5
            count += 1
            placed.append((mx, my))
        curr -= seg_len
        seg += 1
    return placed


def _boundary_length(bx, by):
    # Sequential left-to-right sum exactly like the MATLAB for-loop.  (np.sum
    # uses pairwise summation, whose last-bit rounding difference changes
    # whether the final perimeter mic fits on the last segment.)
    total = 0.0
    for i in range(len(bx) - 1):
        total += float(np.sqrt((bx[i + 1] - bx[i]) ** 2 + (by[i + 1] - by[i]) ** 2))
    return total


# ---------------------------------------------------------------------------
def place_mics_uniform(env: Environment, num_mics: int, inside=None):
    """Strategy 1 - Uniform global spread via farthest point sampling, seeded
    at the candidate closest to the park centroid."""
    c = env.cfg
    inside = inside or env.inside_setup
    cands = _candidate_grid(c.width, c.height, inside, c.fps_grid_step)
    if len(cands) == 0 or num_mics <= 0:
        return np.zeros((0, 2))
    centroid = cands.mean(axis=0)
    seed = int(np.argmin(np.hypot(*(cands - centroid).T)))
    return _fps_fill(cands, [tuple(cands[seed])], num_mics)


def place_mics_fortress(env: Environment, num_mics: int, inside=None):
    """Strategy 2 - 75 % of mics in rings around the villages, rest by FPS."""
    c = env.cfg
    inside = inside or env.inside_setup
    range_p = c.m2px(c.mic_range_p_m)
    n_vil = len(env.zones.rep_x)
    budget = int(matlab_round_scalar(num_mics * 0.75))
    per_village = budget // n_vil
    placed = _village_rings(env, inside, per_village, num_mics, range_p)
    cands = _candidate_grid(c.width, c.height, inside, c.fps_grid_step)
    return _fps_fill(cands, placed, num_mics)


def place_mics_perimeter(env: Environment, num_mics: int, inside=None):
    """Strategy 3 - evenly spaced along the park boundary."""
    c = env.cfg
    if num_mics <= 0:
        return np.zeros((0, 2))
    bx, by = env.boundary_x, env.boundary_y
    spacing = _boundary_length(bx, by) / num_mics
    placed = _perimeter(bx, by, c.m2px(c.mic_range_p_m), spacing, 0, num_mics)
    return np.array(placed, dtype=float).reshape(-1, 2)


def place_mics_optimized_web(env: Environment, num_mics: int, inside=None):
    """Strategy 4 - 50 % village rings, 50 % perimeter, FPS for any leftover."""
    c = env.cfg
    inside = inside or env.inside_setup
    range_p = c.m2px(c.mic_range_p_m)
    half = num_mics // 2
    n_vil = len(env.zones.rep_x)
    per_village = half // n_vil
    placed = _village_rings(env, inside, per_village, half, range_p)

    bx, by = env.boundary_x, env.boundary_y
    if half > 0:
        spacing = _boundary_length(bx, by) / half
        placed += _perimeter(bx, by, range_p, spacing, len(placed), num_mics)

    if len(placed) < num_mics:
        cands = _candidate_grid(c.width, c.height, inside, c.fps_grid_step)
        return _fps_fill(cands, placed, num_mics)
    return np.array(placed, dtype=float).reshape(-1, 2)


def matlab_round_scalar(v: float) -> float:
    return float(np.sign(v) * np.floor(abs(v) + 0.5))


PLACERS = {
    1: place_mics_uniform,
    2: place_mics_fortress,
    3: place_mics_perimeter,
    4: place_mics_optimized_web,
}


def place_mics(env: Environment, strategy: int, num_mics: int) -> np.ndarray:
    if strategy not in PLACERS:
        raise ValueError(f"Unknown mic strategy {strategy}; use 1, 2, 3 or 4")
    return PLACERS[strategy](env, num_mics)
