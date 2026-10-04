# Phases 0–2 delivery — The Dugout

4 October 2026. User also requested the product rename during this batch. The original GitHub URL is intentionally unchanged.

## Phase 0

Implemented the architecture/data/route/storage contracts, Netlify configuration, a relative operating-budget worksheet and local runbook. Verified the empty public repository and the supplied FPL team schema using read-only requests. Personal responses stayed outside Git; integration ID is in ignored local configuration. Documented missing bank/free-transfer/selling-price information and the CORS constraint.

Account-specific Netlify quota/plan, actual deployed rewrite/cache behavior, production source-use review and final name clearance remain explicit launch checks. They cannot be truthfully marked verified without the account/deployment that the user chose to defer.

## Phase 1

Original Dugout mark, wordmark/favicon, sidebar, responsive header/navigation, gameweek hero, three decision cards, squad pitch, player detail dialog, comparison layout, fixture board, source notes and watchlist. Discover has real saved forecast data with functional search, filters, sorting and pagination. Sample squad and optimizer interface are labeled as previews; no invented personalized advice or transfer gains. UI includes preview loading/empty/stale/offline/error states and real loader errors/fallback handling.

Reference image is preserved locally but excluded from public redistribution. All shipped graphic assets are original SVG/CSS. Local screenshots cover desktop, tablet and mobile. The user can now review the visual checkpoint before authorizing further UI work.

## Phase 2

Strengthened the existing downloader: normalization, required source structure checks, complete manifest only after all responses, and atomic latest-pointer update. Added immutable content-addressed app publication with source/forecast hash verification, all-player/fixture coverage, point-component totals, probability/grid checks, timestamp/season checks, previous-release reference and independent failure status. Browser verifies the artifact checksum and can fall back to the prior valid release.

Ran one live end-to-end refresh: 667 player histories, 667 player-fixture forecasts, 10 matches and 20 team-lineup checks; completed in 50.89 seconds. Existing V1/V2 protected artifacts were unchanged. This was an operational refresh of V3, not a new modelling iteration. Both old and new V3 freezes remain preserved.

Prepared manual-dispatch-only GitHub refresh workflow that emits an artifact, with no Netlify deployment and no automatic schedule. The production unattended runner/Blobs integration is prepared as an architectural path, not provisioned or verified. This remaining hosted check is explicitly deferred to final readiness/deployment approval.

## Verification

- 39 Python tests passed: existing model/scorer/availability checks plus 12 publication/ingestion cases.
- 5 frontend boundary tests passed: escaping, version rejection, blocked storage, verified fallback and unsafe manifest path rejection.
- TypeScript typecheck and production build passed.
- Headless browser checks passed: search, watchlist, dialog, comparison, fixtures, state preview; seven routes at 390/768/1440px with no page overflow or uncaught browser exceptions.
- Desktop and mobile screenshots reviewed locally. Fixed mobile stacked-card width and keyboard focus after filter/watchlist updates.
- Dependency audit found old Vite build-tool advisories; upgraded to patched Vite 7.3.5 and pinned its esbuild dependency to 0.28.1. Rechecked before delivery.

This is a local development milestone, not a production launch or a claim of completed platform accuracy. Next authorized phase would be Phase 3: real team import/reconciliation and local planning squad state. No Netlify deployment or recurring job has been activated.
