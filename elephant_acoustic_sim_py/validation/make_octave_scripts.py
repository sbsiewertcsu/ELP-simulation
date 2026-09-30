"""Builds Octave-runnable copies of the ORIGINAL MATLAB scripts (minimal,
non-behavioural patches only) so the Python port can be cross-checked.

Patches applied:
  * local functions moved to the top of the file (Octave needs them defined
    before use; `1;` marks the file as a script)
  * string state comparisons -> strcmp (Octave treats "..." as char arrays)
  * clc / drawnow removed, config values injected, results dumped to CSV
"""
import re, sys, pathlib

HERE = pathlib.Path(__file__).parent
src = (HERE / "large_scale_sim_FINAL_ver_6_DEBUG_ONLY.m").read_text()

split = src.index("% STRATEGY 1: UNIFORM GLOBAL SPREAD")
body, funcs = src[:split], src[split:]

def octavize(body):
    body = body.replace("clear; clc;", "")
    body = re.sub(r'players\(k\)\.state\s*==\s*"(\w+)"', r'strcmp(players(k).state,"\1")', body)
    body = re.sub(r'players\(k\)\.state\s*~=\s*"(\w+)"', r'~strcmp(players(k).state,"\1")', body)
    body = body.replace("drawnow;", "")
    body = body.replace('strat_names = ["Uniform Spread","Targeted Fortress","Perimeter Defense","50/50 Split"];',
                        'strat_names = {"Uniform Spread","Targeted Fortress","Perimeter Defense","50/50 Split"};')
    body = body.replace("strat_names(MIC_STRATEGY)", "strat_names{MIC_STRATEGY}")
    return body

def set_cfg(body, **kw):
    for k, v in kw.items():
        body, n = re.subn(rf"^{k}\s*=\s*[^;]+;", f"{k} = {v};", body, count=1, flags=re.M)
        assert n == 1, k
    return body

# ---- 1. placement dump (deterministic) -----------------------------------
pl = octavize(body)
cut = pl.index("% PRINT TRIAL HEADER")
pl = pl[:pl.rfind("% ====", 0, cut)]
pl = pl.replace("fprintf('Pre-computing position pools...\\n');", "")
dump = r"""
outdir = getenv('OUTDIR');
dlmwrite(fullfile(outdir, 'park_grid.csv'), double(park_grid), 'precision', '%d');
for S = 1:4
  for N = [40 80 600]
    if S == 1, [L, n] = place_mics_uniform(WIDTH, HEIGHT, isInsidePark, mic_specs, N);
    elseif S == 2, [L, n] = place_mics_fortress(WIDTH, HEIGHT, isInsidePark, mic_specs, repulsors, N);
    elseif S == 3, [L, n] = place_mics_perimeter(WIDTH, HEIGHT, park_boundary_x, park_boundary_y, mic_specs, N);
    else, [L, n] = place_mics_optimized_web(WIDTH, HEIGHT, isInsidePark, mic_specs, repulsors, attractor, m2px, park_boundary_x, park_boundary_y, N);
    end
    dlmwrite(fullfile(outdir, sprintf('mics_grid_s%d_n%d.csv', S, N)), [[L.x]' [L.y]'], 'precision', '%.12f');
    % ver_5 places mics with the exact polygon test
    if S == 1, [L, n] = place_mics_uniform(WIDTH, HEIGHT, isInsidePark_poly, mic_specs, N);
    elseif S == 2, [L, n] = place_mics_fortress(WIDTH, HEIGHT, isInsidePark_poly, mic_specs, repulsors, N);
    elseif S == 3, [L, n] = place_mics_perimeter(WIDTH, HEIGHT, park_boundary_x, park_boundary_y, mic_specs, N);
    else, [L, n] = place_mics_optimized_web(WIDTH, HEIGHT, isInsidePark_poly, mic_specs, repulsors, attractor, m2px, park_boundary_x, park_boundary_y, N);
    end
    dlmwrite(fullfile(outdir, sprintf('mics_poly_s%d_n%d.csv', S, N)), [[L.x]' [L.y]'], 'precision', '%.12f');
  end
end
disp('placement dump done');
"""
# placement section references MIC_STRATEGY; keep it (places once), then dump all
(HERE / "oct_placement.m").write_text("1;\n" + funcs + "\n" + pl + dump)

# ---- 2. batch runs (statistical) ------------------------------------------
dump_results = r"""
outdir = getenv('OUTDIR');
fn = fullfile(outdir, sprintf('octave_batch_s%d_n%d.csv', MIC_STRATEGY, NUM_MICS));
dlmwrite(fn, [results.poached' results.neutralized' results.time_1st_poach' results.time_1st_neutral' results.total_time'], 'precision', '%.6f');
"""
for S in (1, 2, 3, 4):
    b = octavize(body)
    b = set_cfg(b, NUM_RUNS="str2num(getenv('RUNS'))", MIC_STRATEGY=str(S),
                NUM_MICS="str2num(getenv('NMICS'))",
                MAX_SIM_DAYS="str2num(getenv('DAYS'))", SIM_DT="250.0")
    b = "rand('twister', sum(100*clock) + %d);\n" % S + b
    (HERE / f"oct_batch_s{S}.m").write_text("1;\n" + funcs + "\n" + b + dump_results)
print("ok")
