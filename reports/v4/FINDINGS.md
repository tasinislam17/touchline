# V4: measured improvement, experimental release

6 October 2026. Integrated after match and player regression gates passed. No Netlify deployment.

## What changed

The previous model had only five current-season rounds and strong shrinkage. Its expected goal rates all sat between 1 and 2, producing a 1–1 modal score for every upcoming fixture. That was a poor main display of a probability distribution, not a claim that every match would end in a draw.

The selected model fits actual goals using lagged team xG, goals scored/conceded, recent five-match xG, home/away history and home advantage. Histories span 2024/25, 2025/26 and completed 2026/27 fixtures; club names carry identity across seasons. Long-term features use 30 matches and venue features up to 15, with shrinkage for sparse histories. All coefficients are learned jointly, with ridge=20 and annual training decay. A development-selected low-score correlation rho=-0.15 improves draw calibration. Unknown clubs receive pooled feature priors, with greater uncertainty not yet quantified as intervals.

Standings points per game was tested, but did not improve development log loss and is excluded. Literal table rank is not used. Historical player xG is aggregated into team xG; expected individual lineups do not yet feed back into team strength. Existing player minutes, scoring and availability components remain, recomputed with the new team rates.

The platform now prominently displays decimal expected goals to two decimal places. Full precision remains in the data; the UI rounds only to hundredths. Three likely integer scorelines and their probabilities remain secondary. Decimal means are not literal possible final scores.

## Chronological evaluation

Development: 2025/26 GW4–30, 271 matches. Refit at each round using only matches completed before its cutoff. Archive cutoffs are conservative earliest-round kickoff minus 24 hours; current season uses official deadlines. The archive is a final historical extract, not a timestamped vintage of xG corrections.

Confirmation: 2025/26 GW31–38 (79 matches) and current completed GW1–5 (50 matches). Lower values are better.

| Metric | Previous | Selected V4 | Improvement |
|---|---:|---:|---:|
| Combined scoreline log loss | 2.98620 | 2.95067 | 1.19% |
| Combined outcome Brier score | 0.63696 | 0.61990 | 2.68% |
| Combined goal MAE per team | 0.97261 | 0.94854 | 2.47% |
| Latest 50: scoreline log loss | 3.11641 | 3.02896 | 2.81% |
| Latest 50: outcome Brier score | 0.66759 | 0.62486 | 6.40% |
| Latest 50: goal MAE per team | 1.05453 | 0.99848 | 5.31% |
| Established-player xPts RMSE | 3.25982 | 3.22804 | 0.98% |

Player guard: 893 established-player gameweeks, common historical roster, GW2–5. All-player common support: 2,532 player-fixture rows. GW1 is excluded for lack of current-season player history. This isolates team-rate changes with identical player minutes/rate assumptions; historical injuries are not backfilled. It does not validate the prospective availability overlay.

The unchanged match gate required at least 1% lower combined log loss, no material Brier deterioration and no season slice worsening by more than 0.03 NLL. The player guard allowed at most 0.02 RMSE deterioration. Both pass; the NLL gate passes narrowly. Predicted draw frequency is 28.14%, versus 29.46% observed. The paired gameweek bootstrap interval for NLL difference is [-0.07168, -0.00673], conditional on this selected model.

## Rejected experiments and limits

Before the final identity correction, 24 cross-season rating configurations were compared on development. Their selected model improved combined confirmation NLL by only 0.80%, failing promotion. Six low-score corrections on that model also failed (best development-selected variant: 0.86%). A separate six-configuration feature model improved by 0.989%, still failing. Its six-value correlation calibration selected the final model on development, then passed the original confirmation gate.

A final identity audit found that archive “Ipswich” needed mapping to live “Ipswich Town.” After correcting this and rerunning every experiment, the rating model still failed (0.95% NLL gain), its correlation variant passed (1.03%), the independent feature model passed (1.15%), and the already-selected corrected feature model passed (1.19%). Its selected weights did not change. The table above uses corrected identities; original pre-correction results remain in `pre_identity_fix/`.

All failures and the protocol amendments are retained. Confirmation was inspected repeatedly while deciding which structural experiments to try. It is reused retrospective evidence, not an independent holdout. The bootstrap does not account for that adaptive selection. These modest gains do not establish globally optimal weights or “high accuracy.” Continuing to tune until a chosen historical metric looks excellent would exaggerate accuracy.

GW6 forecasts are frozen before the deadline alongside V3 forecasts on the identical refreshed snapshot. `python score_v4.py` will score the saved distributions and player forecasts once results are final, without refitting. It currently reports waiting for final results. No scheduled job was enabled.

## Subjective information

`models/v4_scenarios.py` provides a separate sensitivity layer for injury, manager-change and other observations. Every event needs identity, fixture/team, observation/expiry timestamps, source, reason, confidence and explicit attack/concession multipliers. Future, expired, duplicate and excessive combined adjustments are rejected. Baseline rates and the audit trail are retained. These are uncalibrated assumptions and are not applied to production forecasts.

Next data work: collect pre-deadline lineup/injury/manager observations, quantify the expected replacement's contribution, and test whether adjustments add value beyond form already reflected in the model. A manager change has no universally positive effect, and an injured player's contribution must be compared with their replacement. Evaluate this separately to avoid double-counting effects already in team form and player minutes.

## Reproduction

Use the pinned input checksums in `input_manifest.json`; historical CSVs remain ignored local data. Match inputs are also preserved in `match_inputs.json` for audit. Run:

```
python run_v4.py
python run_v4_features.py
python calibrate_v4.py
python calibrate_v4_features.py
python validate_v4_players.py
python freeze_v4.py
python -m pipeline.publication
python -m unittest discover -s tests -v
```

Refreshing data changes inputs and is a new run, not an exact reproduction. `scripts/refresh.py` fetches live FPL data, freezes the already-selected model and publishes local static assets; it does not retune or deploy. Preserve local raw snapshots to reproduce the player guard exactly. Historical sources: the vaastav Fantasy-Premier-League archive, 2024/25 and 2025/26 merged gameweeks. Live sources: official FPL bootstrap, fixtures and element-summary endpoints.

## Verification

45 Python tests, 5 frontend boundary tests, TypeScript/production build and 21 browser route/viewport checks pass. Browser checks verify every main fixture score has two decimals. Tests cover future-label leakage, club identity, distribution marginals, point/clean-sheet consistency, promotion refusal and scenario timestamp boundaries.
