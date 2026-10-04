# The Dugout — implementation contract

Status: Phases 0–2 local implementation. No Netlify service is connected. Repository URL remains https://github.com/tasinislam17/touchline per the user's supplied destination; the product/package identity is The Dugout / the-dugout.

## Decisions

- TypeScript + Vite, browser-rendered semantic HTML and CSS. No SSR or UI framework runtime is required for these screens. Existing Python/NumPy research remains independent. Browser workers will host the future optimizer.
- Static hash routes: Home `#home`, My Team `#team`, Discover `#discover`, fixtures `#fixtures`, comparison `#compare`, watchlist `#watchlist`, optimizer layout `#optimize`, methodology/state previews `#more`.
- Existing model implementations and protected V1/V2 results stay unchanged. A new `pipeline/publication.py` validates research output and produces a versioned app contract. Publication does not train, tune or claim model improvement.
- Personal planning is not implemented yet. No manager profile/picks are bundled, no passwords, authentication, tracking scripts, external fonts or AI API dependencies. Phase 0 probes of the supplied manager ID stayed outside the repository; only field-level findings are documented.
- Netlify configuration is prepared in `netlify.toml`. Only bootstrap/fixture routes are allowlisted. No arbitrary proxy or private FPL endpoints. Manager routes belong to Phase 3. No build hooks or automated Netlify deployment workflows.
- During development use local previews, then commit/push tested batches. Final integration to Netlify waits for the user's readiness decision. Previewing this work does not spend Netlify deploy credits.

## Ownership of modules

| Module | Responsibility |
| --- | --- |
| `fetch_data.py` | Retried public API ingestion, validation, immutable raw snapshot, atomic pointer |
| `availability.py` | Idempotent observed-at availability storage and as-of queries |
| `models/`, `run_v3.py` | Existing experimental forecast and source freeze |
| `pipeline/publication.py` | Data normalization, integrity/coverage checks, publication and prior reference |
| `scripts/refresh.py` | Sequential fetch → forecast → publish, failure status, runtime measurement |
| `web/src/data.ts` | Client manifest loading, SHA-256 verification, fallback and schema boundary |
| `web/src/main.ts` | Local routes, research views, sample squad, player detail, comparison, watchlist |
| `web/src/style.css`, `web/public/brand/` | The Dugout's visual system and original assets |
| `config/season-contract.json` | Rules source/identity/money conventions; not an implemented legality engine |

## Contract v1

`manifest.json` is the publication commit point. It has a schema version, current content-addressed filename/hash/bytes, optional previous reference, publication time, last successful source observation time, manual refresh mode and nullable next schedule. Versioned forecast files are written and synced before atomically replacing the manifest. Publication does not advance the source observation or model creation timestamp. `status.json` records the most recent job attempt separately.

Forecast payload:

- `schema_version`: 1.
- `meta`: season, gameweek, deadline, source observation time, model creation time, source/forecast checksums, model version, stale threshold (24h UI policy, not a guarantee), limitations and schedule state.
- `catalog`: teams, players (price in integer tenths), events with source rule overrides, full fixture list including null-event/null-kickoff fixtures, source settings/position rules. Season namespaces prevent cross-season ID collisions.
- `player_forecasts`: one record per player-fixture, unconditional expected points, expected minutes, appearance/start/60-minute moments, goals, assists, clean-sheet probability, additive points components and availability assumptions.
- `gameweek_totals`: sums all the player's fixtures, including doubles; blank players receive an explicit zero with an empty fixture list.
- `matches`: team goal means, modal score, top scorelines, home/draw/away probabilities and the full probability grid. A modal score is not the rounded pair of means.

Validation rejects missing/duplicate identities, incompatible season/deadline, observation after prediction, predictions after deadline, incomplete forecast coverage, nonfinite values, invalid probability/moment relationships, component mismatches, bad grids and checksum changes. Historical availability uses the first observation timestamp, not `news_added`. Match schedules remain source facts; unconfirmed doubles are not invented.

## User state v1

Only watchlists ship here: `localStorage['the-dugout:watchlist:v1']`, an array of integer player IDs. Invalid storage falls back to empty; blocked storage permits session-only use. No claim of cross-device persistence. A season-aware planning storage schema and migration are Phase 3; do not reuse these IDs across seasons silently.

## Publication and recovery

`python -m pipeline.publication` republishes the existing frozen run, preserving its timestamps. `python scripts/refresh.py` fetches live data and runs the existing V3 configuration before publishing. If a stage fails, the previous publication remains; status changes to failed. Failed raw downloads do not update `data/latest.txt` or write a completed manifest. Orphaned versioned files can exist after an interrupted write, but no committed manifest points to incomplete bytes.

Browser loading verifies SHA-256. If the current file fails integrity/loading/contract validation, it attempts the previous verified file and displays the fallback state. If both fail, it displays a retryable error. A previous release is useful only when one has been published; it is not fabricated on first launch. Multiple concurrent writers are not supported; the CI workflow uses a concurrency group and local refreshes must be serialized.

## Prepared unattended path

`.github/workflows/forecast-refresh.yml` is manual-dispatch only, with no push/pull-request/schedule trigger and no Netlify deployment. Once explicitly invoked it downloads inputs, executes the pipeline and uploads a forecast artifact for review. No workflow has been run or schedule enabled in this phase. GitHub-hosted execution and artifact download must be verified after repository publication and user selection of a runner; local execution is verified now.

The current Free Netlify Scheduled Function time limit (30s) is shorter than our measured complete refresh (~51s). Do not put training in such a function. A future approved free runner plus Netlify Blobs versioned storage is the proposed production refresh path. Blobs publication/account credentials/consistency and live CDN behavior remain launch checks, not proven capabilities. The GitHub Actions schedule can be delayed and is not a precise deadline timer. Freeze comfortably before the deadline, not seconds before it.

## Explicit scope boundary

Implemented: phase specification, original brand/layout, responsive prototypes, real forecast explorer/fixtures, local watchlists, live ingestion, normalized publication and local job orchestration.

Not implemented: real squad import/editing, bank/selling-price reconciliation, legal FPL optimizer, calibrated confidence ranges, multiweek forecasts, production accounts/news/live-rank service, scheduled deployment or trained new model. Sample XI construction is for layout only; it is not budget-checked or labeled as an optimized squad.
