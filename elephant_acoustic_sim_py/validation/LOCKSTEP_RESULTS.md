# Lock-step trace comparison vs original MATLAB code

Same pools, mic layout and initial state; random picks replaced by the same deterministic function in both codes; probabilities set to 0/1. Every step compares 141 continuous values (positions, targets, rangers) and 85 discrete values (poached, encounter, state, caught, targeted, mic flag counts).

| Scenario | Steps | Max position error (px) | Discrete mismatches | Final poached/caught (MATLAB vs Python) | Events exercised |
|---|---|---|---|---|---|
| A_uniform_detect1_poach1 | 1037 (3.00 d) | 8.8e-11 | none | (2, 0) vs (2, 0) | poached 2, caught 0, escapes 0, SEEKING steps 6866, WAITING steps 2 |
| B_perimeter_detect1_poach0 | 1037 (3.00 d) | 4.9e-08 | none | (0, 0) vs (0, 0) | poached 0, caught 0, escapes 5, SEEKING steps 8043, WAITING steps 0 |
| C_fortress_nodetect_poach0 | 1037 (3.00 d) | 3.6e-10 | none | (0, 0) vs (0, 0) | poached 0, caught 0, escapes 5, SEEKING steps 7819, WAITING steps 2 |
| D_5050_600mics_detect1_poach1 | 692 (2.00 d) | 7.2e-12 | none | (0, 7) vs (0, 7) | poached 0, caught 7, escapes 0, SEEKING steps 5071, WAITING steps 3 |
