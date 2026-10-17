# Sweep results

Settings: `SimConfig.batch()` (ver_6 settings), 20 elephants, 10 poachers, 30 sim-days max.
Score = elephants poached when all poachers are neutralized (or at 30 days);
`all_neutralized` flags trials where the poachers were never all caught.

* `preliminary_dt250/` - full sweep (mics 10-160 step 5, strategies 1-5, 50 trials, no-mics control)
  at dt = 250 s. **Preliminary:** the dt study shows 250 s underestimates poaching by ~2-6 elephants.
* `dt_study/` - same seeds at dt = 250 / 50 / 10 s on mics {20, 60, 100} x strategies {uniform, fortress,
  random mesh} (+ no-mics control). 50 s and 10 s agree within noise (15 trials, CI about +/-2 elephants);
  250 s does not. Reproduce the table with `python compare_dt.py`.
