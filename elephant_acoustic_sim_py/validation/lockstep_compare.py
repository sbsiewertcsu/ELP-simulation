"""
LOCK-STEP TRACE COMPARISON against the ORIGINAL MATLAB code.

Randomness is the only reason a Python run can't be compared 1:1 with a MATLAB
run.  This script removes it:
  * the random target picks (randi(count)) in BOTH codes are replaced by the
    same deterministic function  idx = f(step, agent, kind)
  * detection / poaching probabilities are set to 0 or 1 so rand() no longer
    changes the outcome
  * Python starts from exactly the pools, mic layout and initial agent state
    that the MATLAB code generated
Every simulation step, all positions / targets / flags / states / mic counts
from both are compared.

Usage (needs GNU Octave):
    python validation/lockstep_compare.py            # runs the 3 scenarios
"""
import os
import pathlib
import re
import subprocess
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from elephant_sim import Environment, SimConfig, Simulation  # noqa: E402

WORK = HERE / "lockstep_out"
NE, NP = 20, 10

PICK_FN = r"""
function idx = pick(count, kind, id, t)
  idx = mod(floor(round(t)/250)*101 + id*1009 + kind*7919, count) + 1;
end
"""


def py_picker(kind, ids, t, count):
    return (np.floor(round(t) / 250) * 101 + (ids + 1) * 1009 + kind * 7919).astype(np.int64) % count


def build_octave_script():
    sys.path.insert(0, str(HERE))
    from make_octave_scripts import body, funcs, octavize, set_cfg  # noqa
    b = octavize(body)
    b = set_cfg(b, NUM_RUNS="1", MIC_STRATEGY="str2num(getenv('STRAT'))",
                NUM_MICS="str2num(getenv('NMICS'))", MAX_SIM_DAYS="str2num(getenv('DAYS'))",
                SIM_DT="250.0", DETECTION_PROBABILITY="str2num(getenv('PDET'))",
                POACH_PROBABILITY="str2num(getenv('PPOACH'))")
    head, loop = b.split("% SIMULATION LOOP (no graphics)")
    # deterministic picks, in source order inside the loop
    plan = [("count_g", 1, "p"), ("count_g", 2, "p"), ("count_d", 3, "k"),
            ("count_e", 4, "k"), ("count_e", 5, "k"), ("count_g", 6, "p")]
    for cnt, kind, who in plan:
        old = f"idx=randi({cnt});"
        assert old in loop, old
        loop = loop.replace(old, f"idx=pick({cnt},{kind},{who},current_sim_time);", 1)
    assert "randi(" not in loop
    # dump pools / mics / initial state, then one trace row per step
    head = head.replace("% --- Trial state ---", r"""
    od = getenv('OUTDIR');
    dlmwrite(fullfile(od,'pool_general.csv'), pool_general, 'precision','%.17g');
    dlmwrite(fullfile(od,'pool_elephant.csv'), pool_elephant, 'precision','%.17g');
    dlmwrite(fullfile(od,'pool_deep.csv'), pool_deep, 'precision','%.17g');
    dlmwrite(fullfile(od,'mics.csv'), [[mics.x]' [mics.y]'], 'precision','%.17g');
    dlmwrite(fullfile(od,'init.csv'), [[players.x] [players.y] [players.target_x] [players.target_y] [poachers.x] [poachers.y] [poachers.target_x] [poachers.target_y]], 'precision','%.17g');
    fid = fopen(fullfile(od,'trace.csv'), 'w');
    % --- Trial state ---""")
    loop = loop.replace("        % --- STOP CONDITIONS ---", r"""
        st = zeros(1,num_elephants);
        for k=1:num_elephants
            st(k) = find(strcmp(players(k).state, {"ROAMING","SEEKING","WAITING"})) - 1;
        end
        row = [current_sim_time, [players.x], [players.y], [players.target_x], [players.target_y], ...
               [poachers.x], [poachers.y], [poachers.target_x], [poachers.target_y], ...
               [poachers.ranger_x], [poachers.ranger_y], ...
               [players.is_poached], [players.encounter_rolled], st, ...
               [poachers.is_caught], [poachers.is_targeted], ...
               sum([mics.active_e]), sum([mics.active_p]), sum([mics.has_memory]), sum([mics.missed]), sum([mics.threat])];
        fprintf(fid, '%.17g,', row); fprintf(fid, '\n');
        % --- STOP CONDITIONS ---""")
    loop = loop.replace("end % simulation loop", "end % simulation loop\n    fclose(fid);")
    text = "1;\n" + PICK_FN + funcs + "\n" + head + "% SIMULATION LOOP (no graphics)" + loop
    path = HERE / "oct_lockstep.m"
    path.write_text(text)
    return path


def python_row(s: Simulation):
    return np.concatenate([
        [s.t], s.ex, s.ey, s.etx, s.ety, s.px, s.py, s.ptx, s.pty, s.rx, s.ry,
        s.e_poached, s.e_rolled, s.e_state, s.p_caught, s.p_targeted,
        [s.m_active_e.sum(), s.m_active_p.sum(), s.m_has_memory.sum(), s.m_missed.sum(), s.m_threat.sum()]])


COLS = (["t"] + [f"{n}{i}" for n in ("ex", "ey", "etx", "ety") for i in range(NE)]
        + [f"{n}{i}" for n in ("px", "py", "ptx", "pty", "rx", "ry") for i in range(NP)]
        + [f"{n}{i}" for n in ("poached", "rolled", "state") for i in range(NE)]
        + [f"{n}{i}" for n in ("caught", "targeted") for i in range(NP)]
        + ["mics_active_e", "mics_active_p", "mics_memory", "mics_missed", "mics_threat"])
N_CONT = 1 + 4 * NE + 6 * NP          # continuous columns; the rest are discrete


def run_scenario(name, strat, nmics, days, pdet, ppoach, script):
    od = WORK / name
    od.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OUTDIR=str(od), STRAT=str(strat), NMICS=str(nmics), DAYS=str(days),
               PDET=str(pdet), PPOACH=str(ppoach))
    if not (od / "trace.csv").exists():
        subprocess.run(["octave", "--no-gui", "--quiet", str(script)], env=env, check=True,
                       stdout=subprocess.DEVNULL)
    load = lambda f: np.loadtxt(od / f, delimiter=",", ndmin=2)
    oct_trace = np.genfromtxt(od / "trace.csv", delimiter=",")[:, :-1]   # trailing comma
    oct_trace = oct_trace.reshape(-1, len(COLS))
    init = load("init.csv").ravel()

    cfg = SimConfig.batch(mic_strategy=strat, num_mics=nmics, detection_probability=pdet,
                          poach_probability=ppoach)
    envr = Environment(cfg)
    sim = Simulation(cfg, seed=0, env=envr, mic_layout=load("mics.csv"),
                     pools=(load("pool_general.csv"), load("pool_elephant.csv"), load("pool_deep.csv")))
    o = 0
    for arr in ("ex", "ey", "etx", "ety"):
        getattr(sim, arr)[:] = init[o:o + NE]; o += NE
    for arr in ("px", "py", "ptx", "pty"):
        getattr(sim, arr)[:] = init[o:o + NP]; o += NP
    sim.picker = py_picker

    max_err, first_discrete, first_big = 0.0, None, None
    for i, orow in enumerate(oct_trace):
        sim.step(250.0)
        prow = python_row(sim).astype(float)
        err = np.abs(prow[:N_CONT] - orow[:N_CONT])
        # ranger coords are -999 until dispatched in both codes; compare all
        max_err = max(max_err, float(err.max()))
        if first_big is None and err.max() > 1e-6:
            first_big = (i + 1, COLS[int(err.argmax())], float(err.max()))
        bad = np.flatnonzero(prow[N_CONT:] != orow[N_CONT:])
        if first_discrete is None and bad.size:
            first_discrete = (i + 1, [COLS[N_CONT + j] for j in bad[:6]])
    return dict(name=name, steps=len(oct_trace), sim_days=oct_trace[-1, 0] / 86400,
                max_pos_err_px=max_err, first_discrete_mismatch=first_discrete,
                first_err_gt_1e6=first_big,
                octave_final=(int(oct_trace[-1, N_CONT:N_CONT + NE].sum()),
                              int(oct_trace[-1, N_CONT + 3 * NE:N_CONT + 3 * NE + NP].sum())),
                python_final=(sim.poached_count, sim.caught_count),
                events=dict(poached=int(oct_trace[-1, N_CONT:N_CONT + NE].sum()),
                            caught=int(oct_trace[-1, N_CONT + 3 * NE:N_CONT + 3 * NE + NP].sum()),
                            waiting_steps=int((oct_trace[:, N_CONT + 2 * NE:N_CONT + 3 * NE] == 2).sum()),
                            seeking_steps=int((oct_trace[:, N_CONT + 2 * NE:N_CONT + 3 * NE] == 1).sum()),
                            escapes=int(np.sum(np.diff(oct_trace[:, N_CONT + NE:N_CONT + 2 * NE], axis=0) > 0)
                                        - oct_trace[-1, N_CONT:N_CONT + NE].sum()) if ppoach == 0 else 0))


SCENARIOS = [
    # name,                       strat, mics, days, P(detect), P(poach)
    ("A_uniform_detect1_poach1", 1, 40, 3, 1.0, 1.0),
    ("B_perimeter_detect1_poach0", 3, 40, 3, 1.0, 0.0),
    ("C_fortress_nodetect_poach0", 2, 80, 3, 0.0, 0.0),
    ("D_5050_600mics_detect1_poach1", 4, 600, 2, 1.0, 1.0),
]

if __name__ == "__main__":
    script = build_octave_script()
    only = sys.argv[1:]
    lines = ["# Lock-step trace comparison vs original MATLAB code", "",
             "Same pools, mic layout and initial state; random picks replaced by the same "
             "deterministic function in both codes; probabilities set to 0/1. Every step compares "
             f"{N_CONT} continuous values (positions, targets, rangers) and "
             f"{len(COLS) - N_CONT} discrete values (poached, encounter, state, caught, targeted, mic flag counts).", "",
             "| Scenario | Steps | Max position error (px) | Discrete mismatches | Final poached/caught (MATLAB vs Python) | Events exercised |",
             "|---|---|---|---|---|---|"]
    for sc in SCENARIOS:
        if only and sc[0] not in only:
            continue
        r = run_scenario(*sc, script)
        print(r, flush=True)
        ev = r["events"]
        lines.append(f"| {r['name']} | {r['steps']} ({r['sim_days']:.2f} d) | {r['max_pos_err_px']:.1e} | "
                     f"{'none' if r['first_discrete_mismatch'] is None else r['first_discrete_mismatch']} | "
                     f"{r['octave_final']} vs {r['python_final']} | "
                     f"poached {ev['poached']}, caught {ev['caught']}, escapes {ev['escapes']}, "
                     f"SEEKING steps {ev['seeking_steps']}, "
                     f"WAITING steps {ev['waiting_steps']} |")
    (HERE / "LOCKSTEP_RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
