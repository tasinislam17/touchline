# Iteration 2: forecasts, validation and remaining gaps

V1 code and reports remain unchanged. V2 uses a refreshed, timestamped live API snapshot. These results are chronological development evidence, not a newly untouched historical test: the archive was inspected in iteration 1. Future saved forecasts provide the independent check.

## Results

| Dataset / metric | V1 | V2 | Relative error reduction |
|---|---:|---:|---:|
| 2025/26 GW13–38: Points RMSE, prior regulars | 3.0524 | 3.0142 | 1.25% |
| 2025/26 GW13–38: Minutes MAE, all covered players | 14.6662 | 12.3245 | 15.97% |
| 2025/26 GW13–38: Starting-probability Brier | 0.0891 | 0.0761 | 14.57% |
| 2025/26 GW13–38: Scoreline log loss | 2.9022 | 2.9002 | 0.07% |
| 2026/27 GW5 (one week): Points RMSE, prior regulars | 3.3418 | 3.3216 | 0.60% |
| 2026/27 GW5 (one week): Minutes MAE, all covered players | 15.3794 | 13.0516 | 15.14% |
| 2026/27 GW5 (one week): Starting-probability Brier | 0.0944 | 0.0733 | 22.28% |
| 2026/27 GW5 (one week): Scoreline log loss | 3.5613 | 3.5613 | 0.00% |

Lower is better. Player points are aggregated across fixtures in double gameweeks. “Prior regulars” average at least 45 minutes before the predicted gameweek. Comparisons use the same player-fixture support. Probability Brier scores are squared probability errors.

## What changed

- **Minutes:** regularized logistic models for starting, coming on if benched, and reaching 60 minutes conditional on starting/coming on. Their probabilities form a coherent minutes mixture. Features include recent minutes and starts, start/absence streaks, position, rest, recent workload and time since the last appearance.
- **Team goals:** a regularized Poisson attack/defence model adjusts for opponent strength, home advantage and time decay. Candidate low-score corrections redistribute probability among 0–0, 0–1, 1–0 and 1–1 without changing expected goals or clean-sheet marginals.
- **Player points:** predicted minutes feed the existing action-rate model. We compare full learned minutes, a 50% blend and unchanged V1 minutes. Bonus and defensive-contribution models remain approximate; they were not silently replaced by untested complex models.
- **Little/no history:** prospective forecasts use the actual timestamped roster and positional priors. Historical tests do not invent pre-deadline registrations for debutants.

## Selection protocol

Five team configurations, three learned minutes configurations with two blend weights, and the V1 incumbent. For each outer gameweek, candidate team selection uses earlier scoreline log loss and player selection uses earlier regular-player points RMSE. Candidate fits and features exclude future labels and matches completing after the cutoff. The archive outer replay covers GW13–38, with inner validation beginning at GW4. Current-season minutes models can also train on earlier-season observations; no current future outcomes are included.

Archived fixture schedules/deadlines remain reconstructed: the archive cutoff is earliest kickoff minus 24 hours. This is conservative but not a complete historical as-of data system. Candidate architecture was informed by earlier results, so nested selection does not eliminate researcher hindsight.

## Diagnostics

**Archive:** 20,829/20,929 target player-fixture rows covered; 24 actual appearances remain outside historical coverage. Prospective fallback support does not retroactively repair that gap.

Team selections: `{'v1': 1, 'adjusted_r8_h38': 6, 'adjusted_r8_h12_dc': 19}`. Minutes selections: `{'r3_h8_full': 26}`.

Moving four-gameweek block bootstrap interval for mean fold RMSE difference (V2 − V1): [-0.04759857335635984, -0.03068260123879896]. Negative favours V2; this interval does not account for architecture-selection hindsight.

**Current:** 659/667 target player-fixture rows covered; 1 actual appearances remain outside historical coverage. Prospective fallback support does not retroactively repair that gap.

Team selections: `{'v1': 1}`. Minutes selections: `{'r20_h26_full': 1}`.

Moving four-gameweek block bootstrap interval for mean fold RMSE difference (V2 − V1): None. Negative favours V2; this interval does not account for architecture-selection hindsight.

**Ablation:** keeping V1 minutes while using the selected team model gives points RMSE 3.0545, compared with 3.0524 for the original V1 system. The points improvement comes from the minutes model; the new team model is not independently a demonstrated player-points improvement.

The scoreline gain is very small. Keep the team model experimental and compare it prospectively. Forwards and rare high-point games remain difficult; forecasting an expected mean does not imply forecasting each haul.

## Prospective forecasts

Saved **GW6** forecasts at `reports/v2/freezes/gw6_20261004T073109782166Z`.
Creation: `20261004T073109782166Z`. Deadline: `2026-10-10T10:00:00Z`.

Files contain the V1 forecast, chronologically selected V2 forecast, and a fixed minutes challenger. Each freeze records source-code and input hashes and forecast checksums. Later runs create a new directory rather than replacing old forecasts.

- v1: 667 player-fixture predictions, 10 matches; settings `{'team': 'v1', 'player': 'v1'}`.
- selected_v2: 667 player-fixture predictions, 10 matches; settings `{'team': 'adjusted_r20_h12', 'player': 'r3_h8_full'}`.
- minutes_challenger: 667 player-fixture predictions, 10 matches; settings `{'team': 'adjusted_r20_h12', 'player': 'r20_h8_half'}`.

These are early forecasts, not final deadline forecasts. Current availability status and news are attached but do not yet adjust probabilities. No deadline refresh or monitoring task has been scheduled.

After the GW is finished and data-checked:

```sh
python fetch_data.py
python score_freeze.py
```

The scorer verifies saved forecast hashes and scores without refitting. It reports coverage and common-support comparisons. If results are incomplete, it returns a waiting status. Refreshing before the deadline and rerunning V2 creates another separately timestamped early forecast.

## Remaining work

1. Capture and model point-in-time injuries, suspensions and predicted lineups.
2. Enforce team lineup/minutes consistency, and improve transfer/debutant priors.
3. Build joint bonus and defensive-action simulation, then calibrate player-point distributions.
4. Test across more seasons and prospective gameweeks before promoting the scoreline model.

Method reference: [Dixon and Coles (1997)](https://academic.oup.com/jrsssc/article-abstract/46/2/265/6990546). The V2 team model is a ridge-regularized variant with fixed candidate low-score corrections; it is not a reproduction of that paper’s full estimation procedure.
