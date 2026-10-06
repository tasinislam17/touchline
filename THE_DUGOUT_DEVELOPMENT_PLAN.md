# The Dugout — phased development plan

Updated: 4 October 2026. Status: Phases 0–2 authorized and locally implemented; see docs/PHASE_0_FINDINGS.md and docs/DELIVERY_PHASES_0_2.md for verified work and deferred provider checks. No Netlify deployment is connected.

## 1. Product commitments

- GitHub repository: **https://github.com/tasinislam17/touchline**, supplied by the user. Use this destination for development pushes; Netlify integration remains deferred until final readiness approval.
- Name: **The Dugout**. A free FPL research, forecasting and squad-planning platform intended for a full public launch.
- Free to users forever: no subscription, paid feature tiers or paid AI API calls. No conversational assistant, chatbot, LLM-generated news or runtime generative AI dependency.
- Statistical prediction models remain central. Train and run our own code; publish reusable forecasts rather than compute a model for each visitor.
- Infrastructure and data budget: £0. Do not enable paid services, automatic upgrades or usage-based billing. A free provider subdomain is acceptable initially; a custom domain is optional and is not assumed free.
- Team ID the locally configured integration ID is the initial integration test case, not a hardcoded public default. Do not publish its personal planning state, bank corrections or transfer scenarios in sample assets.
- Use live FPL sources operationally. Historical archives support evaluation. The downloaded JSON is schema reference only.
- Public launch is the target. Local previews and testing gates precede it; they are engineering checkpoints, not a change to a private-beta product goal.
- Preserve existing model versions, frozen predictions and evaluation evidence. No claim of optimality or guaranteed rank improvement.

## 2. Visual direction and brand

Use the supplied screenshot as the layout and visual-language reference, not as verified live data or an instruction to reuse its assets.

Desktop: deep aubergine sidebar, white/off-white main canvas, pale lavender separators, emerald positive indicators, purple primary actions. Suggested starting tokens: sidebar #23063D, primary #7300CC, positive #008C45, canvas #F6F7FC, text #210C3D. Refine contrast and exact colors during visual review.

Retain the reference's hierarchy: header search and deadline; personalized gameweek summary; three compact transfer/captain/lineup recommendations; large squad pitch; contextual updates and watchlist. Use generous whitespace around the main decisions while keeping research tables useful and dense. Rounded cards and subtle borders are appropriate; avoid oversized generic marketing sections, decorative AI sparkle icons, excessive gradients and identical cards everywhere.

Create an original Dugout SVG wordmark and dugout/pitch emblem, favicon and app icons. Use an original pitch illustration and team-color shirt symbols. Player photographs, club badges, sponsor-bearing shirts and the Premier League lion in the reference are not automatically cleared for reuse. Track asset sources and permissions; use original graphics wherever permitted reuse cannot be established. Do not imply official affiliation. Name availability must be checked before public branding is finalized; this plan does not establish trademark clearance.

Mobile: bottom navigation Home / My Team / Discover / More; add Live only when it is functional. Research tables can scroll horizontally with sticky identity columns and accessible alternatives. Pitch players must remain tappable. Show loading, empty, stale, error and disconnected states with the same visual quality as populated screens.

Do not reproduce mock facts such as GW8, 64 points, Alex or a live rank as real user data. Forecast precision and recommendation language must match available evidence.

## 3. Zero-budget architecture

Hosting decision: **Netlify**, as requested. Internal implementation details remain subject to Phase 0 checks; do not substitute another host.

1. Existing Python pipeline ingests, validates and versions source data and produces shared JSON forecast artifacts.
2. A static TypeScript web application serves the UI and forecast artifacts through Netlify CDN on the user’s free plan, initially with a netlify.app address. Choose the frontend framework once in Phase 0; avoid a full server-rendering stack unless demonstrated necessary.
3. Prefer allowlisted Netlify proxy rewrites for public FPL routes when upstream headers and caching are adequate. Use a small Netlify Function only where validation, transformation or explicit cache behavior requires it. These same-origin routes serve team imports and selected live views. No arbitrary URL proxy. Cache keys, rate limits, upstream timeouts and stale responses are explicit.
4. Planning squads, scenarios, watchlists and preferences live on the device initially, with versioned JSON export/import and a clear reset action. No passwords or accounts in the first public release; Team ID import is not authentication or proof of ownership. Cross-device sync is deferred.
5. Run bounded optimization in a browser worker where practical. Check solver compatibility, bundle size, license, memory and mobile performance before committing. Keep validated Python reference calculations for parity tests.
6. Execute model jobs on an available local machine initially. Evaluate an eligible free scheduled runner and its compute/artifact quotas before adopting it. A public launch needs a tested unattended update path and failure recovery; it must not silently depend on a laptop always being awake. If no free unattended option works, reliable production refresh remains a launch blocker, not an assumed capability.
7. Store and expose snapshot time, forecast time, model version, next scheduled refresh and last successful refresh separately. Failed jobs retain the last good snapshot with a visible stale label. Historical snapshots stay available for reproducibility, with a retention budget.

### Netlify deployment, refresh and budget

- Keep `netlify.toml` in the repository for build/publish configuration, approved API rewrites, headers and any functions. API routing precedes the SPA fallback. Test deep links, JSON content types and missing API routes so they never return the app HTML by mistake.
- During development, build, preview and test locally. Commit and push completed, tested batches to the user-designated GitHub repository. Do not connect Netlify Git integration, create Deploy Previews, deploy phase outputs, or configure GitHub workflows that trigger Netlify deployments. Keep secrets, personal planning state and unsuitable raw data out of commits; confirm the repository destination and visibility before its first publication.
- Only after the user decides the platform is ready, connect that GitHub repository to Netlify and configure the approved production branch for synced deployment. Before connecting, inspect deployment settings so branch pushes and pull requests do not unexpectedly trigger deployments. Thereafter, batch production changes and keep forecast refreshes independent of website deployments. GitHub pushes before integration do not by themselves deploy to Netlify; keep any existing deployment hooks disabled for this project.
- Phase 0 must check whether the user's account is Legacy or credit-based Free, and whether other projects share its allowance. Do not migrate its plan. For current credit-based Free, Netlify documents 300 monthly credits; production deployments cost 15 each, bandwidth 20 per GB, web requests 2 per 10,000 and function compute 10 per GB-hour. These are Netlify operating credits, separate from Codex development usage. Recheck rates against the actual account before launch.
- Build a measured monthly budget: `15 × production deploys + 20 × delivered GB + 2 × requests / 10,000 + 10 × function GB-hours`, plus any other enabled metered features. Reserve headroom for failures and launches. Static delivery and proxy traffic also consume allowance; caching does not make all traffic free.
- Keep model training/backtesting in the existing Python environment or a separately validated free runner. Netlify Scheduled Functions are available on all plans but currently have a 30-second execution limit and automatically run only for published deploys. Use them only for lightweight work that fits measured limits; do not assume the Python training pipeline can run inside one.
- Evaluate Netlify Blobs for versioned forecast JSON independent of frontend deployments. Validate SDK publication from the chosen runner, authenticated writes, read caching, consistency and current billing. Publish immutable versioned files, validate checksums, then update a manifest using supported consistency semantics; retain last-good versions. Never expose write tokens to browsers. Treat this as a Phase 0/2 proof of feasibility, not an already implemented pipeline.
- No Netlify AI Gateway, Agent Runners or paid AI features. Browser workers retain personal planning and optimization. No paid add-ons or auto-upgrades.
- Before allowance exhaustion, reduce optional polling, stop unnecessary deploys and preserve cached functionality where available. Netlify's hard cap can pause **all projects on the team**, including static pages; a server-side read-only fallback cannot keep a paused site online. Locally cached/exported plans may remain usable, but uninterrupted service at unlimited traffic is not promised under the £0 constraint.

### Browser computation versus live data access

Browser-side computation is the default for filters, comparisons, squad scoring, planning, transfer searches and supported live-points calculations. Small-model inference can also move to the browser if payload and device benchmarks support it. Training, historical evaluation and durable pre-deadline snapshots remain shared offline jobs to avoid repeating expensive work on every visitor's device.

FPL hosts its own API; direct browser requests would not consume our server compute. However, public navigation to an API URL does not imply JavaScript on a different website may read its response. On 4 October 2026 a GET to bootstrap-static with Origin https://thedugout.example returned HTTP 200 but no Access-Control-Allow-Origin header. That response does not permit a normal cross-origin browser fetch to read the JSON. This is a header-level finding for that endpoint, not a completed browser test of every endpoint. Phase 0 verifies the relevant endpoints from the actual application origin. Fetch mode no-cors is not a solution because its opaque response cannot be read as JSON.

Therefore shared snapshots or a minimal allowed-endpoint relay are currently needed for this data route; neither requires server-side optimization. A cached relay reduces FPL upstream fetches, although requests reaching the relay may still count toward its hosting quota. Serve shared data as static snapshots where freshness requirements permit. Pause polling in hidden tabs and update only relevant live events. Do not proxy or poll endpoints unnecessarily. Browser computation reduces our compute needs; it does not itself remove cross-origin restrictions, upstream availability limits or the need to record reproducible predictions.

Reference: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS

## 4. How to authorize work and manage development credits

Each numbered subphase below is an independent authorization boundary. Example: **“Implement Phase 1A only; include its tests and stop with the preview.”** Completing a phase does not authorize the next one. Fix failures necessary to satisfy the authorized scope; report new scope separately.

Effort labels are relative, not credit or time quotes: S = small isolated change; M = several connected components; L = substantial integration or research. Model research has greater uncertainty than ordinary UI work. No reliable conversion from a phase to Codex credits is assumed.

Default delivery per authorized batch:

1. State scope and existing inputs; reuse working code and fixtures.
2. Implement that scope and run its targeted checks.
3. Deliver a local preview/artifact, changed files, tests run, measured results, limitations and next proposed batch. Commit and push the completed batch to the designated GitHub repository when configured; report the commit and push outcome. No phase deployment to Netlify.
4. Stop. Do not start an unrelated redesign, broad model search, dependency migration or subsequent phase.

Cost controls: one coherent visual direction; finite model experiment matrices declared before training; cached raw data; small deterministic test fixtures; targeted checks during development and full relevant regression checks at integration gates. Do not rerun expensive unchanged experiments without a reason. Do not use parallel agents unless requested. A research phase can validly conclude “no improvement; retain incumbent.”

## 5. Development phases

### Phase 0 — specification and free-service feasibility

**0A — implementation contract (S).** Inventory the current pipeline and tests. Define first-launch routes, forecast/data contracts, season rules configuration, storage schema and module boundaries. Record excluded features and acceptance criteria. Record the screenshot as the design reference in a durable project location.

**0B — operational feasibility (M).** Test live public Team ID endpoints using the locally configured integration ID; record available versus missing fields without committing identifiable sample data. Verify the actual Netlify account plan and shared allowance, proxy rewrite versus Function behavior, CORS strategy, permitted source use, asset licenses, forecast-job runtime and free scheduler options. Build a quota worksheet using measured payloads, request counts and refresh scenarios. Confirm free account prerequisites and brand availability checks.

**Testing:** network errors, unavailable/invalid Team ID, missing fields, schema change, cache staleness and job runtime. Read-only probes only; provision/deploy when explicitly authorized.

**Exit:** written technical choices and a viable £0 operating path, or precisely identified blockers. No silent reliance on paid news, photos, databases or compute.

### Phase 1 — The Dugout design system and visual prototype

**1A — brand and shell (M).** Original SVG identity/icons; typography, spacing, colors, navigation, header, deadline and reusable controls. Desktop Home and mobile Home using clearly marked representative data. Build the reference's squad pitch and recommendation hierarchy with The Dugout branding.

**1B — core screen prototypes (M).** My Team, player explorer/profile, comparison and optimizer result layouts. Include real loading, stale, error and empty states. Define which values are official facts, forecasts, user edits or assumptions.

**Testing:** browser screenshots at approximately 390px, 768px and 1440px; keyboard navigation, focus, contrast, zoom, overflow and tap targets. Check no mock values are presented as real. Use visual review for layout instead of brittle tests of every CSS declaration.

**Exit:** user reviews the design before broad UI implementation. This is the main visual checkpoint to prevent expensive rework. No large dashboard redesign hidden in later phases.

### Phase 2 — reliable data and forecast publication

**2A — normalized data (M).** Stable season/player/team/fixture/event identities, timestamped raw snapshots, validated schemas, availability observations and point-in-time feature access. Model fixtures explicitly so blank and double gameweeks are represented correctly. Extend the existing ingestion rather than replace it gratuitously.

**2B — publishable forecast contract (M).** Versioned player-fixture and gameweek forecasts, scoreline probabilities, component contributions, coverage and provenance. Add atomic publication, last-good fallback and refresh status. Create the bounded unattended job path selected in Phase 0.

**Testing:** duplicate runs, incomplete downloads, corrupt artifacts, postponed fixtures, double-gameweek aggregation, season mismatch, future-data leakage and publication rollback. Check probability normalization and coherent expected-points component totals. Preserve existing frozen forecast checksums.

**Exit:** UI can consume a reproducible artifact; failed updates cannot publish partial results; refresh failures are detectable.

### Phase 3 — official and planning squad state

**3A — import and reconciliation (M).** Team ID onboarding, latest public locked squad, chip/history context, and last import time. Distinguish a locked squad from pending pre-deadline changes. Ask only for missing current bank, free transfers, actual selling prices and already-made moves. Label estimated versus confirmed values. Do not infer a precise selling price from current price alone.

**3B — local planning state (M).** Editable planning squad, transfers, locks/exclusions, undo/reset, separate official snapshot and versioned export/import. Re-import must show a reconciliation step instead of overwriting a saved plan. Team switching cannot leak another team's local edits.

**Testing:** 3795318 integration plus anonymized synthetic cases; invalid ID; stale history; missing selling prices; changed deadline; corrupt storage; imports from old schema versions; edited plan reconciliation. Verify no FPL credential collection and no automatic real transfers.

**Exit:** a complete, inspectable squad state can be supplied to the optimizer; insufficient information produces a specific request rather than a false feasible result.

### Phase 4 — FPL rules and scoring engine

**4A — legality and state transitions (M).** Season-configured squad size/positions, club limits, legal XI, purchase/sale arithmetic, bank, free-transfer accumulation, hit costs, chips and deadline transitions. Initial squad budget is distinct from an existing squad's bank plus sale proceeds. Follow current official rules rather than hardcoding remembered rules.

**4B — lineup scoring (M).** Captain/vice fallback, goalkeeper substitution, outfield autosub order and formation checks, blanks/doubles, and chip scoring. Support scenarios needed for expected lineup value. Do not multiply appearance probability into unconditional player xPts a second time.

**Testing:** deterministic worked examples and boundary/property tests; no-show captains, illegal subs, all substitutions unavailable, fractional selling gains, transfer caps, Wildcard/Free Hit state restoration, chip expiry and consecutive-use restrictions. Verify outputs against independently calculated examples.

**Exit:** passing rules contract shared by planning and optimization. No transfer recommendations before this gate.

### Phase 5 — forecast validation and short-horizon predictions

**5A — audit and baseline decision (M).** Score frozen forecasts when completed results exist; retain pending freezes without refitting. Expand diagnostics by position, minutes, availability and scoreline calibration. Separate already-inspected development replay from genuinely unseen evaluation.

**5B — one bounded model iteration (L).** Identify the largest measured error source, prerecord a finite experiment set and compare against simple baselines plus incumbent V2/V3 on common support. Use chronological inner tuning and outer evaluation. Address minutes/availability reliability before adding weakly sourced features. Adopt only supported improvements; otherwise retain the incumbent and document the result.

**5C — 3–5 gameweek forecast horizon (L).** Fixture-specific opponent effects and minutes assumptions, season boundaries, blanks/doubles and explicit uncertain return scenarios. Do not carry next-round availability percentages unchanged into every future gameweek. Publish limitations where return dates and future lineups are unknown.

**Testing:** expanding-window GW tests; leakage checks; player-points MAE/RMSE; start/appearance Brier scores; scoreline log loss; calibration and sample coverage. Add captain/transfer decision metrics where historically available inputs support them. Report uncertainty in model comparisons and subgroup regressions; do not select a winner on one GW alone.

**Exit:** a documented production candidate and honest short-horizon forecasts. No arbitrary target accuracy or guarantee that a research batch must improve the model. Calibrated points intervals are a separate optional research task; hide them until validated.

### Phase 6 — useful public research interface

**6A — explorer and fixtures (M).** Live-artifact-backed player explorer, profiles, sorting/filtering, compare 2–5 players, opponent/fixture views, expected scorelines, and forecast component explanations. Distinguish mean goals from the most likely exact score; show relevant probabilities.

**6B — personal context (M).** General/My Team context, watchlists, owned/locked markers and short-horizon totals. Provide a visible methodology and model-performance page from the first public release. Tables must remain useful without player photos.

**Testing:** source-to-screen values, position/club filters, double-gameweek totals, missing players, URL state, mobile tables, keyboard use and large-list rendering. No invented shots, chances created or set-piece roles if unavailable in approved sources.

**Exit:** visitors can research players without importing a team; imported users receive accurate personal context.

### Phase 7 — lineup, captain and transfer optimizer

**7A — zero-transfer decisions (M).** Select legal XI, captain, vice and bench order under the supported scenario model. Explain assumptions and alternatives. Label approximations where full correlated participation outcomes are unavailable.

**7B — one-transfer search (M).** Respect verified budget/selling prices, locks, exclusions, free transfers and hits. Compare against rolling. Show projected net gain, horizon and main assumptions. Do not treat a fixed points threshold as a universal rule for spending a free transfer.

**7C — two-transfer search and performance (L).** Jointly evaluate moves rather than greedily chaining two single transfers. Use bounded candidate search or a validated solver. Expose candidate restrictions, time limits and whether the result is globally optimal, optimal within the candidate pool or merely best found. Keep UI responsive and support cancellation.

**Testing:** brute-force comparison on small synthetic pools; legality of every result; budget boundaries; infeasible constraints; hit accounting; candidate-pruning effects; ties; worker cancellation; low-memory/mobile benchmarks. Compare browser outputs with reference calculations. Evaluate saved pre-deadline recommendations after results, without substituting hindsight candidates.

**Exit:** actionable roll/transfer/lineup/captain alternatives with correct constraints and reproducible calculations. No unsupported “safe captain,” “guaranteed gain,” or rank-chasing claims.

### Phase 8 — integrated dashboard and planning journey

**8A — personalized Home (M).** Wire the approved design to the real squad and optimizer: gameweek plan, conditional projected points, key squad issues, transfer/captain/lineup cards, pitch and watchlist. Display forecast precision honestly and make freshness visible. Empty onboarding remains useful.

**8B — saved decisions and relevant updates (M).** Save a decision with forecast/model version and assumptions. Show structured official availability notices, fixture changes and relevant price information only where available with a supported meaning. Use deterministic explanatory templates based on actual calculations; no AI calls. Link to sources instead of building an unlicensed article archive.

**Testing:** full journey from Team ID to edited plan to recommendation to export; refresh without losing changes; missing news; stale prices; offline reload; all main navigation routes. Ensure the “official squad” label survives all edits and plans never masquerade as submitted transfers.

**Exit:** coherent public-launch product rather than disconnected tools.

### Phase 9 — public-launch verification and operations

**9A — integrated QA (L).** End-to-end regression, mobile/desktop browsers, accessibility, payload/load-time budgets, API input validation, HTML injection defenses, dependency/license review, request throttling and private-state handling. Validate public pages exclude integration-test personal data. Audit external assets and current service terms.

**9B — operational rehearsal (M).** Simulate deadline traffic, upstream outage, quota exhaustion, missed scheduler run, forecast schema migration and rollback. Measure actual limits rather than infer capacity from static-hosting claims. Rehearse locally with mocks and Netlify-compatible tooling; verify configuration for unattended jobs, forecast publication without full redeploys, deployment permissions, no paid billing path and last-good fallback before the account hard cap. Mark CDN, actual scheduled execution and other provider-only checks as pending until the user-authorized first deployment; local simulation is not production verification. Document that Netlify account suspension also disables the hosted fallback. Publish methodology, privacy/storage explanation, independent-platform notice and a support/issue route.

**9C — full public launch (S after gates).** Prepare the exact GitHub release commit, local preview, launch checklist and rollback artifact. Wait for the user to confirm readiness. Only then connect GitHub-synced Netlify deployment for the approved production branch. Verify real routing, cache/CORS behavior, asset delivery and the first scheduled refresh on the deployed site; complete provider-only checks and report any launch defects. No automatic paid upgrades if demand exceeds free capacity.

**Exit:** public URL, operational runbook, passing critical tests, recoverable deployment and explicit known limitations. Zero unresolved critical scoring, privacy or data-freshness defects. Optional features can be absent; broken advertised features cannot.

### Phase 10 — free post-launch expansion, separately authorized

**10A — deeper planning (L).** Multiweek transfer sequences, free-transfer opportunity cost, saved scenarios and future price/availability assumptions. Avoid presenting uncertain future affordability as guaranteed.

**10B — chip planning (L).** Wildcard/Free Hit squad search, Bench Boost and Triple Captain incremental value, expiry and blank/double scenarios. Bench Boost gain must deduct points ordinary autosubs could already supply; Triple Captain's incremental multiplier is one extra captain score above normal captaincy. Test complete chip state transitions and retain uncertainty over unconfirmed schedules.

**10C — limited live tools (L).** Live points, provisional bonus, autosubs and explicitly requested mini-league views with caching and polling budgets. Test correction/reconciliation after official updates. Global rank estimates and ownership cohorts require a separately validated sampling/coverage plan; no exact-live-rank promise by default.

**10D — calibrated distributions (L, research).** Joint score/player participation simulations, validated points intervals, ceiling probabilities and correlations. Only after this foundation consider rival-aware objectives. Test calibration, simulation consistency and decision utility on unseen periods.

**10E — optional convenience (M per batch).** Downloadable reports, calendar reminders, installable app behavior, richer source-linked notices. Account sync, push/email infrastructure or third-party feeds require a demonstrated sustainable free option before inclusion.

## 6. Dependency and release map

Core sequence: **0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9**. Phase 6 research screens can be implemented once 1 and 2 are stable; Phase 5 evaluation can continue while ordinary product work proceeds, but an unvalidated model change does not silently replace the production candidate. Phase 7 needs 3, 4 and an accepted forecast contract/horizon from 5. Phase 10 is not a prerequisite for the first full public launch.

First public launch includes: The Dugout identity and responsive design; team import/planning state; research and comparison; player/scoreline forecasts; short-horizon outlook; zero/one/two-transfer optimizer; XI/captain/bench decisions; watchlists; saved plans; methodology/performance reporting; structured source-linked updates; reliable refresh and failure states.

Removed entirely: conversational assistant, paid AI generation, paid data assumptions, paywalls. Deferred: account sync, broad news aggregation, comprehensive advanced-event feeds, global live-rank service, effective-ownership cohorts, complex multistep/chip optimizers and rival-based rank simulations.

## 7. Test policy and model promotion

- Every functional phase includes tests and bug fixing; Phase 9 is additional integration and operational assurance, not the first testing phase.
- Use deterministic anonymized fixtures for most tests and a small number of live smoke checks. Do not repeatedly hit every FPL endpoint for UI work.
- Model evaluation and software verification are different: passing code tests does not demonstrate forecast accuracy; lower backtest error does not prove production reliability.
- Freeze predictions before deadlines, record the information cutoff, and score without refitting after results are finalized. Track revisions and unavailable historical inputs.
- Retain incumbent and candidate side by side. Promotion requires a documented comparison over multiple chronological evaluation windows, no material unexplained subgroup regression, reproducible artifacts and an operationally affordable runtime. Set concrete statistical criteria in Phase 5 before looking at candidate outcomes.
- If a recommendation gain is smaller than unresolved model uncertainty, communicate that sensitivity rather than presenting a precise advantage as certainty.

## 8. Inputs needed later, not blockers to this plan

Already supplied: product name, UI reference, Team ID, public-launch target and zero-cost constraint.

GitHub destination is supplied: https://github.com/tasinislam17/touchline. Before the first development push, verify access, existing remote history and repository visibility; preserve the existing visibility and do not overwrite remote work. Do not infer permission to publish personal data or secrets. Netlify account access is needed only when the user approves the final GitHub integration; earlier planning can use documentation and locally tested configuration. Confirm Legacy versus credit-based Free plan and the permitted scheduler option before launch.

At Phase 1: review the first The Dugout visual preview before proceeding across every screen.

At Phase 3: confirm bank, free transfers and actual selling prices only where public import cannot establish them. No FPL password.

At Phase 9: user confirmation that development is ready, followed by GitHub-to-Netlify integration and public deployment authorization for the prepared release. No custom domain or paid source is required by default.

## 9. Hosting references checked for this plan

- Netlify credit rates: https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/how-credits-work/
- Free plan and account limits: https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/
- Paused projects: https://docs.netlify.com/manage/accounts-and-billing/billing/resume-paused-projects/
- Proxy rewrites: https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/
- Scheduled Functions: https://docs.netlify.com/build/functions/scheduled-functions/
- Netlify Blobs: https://docs.netlify.com/build/data-and-storage/netlify-blobs/

Provider quotas and terms can change. Reverify before deployment. This plan does not provision services, schedule jobs, alter the models or publish the user's team information.

## Model V4 update — 6 October 2026

Integrated the development-selected cross-season lagged-context goal model after the unchanged retrospective match and player guards passed. See `reports/v4/FINDINGS.md` for all trials, metrics and repeated-confirmation limitations. Fixture headlines show expected goals to two decimals. Player goal/assist and clean-sheet components use the same updated team rates. Refreshes use `freeze_v4.py`; original V1–V3 artifacts remain intact.

Next modelling checkpoint: score the immutable GW6 V4/V3 comparison with `score_v4.py` after final results, then aggregate prospective evidence across multiple gameweeks. Do not claim high accuracy from a single week. Subjective injuries/manager changes have an auditable scenario interface but require timestamped data and separate validation before automatic team-strength changes. Full lineup simulation, model uncertainty and multi-week optimization remain future work. Continue local testing and GitHub updates; no Netlify deployment until explicitly authorized.
