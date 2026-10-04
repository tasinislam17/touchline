# The Dugout local development and refresh

Requires Node >=22.12, pnpm 11.19, Python >=3.10 and NumPy (see `requirements.txt`).

```sh
pnpm install --frozen-lockfile
pnpm dev
# http://127.0.0.1:4173
pnpm build
pnpm test
python -m unittest discover -s tests -v
```

The committed sanitized public forecast supports UI development without 667 network requests. No manager data is in it. Inspect its observation time in the UI; it is a saved model snapshot, not a live polling service.

## Refresh

```sh
# One-time historical input, if absent; not required just to preview UI
curl -fL https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/2025-26/gws/merged_gw.csv -o data/prior_season.csv
python scripts/refresh.py
# To publish an existing local freeze without refitting:
python -m pipeline.publication
```

Fresh clones do not include raw provider snapshots or the availability database. Refresh creates these. The full Python integration suite requires local raw/history inputs; run a refresh before that suite on a fresh clone. Frontend boundary tests and the saved UI preview do not require these downloads. The old research baseline is retained for reproducibility, not regenerated casually. Do not edit frozen model files to force tests through.

Refresh is serialized: run only one instance at a time. Forecast fitting refuses post-deadline freezes; inspect the next target/deadline rather than bypassing that protection. A failed run leaves `manifest.json` unchanged and writes `status.json`; investigate the stage error and retry. Never rewrite the original prediction timestamp. Failure status is not a new forecast.

## Publication retention and rollback

Every successful publication points to immutable current and previous JSON. Keep both referenced files, plus releases needed for evaluation. The publisher does not auto-delete old files; prune only unreferenced app snapshots after checking retention. Research freezes have separate longer retention. For a local rollback, validate the older release and republish its payload through `publish`; do not modify its model/source timestamps. No automatic remote storage or deletion is configured.

## GitHub and Netlify

Development commits go to the user-specified repository. There is no Netlify deployment connection. The refresh workflow is `workflow_dispatch` only, uploads artifacts only, and does not push forecast data or trigger deployment. No scheduled workflow is enabled. Enable a recurring runner only when explicitly requested and the first hosted manual execution has passed.

After final launch approval, connect the approved GitHub branch to Netlify, inspect build settings and then test the hosted proxy/security headers, routing, caching and refresh publication. Validate the account quota/plan first. The prepared `netlify.toml` does not itself deploy anything.

## Browser QA

Install a compatible Playwright package/browser in your test environment, then run `node scripts/browser-check.mjs` with the dev server running. Optional `PLAYWRIGHT_MODULE` and `PLAYWRIGHT_EXECUTABLE` environment variables can select an existing installation. Screenshots are written to ignored `artifacts/qa/`.
