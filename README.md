# The Dugout

Free, independent Fantasy Premier League research and planning. Phases 0–2 introduce the responsive local prototype and validated forecast publication layer. No conversational assistant or paid AI API calls.

```sh
pnpm install --frozen-lockfile
pnpm dev
# Local preview: http://127.0.0.1:4173
```

- [Development plan](THE_DUGOUT_DEVELOPMENT_PLAN.md)
- [Architecture and data contract](docs/ARCHITECTURE.md)
- [Phase 0 feasibility](docs/PHASE_0_FINDINGS.md)
- [Visual design](docs/DESIGN.md)
- [Runbook](docs/RUNBOOK.md)

Node >=22.12 and pnpm 11.19 are required for the frontend. Python commands below use the existing research pipeline. `python scripts/refresh.py` refreshes data and publishes a new validated snapshot. The UI labels its source time and experimental model status. My Team and optimizer screens are **prototypes**, not connected squad management or transfer recommendations.

Development stays local and is pushed to the designated GitHub repository. Netlify deployment is deferred until the user confirms final readiness. The repository URL keeps its original path; product branding is **The Dugout**.

---

# FPL forecasting research

Two linked outputs: a distribution over match scorelines and expected player FPL points.
This is an executable research baseline, not a claim of an optimal or production-ready model.

## Iteration 3 and local forecast review

V3 adds timestamped official availability observations, an explicit availability
policy, and team starter constraints. Official next-round percentages are model
inputs, not calibrated starting probabilities. Valid next-round percentages take
precedence over status flags; removed/unselectable players remain excluded. Missing
percentage fallbacks are recorded with every prediction. Text news is not parsed
as an instruction or used to infer return dates.

```sh
python fetch_data.py
python run_v3.py
python build_review.py
python serve_review.py
```

Open `http://127.0.0.1:8765`. The self-contained `review/index.html` also opens as a
local file. The page provides player search, team/position/availability filters,
sorting, pagination, V2/V3 comparisons, component explanations, match probabilities
and team lineup audits. It displays a saved snapshot; it does not poll the API.

`python availability.py --fetch` captures a lightweight live availability snapshot.
`python availability.py` imports already-downloaded snapshots idempotently. SQLite
as-of queries use the observation time, never a backdated `news_added` timestamp.
No recurring scheduler has been installed. To update the forecast and page, rerun
the full sequence above (reuse an already-running review server).

V3 freezes three variants on the same input snapshot: the unadjusted V2 model,
availability-only adjustment, and availability plus lineup adjustment. Original
V2 models/reports/freezes are checksum-protected and unchanged. Run
`python score_v3.py` after refreshing finished/data-checked results to score the
saved forecasts without refitting. The existing V2 scorer remains separate.

The lineup layer enforces one goalkeeper and ten outfield starter marginals while
respecting availability caps; it fails on infeasible capacity instead of inventing
available players. It does not infer specific football roles from FPL positions,
and is not a joint substitution/minutes simulator. Scoreline forecasts remain V2
outputs; team injury effects are not estimated. Availability mapping is experimental
and requires prospective validation. See `reports/v3/FINDINGS.md`.

## Iteration 2

The new work is isolated in `models/v2.py`, `run_v2.py`, and `reports/v2/`.
V1 code and result checksums are verified before and after the V2 run.

```sh
python fetch_data.py
python run_v2.py
python report_v2.py
python -m unittest discover -s tests -v
```

V2 fits opponent-adjusted team goal rates and regularized appearance/minutes hurdle
models. An expanding inner validation window selects settings before each outer GW.
The original archive has already been inspected, so this is a chronological development
replay, not a fresh independent historical holdout. See `reports/v2/FINDINGS.md` for
results, ablations, calibration diagnostics and limitations.

Each run creates a separate, checksummed early forecast in `reports/v2/freezes/`.
Forecast creation refuses to label a post-deadline prediction as pre-deadline. Full
scoreline probabilities are saved so later scoring never needs to refit a model.
After refreshing data once the predicted GW is finished and data-checked, run:

```sh
python score_freeze.py
# Or score an explicitly chosen earlier freeze:
python score_freeze.py reports/v2/freezes/gw6_TIMESTAMP
```

The scorer detects altered forecasts and season mismatches, reports coverage, and
uses common player-fixture support for model comparisons. The initial experimental
freeze ending `072554429641Z` predates full score-grid persistence; it remains intact
but does not support exact scoreline log-loss evaluation. Use the latest freeze for
the complete prospective comparison. No scheduled task is created by these scripts.

## Run

Python 3.10+ and NumPy are required (`pip install -r requirements.txt`).

```sh
python fetch_data.py
curl -fL https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/2025-26/gws/merged_gw.csv -o data/prior_season.csv
python run_experiments.py
python -m unittest discover -s tests -v
python make_report.py
```

On this machine the bundled Python is `/Users/tasin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`.

The downloader reads the live API, stores every raw response in a new UTC directory,
and writes SHA-256 checksums. It uses four concurrent requests and retries. The user's
downloaded JSON is not a training input. An incomplete download never replaces latest.txt.
The archive is a separate historical validation source, not a substitute for live ingestion.

## Model graph

Past match results and xG -> shrunk team attack/defence -> home/away goal intensities
-> independent Poisson score grid -> result and clean-sheet probabilities.

Past player appearances -> recency-weighted minutes, start, play and 60-minute probabilities.
Past player actions + positional shrinkage -> goal, assist, save, card, penalty and bonus rates.
Team goal intensity reconciles player goals (2% fixed own-goal allowance).
Defensive-action threshold frequencies -> defensive-contribution award probability.
Season scoring weights -> additive expected points. A validation-selected blend with
rolling historical points is a separate challenger (0, 50 or 100% component weight).

The engine emits all component expectations. Bonus is currently an empirical expected
rate, not a joint BPS competition model. Defensive contribution uses a threshold-frequency
model; its raw action estimate is descriptive. Clean sheets approximate full-match survival
conditional on reaching 60 minutes. Player point intervals and haul probabilities are not
implemented: an honest joint simulation is needed before exposing those outputs.

## Experiments and leakage controls

- Current season: train GW1-3 and select on GW4; freeze hyperparameters and evaluate GW5.
- Historical season: expanding windows for GW4-12 validation; freeze hyperparameters and
  evaluate GW13-38, refitting rates on earlier matches at each deadline.
- Nine team configurations and 36 component/blend configurations are compared.
- Training match kickoff plus three hours must precede the prediction cutoff; training
  round must also precede the target. All target-gameweek fixtures are predicted together.
- Historical cutoffs are earliest gameweek kickoff minus 24 hours, a conservative proxy.
  Exact archived deadlines/fixture-publication snapshots are unavailable here.
- No current cumulative player statistics, injury flags, price, ownership, ep_next,
  or retrospective season totals enter forecast features.
- Historical player teams come from fixture histories; current-season position labels
  and player universe come from today's bootstrap, so full point-in-time reconstruction
  is not claimed. Previously unseen players have no prediction; coverage is reported.
- Double-gameweek fixture forecasts are added before player-gameweek points scoring.
  Players with blanks have no fixture rows; this is a fixture-conditional forecast benchmark,
  not a complete squad/transfer strategy backtest.
- Current live API histories may include retrospective corrections. Archived fixture
  schedules are also retrospective. Snapshots collected now improve future evaluation.

Main player selection metric: RMSE for players averaging >=45 minutes before the target
gameweek. Also report MAE/bias and all-player errors, so inactive-player zeros cannot hide
poor predictions for relevant players. Team selection uses scoreline log loss. Lower is
better. Probability MSE is the binary Brier score; result Brier is the unnormalised
three-class sum. Secondary metrics shown under baseline are the component model's metrics;
only points and team scorelines have separate baseline forecasts.

Do not repeatedly tune against GW5 or the archive test block and keep calling it a holdout.
After inspecting these results, any further test-guided changes require a new future test
block or nested rolling evaluation. No optimizer can establish a universally optimum model.

## Next research increments

1. Point-in-time injury, suspension, lineup, transfer/registration and congestion data;
   a calibrated appearance/minutes hurdle model is the first priority.
2. Opponent-adjusted hierarchical team strength, time decay and promoted-team priors;
   compare correlated/Dixon-Coles goal distributions against the simple baseline.
3. Separate penalty and non-penalty goal shares; assist eligibility and own-goal modelling.
4. Joint match simulation for on-pitch clean sheets, action count thresholds and bonus.
5. Calibrated player outcome distributions; nested temporal selection and additional seasons.

All predictions in `reports/next_gameweek_*` are research outputs using match histories
only. They do not yet account for current injury news and should not be presented as
finished FPL recommendations.
