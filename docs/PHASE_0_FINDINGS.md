# Phase 0 feasibility findings — The Dugout

Checked 4 October 2026.

## Verified

- The supplied GitHub repository is public and initially empty; no existing branch history to overwrite. Its URL stays unchanged following the product rename.
- Public manager entry and GW5 picks requests for the supplied integration ID returned JSON. Picks had 15 players and fields `element`, `position`, `multiplier`, captain/vice flags and position type. Event history exposed deadline bank/value and transfer count/cost. It did not expose current purchase/selling prices or verified pending transfers/free transfers. The actual personal responses were not copied into app assets, tests or Git.
- Live bootstrap previously returned HTTP 200 without an `Access-Control-Allow-Origin` header for an external origin. A normal cross-origin website fetch cannot read that response. Netlify allowlisted rewrites are the planned same-origin route; actual Netlify-origin checks wait for the final deployment by user instruction.
- Local live refresh fetched 667 histories and completed forecast/publication in approximately 51 seconds. Existing model parameters and frozen V1/V2 evidence are preserved. This is runtime/operational evidence, not new accuracy evidence.
- Existing research has V1/V2 chronological development evaluation and V3 prospective freezes. There is no validated injury/return-date model, no joint lineup simulator, no multiweek optimizer and no calibrated points interval.

## Account-dependent checks intentionally deferred

No Netlify connection or deploy was authorized. Actual account Legacy versus credit-based Free status, shared-site usage, live proxy cache behavior, Netlify Blobs consistency/access, function billing and the first unattended hosted execution cannot be verified locally. These are explicit launch gates. No hosting access or secret is needed to review the current app.

## Zero-cost operating worksheet

For a current credit-based Free account, provisionally 300 monthly credits. Estimate:

`15 × production deployments + 20 × delivered GB + 2 × requests/10,000 + 10 × function GB-hours`

Example assumptions, not a capacity promise: 2 deployments, 5 GB delivery, 100,000 requests and 0.5 function GB-hours totals 155 credits, leaving 145 before other team projects/usage. Measure actual gzip transfer, asset caching, browser sessions and API requests before assigning an expected user capacity. The app bundle is approximately 18 KB gzip (JS + CSS, excluding forecast JSON). Forecast contract size is about 978 KB uncompressed. It is shared rather than separately computed per visitor. Production deploys must never be used as a frequent data-refresh mechanism.

Netlify's team hard cap can pause static pages as well as API functions. Read-only UI is not an escape from a paused account. Budget headroom and reducing polling are operational controls, not guarantees of unlimited free traffic.

## Data and brand dependencies

Original SVG mark, wordmark, pitch and club-color shirt drawings are included. No third-party player photographs, Premier League lion, club badges or commercial stock assets are bundled. The user's reference image is kept locally under an ignored path, not redistributed in the public repository.

The public API has no contractual reliability guarantee established by this work. Public accessibility is not proof of permission for every downstream commercial/republication use. Source/asset terms must be checked before public launch. The name changed to The Dugout during implementation; this is the user's selected working brand, not trademark clearance. No claim of exclusive name or domain availability is made.

## Primary references

- Netlify routing: https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/
- Netlify rates: https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/how-credits-work/
- Scheduled Functions limits: https://docs.netlify.com/build/functions/scheduled-functions/
- Blobs: https://docs.netlify.com/build/data-and-storage/netlify-blobs/
- GitHub event/schedule behavior: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Browser CORS: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS
- Official data: https://fantasy.premierleague.com/api/bootstrap-static/
