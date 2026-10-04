# FPL model experiments

Live API snapshot plus a separate 2025/26 archive. Lower error is better. These are initial research results, not proof of an optimal model.

| Evaluation | Regular-player RMSE: model / baseline | Regular-player MAE: model / baseline | Scoreline log loss: model / baseline |
|---|---:|---:|---:|
| current: GW5–5 | 3.342 / 3.559 | 2.393 / 2.608 | 3.561 / 3.205 |
| archive: GW13–38 | 3.052 / 3.298 | 2.170 / 2.403 | 2.902 / 2.944 |

Regulars are identified only from prior appearances (average >=45 minutes). The points baseline is recency-weighted historical points; the scoreline baseline is league-average home/away scoring. Both are refitted using past data only.

## Current experiment

Selection gameweeks: [4]. Held-out gameweeks: [5].
Team settings: `{'prior': 2, 'xg_weight': 0.5}`. Player settings: `{'prior': 90, 'recent': 0.65, 'xg_weight': 1}`; component blend weight 1.

Coverage: 659/667 historical player-fixture rows; 8 omitted, including 1 appearances. Missing predictions are not treated as zero-point successes.
Minutes MAE: 15.38. Start-probability Brier: 0.0944.

| Position, prior regulars | Rows | Points RMSE | Bias |
|---|---:|---:|---:|
| GKP | 20 | 3.418 | -0.909 |
| DEF | 89 | 3.307 | -0.413 |
| MID | 96 | 3.133 | -0.333 |
| FWD | 20 | 4.264 | -0.483 |

GW-block bootstrap 95% interval for mean fold RMSE difference (model minus baseline): None. Negative favours the model. This is not a guarantee and does not account for every time-series dependence.

For prior regulars, fixture points MAE is 2.415 when minutes error is under 30 minutes, versus 2.329 when it is at least 30 minutes. This is an association, not a causal attribution.

## Archive experiment

Selection gameweeks: [4, 5, 6, 7, 8, 9, 10, 11, 12]. Held-out gameweeks: [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38].
Team settings: `{'prior': 8, 'xg_weight': 0.5}`. Player settings: `{'prior': 360, 'recent': 0.65, 'xg_weight': 0.75}`; component blend weight 1.

Coverage: 20,829/20,929 historical player-fixture rows; 100 omitted, including 24 appearances. Missing predictions are not treated as zero-point successes.
Minutes MAE: 14.67. Start-probability Brier: 0.0891.

| Position, prior regulars | Rows | Points RMSE | Bias |
|---|---:|---:|---:|
| GKP | 524 | 2.656 | -0.184 |
| DEF | 2140 | 3.019 | -0.090 |
| MID | 2402 | 2.979 | -0.188 |
| FWD | 547 | 3.477 | -0.446 |

GW-block bootstrap 95% interval for mean fold RMSE difference (model minus baseline): [-0.2868482383417363, -0.20484540338170854]. Negative favours the model. This is not a guarantee and does not account for every time-series dependence.

For prior regulars, fixture points MAE is 2.017 when minutes error is under 30 minutes, versus 2.449 when it is at least 30 minutes. This is an association, not a causal attribution.

## What tuning found

Historical validation selected a 50/50 goals/xG team signal with eight pseudo-matches of shrinkage toward league averages. Player validation selected a 360-minute positional prior, a 0.65 weight multiplier for each older appearance, and a 75% xG/xA blend. It selected the component model without a historical-points blend. These settings were chosen on GW4-12, before scoring GW13-38. The xG blend candidates were close in validation RMSE (3.068 for 75%, 3.069 for 100%, 3.071 for 0%); that is weak evidence for one exact blend, not a reason to claim a precise optimum.

## Interpretation and next steps

The current-season result is one held-out week only. The larger archive gives a more useful robustness check. Do not choose a new model based on these test results and report the same test set as untouched. The next model iteration needs nested temporal evaluation or future games.

Known limitations: independent team-goal distributions, crude empirical minutes forecasts, fixed own-goal allowance, proportional goal allocation, approximate on-pitch clean sheets, empirical bonus rather than joint BPS ranking, no joint lineup/minutes constraint, incomplete new-player coverage, and no historical injury/lineup information. Archive cutoffs use earliest kickoff minus 24 hours. These are reconstructed historical evaluations, not pristine archived pre-deadline forecasts.

The strongest research priorities are appearance/minutes models, opponent-adjusted team ratings, and calibrated joint action simulation. The diagnostic JSON includes probability calibration bins, errors by position and minutes error, and the largest individual misses.

Scoring reconstruction: zero mismatches across both datasets. Automated tests cover defensive thresholds, future-target mutation invariance, probability bounds, team goal reconciliation, and exact scoring reconstruction.

Sources: [live FPL API](https://fantasy.premierleague.com/api/bootstrap-static/), [historical archive](https://github.com/vaastav/Fantasy-Premier-League/tree/master/data/2025-26), [official defensive-contribution explanation](https://www.premierleague.com/en/news/4361991).
