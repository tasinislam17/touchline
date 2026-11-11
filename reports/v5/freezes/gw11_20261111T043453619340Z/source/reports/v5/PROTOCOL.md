# V5 additional-gameweek protocol

Written on 11 November 2026 after downloading the public snapshot, identifying completed GW1–10, and scoring the immutable GW6 V4/V3 forecast. No V5 candidate results had been computed when this protocol was written.

## Evidence boundaries

- GW6 is a genuinely prospective frozen forecast and is reported separately. It was inspected before this experiment.
- Candidate development uses 2025/26 GW4–30 plus 2026/27 GW1–8. The archive and current GW1–6 have already been inspected; this is model development, not a holdout.
- Current GW9–10 are the untouched confirmation slice for this experiment. They contain only 20 matches, so a win is encouraging rather than proof of general superiority.
- Once selection and confirmation are complete, the GW11 forecast may fit coefficients on every match completed before its official deadline, including GW9–10. That forecast is new prospective evidence and must be frozen before the deadline.

## Match-model family

The V4 configuration is the fixed comparator: actual-goal target; lagged long-term xG/goals, recent xG, venue xG and home advantage; ridge 20; 365-day half-life; 30/5/15-match long/recent/venue windows; Dixon–Coles rho -0.15; no points-per-game feature.

Test a finite set of single structural changes, declared in `run_v5.py`: ridge 10/40, half-life 180/730 days, recent window 3/8, long window 20/50, venue window 10/20, xG-only features, rest/congestion difference, points-per-game, and rho -0.10/-0.20. Do not expand the grid after seeing GW9–10. Select by the mean of archive-development NLL and current GW1–8 NLL, giving the two seasons equal influence rather than allowing the larger archive to drown out current-season evidence. Report pooled metrics, both selection components, outcome Brier, goal MAE, draw calibration and every candidate.

Promote a match candidate only if development NLL is no worse than V4, GW9–10 NLL improves, Brier is no worse by more than 0.01, neither confirmation GW worsens by more than 0.08 NLL, distributions are valid, and the paired match bootstrap interval is reported. Otherwise retain V4 parameters and still refit its coefficients on all completed data for GW11.

## Player/minutes family

Keep player scoring/rate assumptions and team rates fixed while comparing twelve minutes configurations: ridge 3/10/20 crossed with half-life 4/8/16/26, with full learned minutes. The V4 comparator is ridge 3, half-life 8. Select by established-player points RMSE on GW6–8. Confirm on common-support GW9–10. Also report all-player RMSE, MAE/bias, minutes MAE, start and 60-minute Brier/MSE, and coverage.

Promote a minutes candidate only if development established-player RMSE improves, GW9–10 established-player RMSE does not worsen by more than 0.02, and start/60-minute MSE do not each worsen by more than 0.005. The final combined team/minutes candidate must meet the same player-point guard on GW9–10. Current availability flags are never backfilled into historical matches.

## Subjective information

No retrospective injury diagnosis, manager-change coefficient or expected lineup is fabricated. The existing audited scenario interface remains separate. Before those adjustments can enter the baseline, collect timestamped pre-deadline observations and validate them on future rounds. Current official availability data may affect the prospective player forecast only through the existing explicitly uncalibrated overlay.

## Publication

Preserve V1–V4 code, freezes and results. Write V5 artifacts separately, require immutable input/source checksums, run leakage and distribution tests, publish only a pre-deadline GW11 freeze, and keep Netlify disconnected.
