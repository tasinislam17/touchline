# V3: availability and lineup review

Created 2026-10-04T08:55:04.355260+00:00 for GW6. Input observed 2026-10-04T08:54:13+00:00.

Generated 667 player-fixture forecasts and 10 matches. 180 players receive zero availability under the documented policy.
All 20 team-fixture checks satisfy 11 expected starters, including exactly one goalkeeper.

The same-snapshot V2 comparator and availability-only ablation isolate input changes from the lineup adjustment. Original V2 artifacts remain unchanged.

## Interpretation

Official fields and news text are preserved as source facts. A next-round percentage is used as an availability multiplier/cap, not a calibrated chance of starting. Missing-value fallbacks are explicit. News text is displayed, not used to infer diagnoses or parse return dates. A positive next-round percentage takes precedence over an injury/suspension status unless the player is removed or unselectable.

Current flags have not been applied to old games. There is no claimed historical V3 accuracy improvement; it must be evaluated prospectively. Compare V3 with the same-snapshot V2 forecast after results are final.

## Limits

- Availability percentages are an uncalibrated model input, not starting probabilities.
- Only GK/outfield competition is constrained; detailed roles and formations are not inferred from FPL positions.
- Individual minutes are not a joint substitution/90-minute simulation.
- Persistent injuries can already affect historical minutes; the availability multiplier may double-count some of that effect.
- Scorelines are inherited from V2 and do not yet respond to injury news.
- No retrospective injury backtest: observations begin when collected, not at news_added.

4 timestamped availability snapshots are stored in data/availability.sqlite. Import is idempotent; observations are never backdated to news_added.

## Commands

```sh
python fetch_data.py
python run_v3.py
python build_review.py
python serve_review.py
```

For lightweight availability capture only: `python availability.py --fetch`. It does not refresh model forecasts. No recurring capture task is scheduled.

Freeze: `reports/v3/freezes/gw6_20261004T085504355260Z`.

After refreshing finished/data-checked results, run `python score_v3.py` to compare the saved variants without refitting.

Source: [official live FPL API](https://fantasy.premierleague.com/api/bootstrap-static/).
