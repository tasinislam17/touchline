# V4 match-model experiment protocol

Written before running candidate evaluation on 6 October 2026.

Objective: improve probabilistic forecasts, not maximize the number of different modal scorelines.

Keep the selected existing adjusted-r20/h12 model as a fixed comparator, plus a league-average Poisson baseline. Do not edit V1–V3 freezes or protected source files.

Candidate family: opponent-adjusted Poisson attack/defence with multi-season, name-mapped team continuity; goals/xG blending; decay; regularization; optional separate home/away effects. Candidate matrix is fixed in run_v4.py before evaluation. Unknown/promoted teams have explicit pooled priors, never a borrowed same-number team ID. Historical lineups and current injury flags are not reconstructed using hindsight. Expected-lineup adjustments remain experimental until separately validated.

Development: 2025/26 GW4–30 using 2024/25 as prior history. Pick hyperparameters by mean scoreline log loss on development only. Later 2025/26 GW31–38 and current 2026/27 completed GW1–5 are confirmation slices, not tuning targets. All these seasons have been inspected in this project or are available retrospectively: this is chronological retrospective evidence, not an untouched prospective holdout. Do not repeatedly retune against confirmation results.

Acceptance: at least 1% lower combined confirmation scoreline log loss than the current fixed incumbent; result Brier score no worse by >0.01; neither confirmation season's log loss worse by >0.03; no invalid distributions or coverage loss. Report goal MAE, draw calibration, and paired gameweek bootstrap uncertainty. If this finite experiment fails, retain the incumbent in production, report failure and propose a genuinely new experiment/data source. Do not loosen the gate until something passes.

Selection uses only development outcomes. Refit the selected candidate for each evaluation GW from completed matches before its deadline (conservative completion cutoff), including prior-season matches. Never train on the target round or current cumulative standings. Table points/GD may be inspected as historical features only; exclude features with no validated added value. No claim that more features necessarily improve forecasting.

Player integration: retain V3 availability/minutes and recompute components consistently using new team goal rates; do not merely replace scoreline cards while leaving old clean-sheet assumptions. Preserve V3 same-input comparator. A dedicated gate checks recent player-point regression on common support before publication. Upcoming forecasts are frozen before deadline. Production remains experimental pending prospective evidence.

## Round 2 amendment — before correction fitting

Round 1 failed the unchanged 1% combined log-loss gate (0.80% improvement). Development predictions also underpredicted draws (24.3% predicted, 28.0% observed). Preserve round-1 results and code. Test a low-score Dixon–Coles correlation correction, selecting rho from [-0.20, -0.15, -0.10, -0.05, 0, 0.05] solely on development GW4–30. Keep all team parameters fixed at the development-selected round-1 values. This is a new structural distribution correction, not retuning the team matrix or lowering the gate. Confirmation was already inspected; report repeated-use limitations explicitly and require prospective monitoring. No further grid expansion in this run if the correction fails.

Player regression guard: current completed GW2–5, common player-fixture support, identical fitted minutes/rate model and no retrospective injury overlay. Regular-player points RMSE must not worsen by more than 0.02 absolute. A 0.02 tolerance is a development operational guard, not statistical proof. GW1 has no current-season player history, so is excluded from this guard and disclosed. Historical injury flags cannot be honestly replayed.

## Separate feature-model experiment

The fixed team-rating grid and correlation correction both failed promotion; they are retained as rejected candidates. No more hyperparameters are added to that grid. A separate model family now learns actual goals from lagged team xG/goals, short-term form, venue-specific history and reconstructed pre-round points per game. Its small coefficient set is fitted to actual goal outcomes rather than treating xG as the target. This addresses signal calibration and adds substantive features instead of relaxing acceptance.

Three ridge values [1, 5, 20], with/without standings features; choose solely on the original development slice. All feature rows are constructed at the start of the fixture's round. Fit rows must have completed before the target deadline. Correlation remains fixed at zero for this experiment. Confirmation remains the same, explicitly reused and exploratory; do not describe it as independent statistical proof. Acceptance thresholds remain unchanged. Preserve and report failures. This amendment responds to the user's request to continue iteration; it supersedes the earlier stop after the correlation grid, not the promotion standard.

## Feature-family distribution calibration

The independent feature model narrowly failed the unchanged gate (0.989% combined NLL improvement). Its development draw probability remains below observed frequency. Before evaluating this correction, fix the same six rho values as round 2; retain the development-selected ridge=20, standings=False. Choose rho by development NLL only. Do not change thresholds. Confirmation remains repeatedly reused retrospective evidence. Preserve the uncorrected results.

## Identity correction

Final audit found archive Ipswich/live Ipswich Town aliases. Normalize archive Ipswich to Ipswich Town before all experiments. Preserve pre-fix JSON evidence in pre_identity_fix. This is a club identity bug fix, not a weight change. Rerun all evaluations and unchanged gates; do not publish if they fail.
