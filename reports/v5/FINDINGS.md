# V5: additional-gameweek evaluation and GW11 forecast

Run on 11 November 2026 using the official FPL snapshot retrieved at 04:27:46 UTC. Completed current-season rounds: GW1–10. The selected GW11 forecast was frozen before the 21 November 2026 11:00 UTC deadline. No Netlify deployment was performed.

## What the new evidence says

The immutable GW6 V4 forecast was scored before V5 tuning. Against the same-snapshot V3 comparison, V4 improved established-player points RMSE from 2.7709 to 2.7551 and exact-score log loss from 3.2000 to 3.1830. Its result Brier score was slightly worse, 0.6536 versus 0.6488. One round is evidence, not a reliable promotion test.

V5 then tested 16 predeclared match configurations. Variables included ridge weight, calendar decay, long/recent/venue form windows, xG-only versus xG-plus-goals features, rest advantage, points per game and low-score correlation. Development gave equal influence to archived 2025/26 GW4–30 and current 2026/27 GW1–8.

The 50-match long-form candidate ranked first in development, but failed the untouched GW9–10 confirmation:

| GW9–10 match metric | V4 retained | 50-match candidate |
|---|---:|---:|
| Exact-score log loss | 2.8675 | 2.8817 |
| Result Brier score | 0.5970 | 0.6056 |
| Goal MAE per team | 0.8619 | 0.8628 |

It lost on both GW9 and GW10, and its paired match bootstrap interval for NLL difference crossed zero, [-0.0213, 0.0480]. It was rejected. No tested match-variable or weighting change replaced V4. The GW11 match coefficients were nevertheless refitted with every completed match through GW10, so the retained architecture uses all newly available results.

## Minutes and player points

Twelve ridge/recency configurations were compared with team rates and player rate assumptions held fixed. Ridge 3 with a 26-gameweek half-life beat the V4 ridge 3/eight-gameweek configuration on GW6–8 development and passed the GW9–10 player guard.

| GW9–10 player metric | V4 minutes | V5 minutes |
|---|---:|---:|
| Established-player xPts RMSE | 2.7730 | 2.7709 |
| Established-player xPts MAE | 2.0697 | 2.0702 |
| All-player RMSE | 1.9113 | 1.9122 |
| Minutes MAE | 12.6364 | 12.4985 |
| Start-probability MSE | 0.06810 | 0.06820 |
| 60-minute probability MSE | 0.07482 | 0.07469 |

This is a small, mixed improvement: the primary established-player RMSE and minutes MAE improved, while established-player MAE, all-player RMSE and start MSE changed slightly in the other direction. It passes the preregistered tolerances, but should not be described as a major accuracy gain. V5 promotes only the minutes half-life from 8 to 26.

## Production candidate

- Match model: retained V4 structure and weights, refitted through GW10.
- Minutes model: ridge 3, half-life 26, fitted through GW10.
- Player rate model: unchanged prior 90, recency 0.65, xG weight 1.0.
- Availability: current official snapshot through the existing uncalibrated overlay.
- Forecast: 672 players across 10 GW11 fixtures, with full score grids and decimal expected goals.

GW11 expected-goal means range from Hull City 1.13–1.38 Brighton to Man City 1.74–1.07 Fulham. The platform continues to display the full decimal means rather than turning each match into a rounded exact-score claim.

The V5 and same-snapshot V4 player forecasts are both preserved. `python score_v5.py` currently reports `waiting_for_final_results`; after GW11 is final it will compare them without refitting.

## Limits and next evidence

GW9–10 contain only 20 confirmation matches and 430 established-player observations. The V5 minutes gain can reverse over future rounds. Further hyperparameter changes must not repeatedly tune against GW9–10. Score the frozen GW11 comparison, accumulate several prospective rounds, and make the next decision from that block.

No injury diagnosis, manager-change boost or expected lineup has been backfilled. Those factors remain in the timestamped scenario interface until enough pre-deadline observations exist to estimate whether they add information beyond team form and player minutes.

## Verification

The source snapshot, two historical archives, selection results, source hashes, V5 forecast and same-snapshot V4 comparator are checksum-bound. Tests cover future-label leakage, score-grid normalization and means, selection tampering, publication integrity and immutable scoring. The existing V1–V4 artifacts remain unchanged.
