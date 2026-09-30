"""
Core simulation physics - a line-by-line port of the MATLAB main loop
(sections 4, 5 and 7 of ver_5 / the simulation loop of ver_6), vectorised with
NumPy.  Graphics are kept completely separate (see live_dashboard.py), so the
same engine drives both the interactive dashboard and the batch runner.

Order of operations each step (identical to MATLAB):
    1. poacher movement
    2. elephant movement (+ ROAMING/SEEKING/WAITING state machine)
    3. microphone scans, hysteresis/memory and alert -> ranger dispatch
    3.5 ranger interception
    4. poaching check (one 85 % roll per encounter; failed roll -> elephant flees)
"""
from __future__ import annotations

import numpy as np

from .config import ROAMING, SEEKING, WAITING, SimConfig
from .environment import Environment
from .mic_placement import place_mics

_EPS = 1e-12


def _safe(d):
    """Guard divisions by an exactly-zero distance (MATLAB would produce NaN)."""
    return np.where(d == 0, _EPS, d)


class Simulation:
    def __init__(self, cfg: SimConfig, seed=None, env: Environment | None = None,
                 mic_layout: np.ndarray | None = None, pools=None):
        """
        cfg        : SimConfig (use SimConfig.live() or SimConfig.batch())
        seed       : int for reproducible runs, None = random (MATLAB rng('shuffle'))
        env        : optional pre-built Environment (reuse across batch trials)
        mic_layout : optional pre-computed (N,2) mic positions
        pools      : optional (general, elephant, deep) target pools
        """
        self.cfg = cfg
        self.rng = np.random.default_rng(seed)
        self.picker = None
        self.env = env if env is not None else Environment(cfg)
        z = self.env.zones
        c = cfg

        # pixel-scaled constants
        self.px_reached = c.m2px(c.dist_reached_m)
        self.px_avoid = c.m2px(c.avoid_buffer_m)
        self.px_green_repel = z.att_r + c.m2px(c.poacher_green_repel_m)
        self.px_poach = c.m2px(c.poach_dist_m)
        self.px_catch = c.m2px(c.ranger_catch_m)
        self.range_e = c.m2px(c.mic_range_e_m)
        self.range_p = c.m2px(c.mic_range_p_m)

        # MATLAB order: agents (4), pools (4.5), mics (5)
        self._init_elephants_and_poachers_part1()
        if pools is None:
            pools = self.env.build_pools(self.rng)
        self.pool_general, self.pool_elephant, self.pool_deep = pools
        self._init_targets_from_pool_if_needed()

        if mic_layout is None:
            mic_layout = place_mics(self.env, c.mic_strategy, c.num_mics)
        self._init_mics(mic_layout)

        self.t = 0.0
        self.time_first_poach = None     # sim seconds
        self.time_first_neutral = None

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def _init_elephants_and_poachers_part1(self):
        c, env, rng = self.cfg, self.env, self.rng
        z = env.zones
        nE, nP = c.num_elephants, c.num_poachers

        # --- elephants: start outside red zones, inside the park
        start = env.sample_valid(rng, env.valid_elephant, nE)
        self.ex, self.ey = start[:, 0].copy(), start[:, 1].copy()
        self.evx = np.zeros(nE)
        self.evy = np.zeros(nE)
        self.e_poached = np.zeros(nE, bool)
        self.e_poach_time = np.full(nE, -999.0)
        self.e_threatened = np.zeros(nE, bool)
        self.e_rolled = np.zeros(nE, bool)
        self.e_state = np.full(nE, ROAMING, dtype=int)
        self.e_entry_time = np.zeros(nE)
        self.e_last_visit = np.full(nE, -999.0)
        if not c.initial_targets_from_pool:
            tgt = env.sample_valid(rng, env.valid_elephant, nE)
            self.etx, self.ety = tgt[:, 0].copy(), tgt[:, 1].copy()

        # --- poachers: 50 % near a village, 50 % just outside the boundary
        px = np.zeros(nP)
        py = np.zeros(nP)
        m6000 = c.m2px(c.poacher_spawn_village_m)
        m5000 = c.m2px(c.poacher_spawn_border_m)
        green_clear = z.att_r + c.m2px(c.avoid_buffer_m)
        for p in range(nP):
            while True:
                if rng.random() > 0.5:
                    sn = rng.integers(len(z.rep_x))
                    sx = z.rep_x[sn] + (rng.random() - 0.5) * m6000
                    sy = z.rep_y[sn] + (rng.random() - 0.5) * m6000
                    if bool(env.inside_setup(sx, sy)) and \
                            np.hypot(sx - z.att_x, sy - z.att_y) > green_clear:
                        break
                else:
                    ii = rng.integers(len(env.boundary_x))
                    sx = env.boundary_x[ii] + (rng.random() - 0.5) * m5000
                    sy = env.boundary_y[ii] + (rng.random() - 0.5) * m5000
                    if not bool(env.inside_setup(sx, sy)):
                        break
            px[p], py[p] = sx, sy
        self.px, self.py = px, py
        self.pvx = np.zeros(nP)
        self.pvy = np.zeros(nP)
        if not c.initial_targets_from_pool:
            tgt = env.sample_valid(rng, env.valid_general, nP)
            self.ptx, self.pty = tgt[:, 0].copy(), tgt[:, 1].copy()
        self.p_caught = np.zeros(nP, bool)
        self.p_caught_time = np.full(nP, -999.0)
        self.p_targeted = np.zeros(nP, bool)
        self.rx = np.full(nP, -999.0)
        self.ry = np.full(nP, -999.0)
        self.base_x = np.full(nP, -999.0)
        self.base_y = np.full(nP, -999.0)

    def _init_targets_from_pool_if_needed(self):
        if not self.cfg.initial_targets_from_pool:
            return
        nE, nP = self.cfg.num_elephants, self.cfg.num_poachers
        i = self.rng.integers(len(self.pool_elephant), size=nE)
        self.etx, self.ety = self.pool_elephant[i, 0].copy(), self.pool_elephant[i, 1].copy()
        j = self.rng.integers(len(self.pool_general), size=nP)
        self.ptx, self.pty = self.pool_general[j, 0].copy(), self.pool_general[j, 1].copy()

    def _init_mics(self, layout):
        layout = np.asarray(layout, dtype=float).reshape(-1, 2)
        n = len(layout)
        self.num_mics = n
        self.mx = layout[:, 0].copy()
        self.my = layout[:, 1].copy()
        self.m_active_e = np.zeros(n, bool)
        self.m_active_p = np.zeros(n, bool)
        self.m_threat = np.zeros(n, bool)
        self.m_missed = np.zeros(n, bool)
        self.m_has_memory = np.zeros(n, bool)
        self.m_elephant_memory = np.full(n, -999999.0)
        self.m_last_scan = np.zeros(n)

    # ------------------------------------------------------------------
    # Random target picks.  `kind` / `agent_ids` are only used by an optional
    # deterministic `picker` hook (validation/lockstep_compare.py), which lets
    # the Python engine be run in lock-step with the original MATLAB code.
    PICK_POACHER_REACHED, PICK_POACHER_BOUNCE, PICK_ELEPHANT_DEEP = 1, 2, 3
    PICK_ELEPHANT_AVOID, PICK_ELEPHANT_BOUNCE, PICK_POACHER_AFTER_ESCAPE = 4, 5, 6

    def _pick(self, pool, agent_ids, kind):
        agent_ids = np.atleast_1d(agent_ids)
        if self.picker is not None:
            idx = np.asarray(self.picker(kind, agent_ids, self.t, len(pool)), dtype=int)
        else:
            idx = self.rng.integers(len(pool), size=agent_ids.size)
        return pool[idx, 0], pool[idx, 1]

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------
    def step(self, sim_dt: float):
        """Advance the world by sim_dt simulated seconds."""
        c = self.cfg
        self.t += sim_dt
        step_e = c.speed_elephant_mps * sim_dt / c.meters_per_pixel
        step_p = c.speed_poacher_mps * sim_dt / c.meters_per_pixel
        step_r = c.speed_ranger_mps * sim_dt / c.meters_per_pixel
        self._move_poachers(step_p)
        self._move_elephants(step_e)
        self._scan_mics()
        self._move_rangers(step_r)
        self._poaching_check()

    # --- 1. POACHER MOVEMENT ------------------------------------------
    def _move_poachers(self, step_p):
        env, z, c = self.env, self.env.zones, self.cfg
        ids = np.flatnonzero(~self.p_caught)
        if ids.size == 0:
            return
        x, y = self.px[ids], self.py[ids]
        tx, ty = self.ptx[ids], self.pty[ids]
        dist = np.hypot(tx - x, ty - y)

        reached = dist < self.px_reached
        if reached.any():
            nx_, ny_ = self._pick(self.pool_general, ids[reached], self.PICK_POACHER_REACHED)
            tx[reached], ty[reached] = nx_, ny_
            dist[reached] = np.hypot(tx[reached] - x[reached], ty[reached] - y[reached])

        dist = _safe(dist)
        dvx = (tx - x) / dist
        dvy = (ty - y) / dist

        d_green = _safe(np.hypot(x - z.att_x, y - z.att_y))
        near = d_green < self.px_green_repel
        dvx = np.where(near, dvx + (x - z.att_x) / d_green * c.repulsion_gain, dvx)
        dvy = np.where(near, dvy + (y - z.att_y) / d_green * c.repulsion_gain, dvy)

        vx, vy = self._blend(self.pvx[ids], self.pvy[ids], dvx, dvy)

        was_in = env.inside_grid(x, y)
        nx = x + vx * step_p
        ny = y + vy * step_p
        now_in = env.inside_grid(nx, ny)
        bounce = was_in & ~now_in
        if bounce.any():
            vx[bounce] = -vx[bounce]
            vy[bounce] = -vy[bounce]
            bx_, by_ = self._pick(self.pool_general, ids[bounce], self.PICK_POACHER_BOUNCE)
            tx[bounce], ty[bounce] = bx_, by_
        move = ~bounce
        x = np.where(move, nx, x)
        y = np.where(move, ny, y)

        self.px[ids], self.py[ids] = x, y
        self.pvx[ids], self.pvy[ids] = vx, vy
        self.ptx[ids], self.pty[ids] = tx, ty

    def _blend(self, vx, vy, dvx, dvy):
        """Normalise desired direction, blend 95/5 with the current heading and
        re-normalise (the 'velocity-blending' wide-turn model)."""
        a = self.cfg.velocity_blend
        mag = np.hypot(dvx, dvy)
        pos = mag > 0
        dvx = np.where(pos, dvx / np.where(pos, mag, 1), dvx)
        dvy = np.where(pos, dvy / np.where(pos, mag, 1), dvy)
        vx = vx * (1 - a) + dvx * a
        vy = vy * (1 - a) + dvy * a
        mag = np.hypot(vx, vy)
        pos = mag > 0
        vx = np.where(pos, vx / np.where(pos, mag, 1), vx)
        vy = np.where(pos, vy / np.where(pos, mag, 1), vy)
        return vx, vy

    # --- 2. ELEPHANT MOVEMENT -----------------------------------------
    def _move_elephants(self, step_e):
        env, z, c, t = self.env, self.env.zones, self.cfg, self.t
        ids = np.flatnonzero(~self.e_poached)
        if ids.size == 0:
            return
        x, y = self.ex[ids], self.ey[ids]
        tx, ty = self.etx[ids], self.ety[ids]
        state = self.e_state[ids].copy()
        entry = self.e_entry_time[ids]
        last_visit = self.e_last_visit[ids]

        dist = np.hypot(tx - x, ty - y)          # NB: computed before the state machine
        d_bai = _safe(np.hypot(x - z.att_x, y - z.att_y))

        # state machine (if / elseif / elseif  ->  one transition per step)
        roam, seek, wait = state == ROAMING, state == SEEKING, state == WAITING
        to_seek = roam & ((t - last_visit) > c.revisit_cooldown_s) & (d_bai < z.att_sense)
        to_wait = seek & (d_bai < z.att_r)
        to_roam = wait & ((t - entry) > c.bai_wait_s)
        state[to_seek] = SEEKING
        state[to_wait] = WAITING
        entry = np.where(to_wait, t, entry)
        state[to_roam] = ROAMING
        last_visit = np.where(to_roam, t, last_visit)
        if to_roam.any():
            dx_, dy_ = self._pick(self.pool_deep, ids[to_roam], self.PICK_ELEPHANT_DEEP)
            tx[to_roam], ty[to_roam] = dx_, dy_
            # MATLAB does not recompute `dist` here - kept identical.

        retarget = (dist < self.px_avoid) & (state != WAITING)
        if retarget.any():
            rx_, ry_ = self._pick(self.pool_elephant, ids[retarget], self.PICK_ELEPHANT_AVOID)
            tx[retarget], ty[retarget] = rx_, ry_
            dist[retarget] = np.hypot(tx[retarget] - x[retarget], ty[retarget] - y[retarget])

        waiting = state == WAITING
        dist = _safe(dist)
        dvx = np.where(waiting, 0.0, (tx - x) / dist)
        dvy = np.where(waiting, 0.0, (ty - y) / dist)

        seeking = state == SEEKING
        dvx = np.where(seeking, dvx + (z.att_x - x) / d_bai * c.bai_attraction_gain, dvx)
        dvy = np.where(seeking, dvy + (z.att_y - y) / d_bai * c.bai_attraction_gain, dvy)

        for rxv, ryv, rrv in zip(z.rep_x, z.rep_y, z.rep_r):
            d_rep = _safe(np.hypot(x - rxv, y - ryv))
            near = d_rep < rrv + self.px_avoid
            dvx = np.where(near, dvx + (x - rxv) / d_rep * c.repulsion_gain, dvx)
            dvy = np.where(near, dvy + (y - ryv) / d_rep * c.repulsion_gain, dvy)

        vx, vy = self._blend(self.evx[ids], self.evy[ids], dvx, dvy)

        nx = x + vx * step_e
        ny = y + vy * step_e
        ok = env.inside_grid(nx, ny)
        x = np.where(ok, nx, x)
        y = np.where(ok, ny, y)
        bad = ~ok
        if bad.any():
            vx[bad] = -vx[bad]
            vy[bad] = -vy[bad]
            bx_, by_ = self._pick(self.pool_elephant, ids[bad], self.PICK_ELEPHANT_BOUNCE)
            tx[bad], ty[bad] = bx_, by_

        self.ex[ids], self.ey[ids] = x, y
        self.evx[ids], self.evy[ids] = vx, vy
        self.etx[ids], self.ety[ids] = tx, ty
        self.e_state[ids] = state
        self.e_entry_time[ids] = entry
        self.e_last_visit[ids] = last_visit

    # --- 3. SENSOR NETWORK & HYSTERESIS LOGIC -------------------------
    def _scan_mics(self):
        c, t = self.cfg, self.t
        if self.num_mics == 0:
            return
        S = np.flatnonzero((t - self.m_last_scan) >= c.scan_interval_sim)
        if S.size == 0:
            return
        self.m_last_scan[S] = t
        mx, my = self.mx[S, None], self.my[S, None]
        pdet = c.detection_probability

        # elephants (only living ones)
        eids = np.flatnonzero(~self.e_poached)
        inE = np.hypot(self.ex[eids][None, :] - mx, self.ey[eids][None, :] - my) < self.range_e
        detE = np.zeros_like(inE)
        detE[inE] = self.rng.random(int(inE.sum())) <= pdet
        act_e = detE.any(axis=1)
        e_in = inE.any(axis=1)

        # poachers (only active ones)
        pids = np.flatnonzero(~self.p_caught)
        inP = np.hypot(self.px[pids][None, :] - mx, self.py[pids][None, :] - my) < self.range_p
        detP = np.zeros_like(inP)
        detP[inP] = self.rng.random(int(inP.sum())) <= pdet
        act_p = detP.any(axis=1)
        p_in = inP.any(axis=1)

        self.m_active_e[S] = act_e
        self.m_active_p[S] = act_p
        self.m_elephant_memory[S[act_e]] = t
        self.m_missed[S] = (e_in & ~act_e) | (p_in & ~act_p)
        has_mem = (t - self.m_elephant_memory[S]) <= c.mic_memory_s
        self.m_has_memory[S] = has_mem

        # ALERT: poacher heard now AND an elephant heard now or within 4 h
        alert = act_p & (act_e | has_mem)
        threat = np.zeros(S.size, bool)
        if alert.any():
            cand = ~self.p_targeted[pids]           # (already filtered to not caught)
            hit = inP[alert] & cand[None, :]         # every untargeted poacher in range
            threat[alert] = hit.any(axis=1)
            newly = pids[hit.any(axis=0)]
            if newly.size:
                self._dispatch_rangers(newly)
        self.m_threat[S] = threat

    def _dispatch_rangers(self, newly):
        z = self.env.zones
        self.p_targeted[newly] = True
        d = np.hypot(self.px[newly, None] - z.rep_x[None, :],
                     self.py[newly, None] - z.rep_y[None, :])
        base = np.argmin(d, axis=1)                  # nearest village (first on ties)
        self.base_x[newly] = z.rep_x[base]
        self.base_y[newly] = z.rep_y[base]
        self.rx[newly] = self.base_x[newly]
        self.ry[newly] = self.base_y[newly]

    # --- 3.5 RANGER INTERCEPTION -------------------------------------
    def _move_rangers(self, step_r):
        ids = np.flatnonzero(self.p_targeted & ~self.p_caught)
        if ids.size == 0:
            return
        dx = self.px[ids] - self.rx[ids]
        dy = self.py[ids] - self.ry[ids]
        dist = np.hypot(dx, dy)
        caught = dist < self.px_catch
        if caught.any():
            cid = ids[caught]
            self.p_caught[cid] = True
            self.p_caught_time[cid] = self.t
            if self.time_first_neutral is None:
                self.time_first_neutral = self.t
        mv = ~caught
        if mv.any():
            mid = ids[mv]
            self.rx[mid] += dx[mv] / dist[mv] * step_r
            self.ry[mid] += dy[mv] / dist[mv] * step_r

    # --- 4. POACHING CHECK --------------------------------------------
    def _poaching_check(self):
        c, z, t = self.cfg, self.env.zones, self.t
        alive_e = np.flatnonzero(~self.e_poached)
        if alive_e.size == 0:
            return
        self.e_threatened[alive_e] = False
        pids = np.flatnonzero(~self.p_caught)
        if pids.size == 0:
            self.e_rolled[alive_e] = False
            return
        d = np.hypot(self.ex[alive_e, None] - self.px[None, pids],
                     self.ey[alive_e, None] - self.py[None, pids])
        in_rng = d < self.px_poach
        any_in = in_rng.any(axis=1)
        self.e_rolled[alive_e[~any_in]] = False     # left range -> new roll allowed

        flee_dist = self.px_avoid * c.flee_factor
        for row in np.flatnonzero(any_in):
            k = alive_e[row]
            d_safe = np.hypot(self.ex[k] - z.att_x, self.ey[k] - z.att_y)
            for col in np.flatnonzero(in_rng[row]):
                p = pids[col]
                if d_safe > z.att_r:                  # the Bai is a safe haven
                    self.e_threatened[k] = True
                    if not self.e_rolled[k]:
                        self.e_rolled[k] = True
                        if self.rng.random() <= c.poach_probability:
                            self.e_poached[k] = True
                            self.e_poach_time[k] = t
                            if self.time_first_poach is None:
                                self.time_first_poach = t
                        else:
                            fdx = self.ex[k] - self.px[p]
                            fdy = self.ey[k] - self.py[p]
                            fm = np.hypot(fdx, fdy) or _EPS
                            self.etx[k] = self.ex[k] + fdx / fm * flee_dist
                            self.ety[k] = self.ey[k] + fdy / fm * flee_dist
                            gx, gy = self._pick(self.pool_general, p, self.PICK_POACHER_AFTER_ESCAPE)
                            self.ptx[p], self.pty[p] = gx[0], gy[0]

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------
    @property
    def poached_count(self) -> int:
        return int(self.e_poached.sum())

    @property
    def caught_count(self) -> int:
        return int(self.p_caught.sum())

    def finished(self) -> bool:
        """Batch stop condition: all elephants poached or all poachers caught."""
        return (self.poached_count == self.cfg.num_elephants or
                self.caught_count == self.cfg.num_poachers)

    def show_poached_alert(self, window: float = 3.0) -> bool:
        return bool(np.any(self.e_poached & ((self.t - self.e_poach_time) < window)))

    def show_caught_alert(self, window: float = 3.0) -> bool:
        return bool(np.any(self.p_caught & ((self.t - self.p_caught_time) < window)))
