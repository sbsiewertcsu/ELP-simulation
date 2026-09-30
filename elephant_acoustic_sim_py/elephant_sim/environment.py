"""
Park geometry: boundary polygon, villages (red zones), Dzanga Bai (green
zone), the fast pixel-grid boundary lookup and the pre-computed pools of valid
target positions.  Mirrors sections 2, 3, 4.5 and 5.5 of the MATLAB code.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SimConfig

# Section 2 of the MATLAB code - park outline in a 1000x1000 reference frame
REF_POLY_X = np.array([
    50, 150, 300, 450, 600, 680, 750, 850, 980,
    980, 850, 720, 650, 620, 640, 620, 550, 500,
    450, 380, 350, 350, 320, 250, 200, 100, 50,
    20, 50,
], dtype=float)
REF_POLY_Y = np.array([
    150, 100, 60, 50, 20, 20, 20, 30, 40,
    120, 140, 140, 300, 400, 500, 650, 800, 900,
    1000, 850, 750, 650, 550, 520, 480, 400, 300,
    280, 150,
], dtype=float)

# Section 3 - villages (reference-frame coordinates, radius config attribute)
VILLAGES = [
    ("Nola", 320, 220, "rad_nola_m"),
    ("Salo", 380, 430, "rad_salo_m"),
    ("Bayanga", 480, 600, "rad_bayanga_m"),
    ("Lidjombo", 380, 750, "rad_lidjombo_m"),
    ("Mossipa", 190, 120, "rad_mossipa_m"),
]
BAI_REF = (550, 550)


def matlab_round(v):
    """MATLAB round(): halves are rounded away from zero (numpy rounds to even)."""
    v = np.asarray(v, dtype=float)
    return np.sign(v) * np.floor(np.abs(v) + 0.5)


def inpolygon(x, y, xv, yv, tol: float = 1e-9):
    """Vectorised equivalent of MATLAB ``inpolygon`` (points on the edge count
    as inside).  Uses the even-odd crossing rule plus an explicit on-edge test.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    shape = np.broadcast(x, y).shape
    px = np.broadcast_to(x, shape).ravel()
    py = np.broadcast_to(y, shape).ravel()

    xv = np.asarray(xv, dtype=float)
    yv = np.asarray(yv, dtype=float)
    x1, y1 = xv, yv
    x2, y2 = np.roll(xv, -1), np.roll(yv, -1)

    inside = np.zeros(px.shape, dtype=bool)
    on_edge = np.zeros(px.shape, dtype=bool)
    for i in range(len(xv)):
        ax, ay, bx, by = x1[i], y1[i], x2[i], y2[i]
        if ax == bx and ay == by:          # zero-length closing edge
            continue
        # crossing test (even-odd)
        cond = (ay > py) != (by > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (bx - ax) * (py - ay) / (by - ay) + ax
        inside ^= cond & (px < xint)
        # on-edge test
        seg_len = np.hypot(bx - ax, by - ay)
        cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
        near_line = np.abs(cross) <= tol * seg_len * max(1.0, seg_len)
        within = ((px >= min(ax, bx) - tol) & (px <= max(ax, bx) + tol) &
                  (py >= min(ay, by) - tol) & (py <= max(ay, by) + tol))
        on_edge |= near_line & within
    return (inside | on_edge).reshape(shape)


@dataclass
class Zones:
    rep_x: np.ndarray
    rep_y: np.ndarray
    rep_r: np.ndarray
    rep_names: list
    att_x: float
    att_y: float
    att_r: float
    att_sense: float


class Environment:
    """Everything static about the park."""

    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        W, H = cfg.width, cfg.height
        self.boundary_x = REF_POLY_X * cfg.sf_x
        self.boundary_y = REF_POLY_Y * cfg.sf_y

        self.zones = Zones(
            rep_x=np.array([v[1] * cfg.sf_x for v in VILLAGES]),
            rep_y=np.array([v[2] * cfg.sf_y for v in VILLAGES]),
            rep_r=np.array([cfg.m2px(getattr(cfg, v[3])) for v in VILLAGES]),
            rep_names=[v[0] for v in VILLAGES],
            att_x=BAI_REF[0] * cfg.sf_x,
            att_y=BAI_REF[1] * cfg.sf_y,
            att_r=cfg.m2px(cfg.bai_rad_m),
            att_sense=cfg.m2px(cfg.bai_sense_m),
        )

        # Section 5.5 - pre-computed (H+1)x(W+1) lookup grid of the polygon
        gx, gy = np.meshgrid(np.arange(W + 1), np.arange(H + 1))
        self.park_grid = inpolygon(gx, gy, self.boundary_x, self.boundary_y)

    # ------------------------------------------------------------------
    def inside_exact(self, x, y):
        """MATLAB: inpolygon(x, y, park_boundary_x, park_boundary_y)"""
        return inpolygon(x, y, self.boundary_x, self.boundary_y)

    def inside_grid(self, x, y):
        """MATLAB: park_grid(min(max(round(y)+1,1),H+1), min(max(round(x)+1,1),W+1))
        (converted to 0-based indexing)."""
        W, H = self.cfg.width, self.cfg.height
        r = np.clip(matlab_round(y), 0, H).astype(int)
        c = np.clip(matlab_round(x), 0, W).astype(int)
        return self.park_grid[r, c]

    def inside_setup(self, x, y):
        """Boundary test used during initialisation (exact in ver_5, grid in ver_6)."""
        if self.cfg.exact_polygon_setup:
            return self.inside_exact(x, y)
        return self.inside_grid(x, y)

    # ------------------------------------------------------------------
    # Validity rules shared by spawning / target selection / pools
    def valid_general(self, x, y):
        """Inside park and away from the Bai (poacher targets)."""
        z, c = self.zones, self.cfg
        d = np.hypot(x - z.att_x, y - z.att_y)
        return self.inside_setup(x, y) & (d > z.att_r + c.m2px(c.avoid_buffer_m))

    def valid_elephant(self, x, y):
        """Inside park and outside every red zone (+1266 m buffer)."""
        z, c = self.zones, self.cfg
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        ok = self.inside_setup(x, y)
        buf = c.m2px(c.elephant_spawn_buffer_m)
        for rx, ry, rr in zip(z.rep_x, z.rep_y, z.rep_r):
            ok = ok & ~(np.hypot(x - rx, y - ry) < rr + buf)
        return ok

    def valid_deep(self, x, y):
        """Inside park and deep in the forest (> 10 km from the Bai)."""
        z, c = self.zones, self.cfg
        d = np.hypot(x - z.att_x, y - z.att_y)
        return self.inside_setup(x, y) & (d > c.m2px(c.deep_forest_m))

    # ------------------------------------------------------------------
    def sample_valid(self, rng: np.random.Generator, rule, n: int = 1):
        """Rejection-sample n points uniformly in [0,W]x[0,H] satisfying rule."""
        W, H = self.cfg.width, self.cfg.height
        out = []
        need = n
        while need > 0:
            m = max(64, need * 4)
            xs = rng.random(m) * W
            ys = rng.random(m) * H
            ok = rule(xs, ys)
            pts = np.column_stack([xs[ok], ys[ok]])[:need]
            out.append(pts)
            need -= len(pts)
        return np.vstack(out)

    def build_pool(self, rng: np.random.Generator, rule) -> np.ndarray:
        """Section 4.5: up to POOL_SIZE valid points from at most 200000 attempts."""
        c = self.cfg
        W, H = c.width, c.height
        xs = rng.random(c.pool_max_attempts) * W
        ys = rng.random(c.pool_max_attempts) * H
        ok = rule(xs, ys)
        pts = np.column_stack([xs[ok], ys[ok]])
        return pts[: c.pool_size]

    def build_pools(self, rng: np.random.Generator):
        pool_general = self.build_pool(rng, self.valid_general)
        pool_elephant = self.build_pool(rng, self.valid_elephant)
        pool_deep = self.build_pool(rng, self.valid_deep)
        if len(pool_deep) == 0:
            pool_deep = pool_elephant
        return pool_general, pool_elephant, pool_deep
