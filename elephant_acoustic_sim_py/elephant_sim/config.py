"""
Configuration & real-world scaling for the Dzanga-Sangha elephant acoustic
simulation.  Python port of the MATLAB code by Abhirath Koushik
(large_scale_sim_FINAL_ver_5_REAL.m / large_scale_sim_FINAL_ver_6_DEBUG_ONLY.m).

All distances in the MATLAB code are given in metres and converted to map
pixels with ``m2px``.  The values below are copied 1:1 from the MATLAB source.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

STRATEGY_NAMES = {
    1: "Uniform Spread",
    2: "Targeted Fortress",
    3: "Perimeter Defense",
    4: "Combination Fortress & Perimeter",   # called "50/50 Split" in the batch script
}
BATCH_STRATEGY_NAMES = {
    1: "Uniform Spread",
    2: "Targeted Fortress",
    3: "Perimeter Defense",
    4: "50/50 Split",
}

# Elephant behaviour states (MATLAB used the strings "ROAMING"/"SEEKING"/"WAITING")
ROAMING, SEEKING, WAITING = 0, 1, 2
STATE_NAMES = {ROAMING: "ROAMING", SEEKING: "SEEKING", WAITING: "WAITING"}


@dataclass
class SimConfig:
    # ---- 1. Configuration & scaling -------------------------------------
    width: int = 600
    height: int = 600
    ref_width: int = 1000
    ref_height: int = 1000
    meters_per_pixel: float = 158.0
    speed_elephant_mps: float = 1.11   # 4 km/h
    speed_poacher_mps: float = 0.55    # 2 km/h
    speed_ranger_mps: float = 5.55     # 20 km/h
    detection_probability: float = 0.90
    poach_probability: float = 0.85
    scan_interval_sim: float = 1.0     # sim-seconds between mic scans

    mic_strategy: int = 1              # 1=Uniform 2=Fortress 3=Perimeter 4=50/50
    num_mics: int = 80

    num_elephants: int = 20
    num_poachers: int = 10

    # ---- 1.5 Real-world distances (metres) -------------------------------
    rad_nola_m: float = 3040
    rad_salo_m: float = 2280
    rad_bayanga_m: float = 3040
    rad_lidjombo_m: float = 2280
    rad_mossipa_m: float = 2280
    bai_rad_m: float = 500             # NOTE: ver_5 (live) = 500 m, ver_6 (batch) = 400 m
    bai_sense_m: float = 6080
    mic_range_e_m: float = 3950        # elephant rumble detection range
    mic_range_p_m: float = 200         # poacher detection range
    poach_dist_m: float = 100          # poacher-elephant distance for an encounter
    dist_reached_m: float = 1266
    avoid_buffer_m: float = 2533
    deep_forest_m: float = 10000
    elephant_spawn_buffer_m: float = 1266   # hard-coded m2px(1266) in MATLAB
    poacher_green_repel_m: float = 3000     # hard-coded m2px(3000) in MATLAB
    ranger_catch_m: float = 500             # hard-coded m2px(500) in MATLAB
    poacher_spawn_village_m: float = 6000   # hard-coded m2px(6000)
    poacher_spawn_border_m: float = 5000    # hard-coded m2px(5000)

    # ---- Behaviour constants (hard-coded in the MATLAB loop) --------------
    velocity_blend: float = 0.05        # v = 0.95*v + 0.05*desired
    repulsion_gain: float = 4.0
    bai_attraction_gain: float = 0.8
    revisit_cooldown_s: float = 60.0    # time before an elephant re-seeks the Bai
    bai_wait_s: float = 10.0            # time spent WAITING at the Bai
    mic_memory_s: float = 14400.0       # 4 h elephant memory in a mic
    flee_factor: float = 1.2            # flee distance = avoid_buffer * 1.2

    pool_size: int = 2000
    pool_max_attempts: int = 200000
    fps_grid_step: int = 10             # mic-placement candidate grid (px)

    # ---- Faithfulness switches (ver_5 vs ver_6 differ slightly) ----------
    # ver_5 (live): start positions, pools and mic placement use the exact
    # polygon test (inpolygon); only the main loop uses the pixel lookup grid.
    # ver_6 (batch): the pixel lookup grid is used everywhere.
    exact_polygon_setup: bool = True
    # ver_5 draws the agents' first targets by fresh rejection sampling,
    # ver_6 picks them from the pre-computed pools.
    initial_targets_from_pool: bool = False

    # ------------------------------------------------------------------
    @property
    def sf_x(self) -> float:
        return self.width / self.ref_width

    @property
    def sf_y(self) -> float:
        return self.height / self.ref_height

    def m2px(self, meters: float) -> float:
        return meters / self.meters_per_pixel

    def with_(self, **kw) -> "SimConfig":
        return replace(self, **kw)

    # Presets ------------------------------------------------------------
    @classmethod
    def live(cls, **kw) -> "SimConfig":
        """Settings of large_scale_sim_FINAL_ver_5_REAL.m (interactive)."""
        base = dict(bai_rad_m=500, num_mics=80, mic_strategy=1,
                    exact_polygon_setup=True, initial_targets_from_pool=False)
        base.update(kw)
        return cls(**base)

    @classmethod
    def batch(cls, **kw) -> "SimConfig":
        """Settings of large_scale_sim_FINAL_ver_6_DEBUG_ONLY.m (Monte Carlo)."""
        base = dict(bai_rad_m=400, num_mics=600, mic_strategy=1,
                    exact_polygon_setup=False, initial_targets_from_pool=True)
        base.update(kw)
        return cls(**base)
