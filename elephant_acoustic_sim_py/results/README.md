# Sweep results

Settings: `SimConfig.batch()` (ver_6 settings), 20 elephants, 10 poachers, 30 sim-days max, 50 trials per
(strategy, mic count), mics 10-160 step 5, strategies 1-5 plus a no-mics control, seed 0.
Score = elephants poached when all poachers are neutralized (or at 30 days);
`all_neutralized` flags trials where the poachers were never all caught.

* `dt50/` - **main result.** Full sweep at dt = 50 s (`python run_sweep.py --runs 50 --dt 50`).
  No mics: 17.2 of 20 elephants poached. Best layouts reach about 2-3 poached at 150-160 mics and catch all
  poachers in nearly every trial from about 75-100 mics. Random mesh, uniform spread and targeted fortress are
  within noise of each other at high mic counts; 50/50 split is worse; perimeter-only barely helps
  (likely because the alert rule needs a nearby elephant memory).
* `dt_study/` - same seeds at dt = 250 / 50 / 10 s on mics {20, 60, 100} x {uniform, fortress, random mesh}
  (+ no-mics control). 50 s and 10 s agree within noise (15 trials, CI about +/-2 elephants); 250 s does not.
  Reproduce the table with `python compare_dt.py`. 50 s has not been checked against 1 s.
* `preliminary_dt250/` - **superseded.** Same sweep at dt = 250 s. Kept for reference only: the dt study shows
  250 s underestimates poaching by about 2-6 elephants.

Best-N values sit at the top of the range because the curves are still falling and noisy; they are not optimal
mic counts. Absolute numbers depend on the model's assumptions (random-walking poachers, perfect ranger
tracking, flat detection radius).
