# Phase 3 delivery — official and planning squad state

Delivered locally on 6 October 2026. No Netlify deployment was created or connected.

## Public import contract

The My Team route accepts a numeric public FPL Team ID. It reads three official, read-only endpoints through same-origin `/api/fpl` routes:

- entry summary;
- latest completed/locked gameweek picks;
- season history and chips.

The local Vite preview and prepared Netlify configuration proxy only those GET paths. The browser never receives an FPL credential, write token or mutation route. Team ID `3795318` was used for the authorized live integration check; no returned personal payload is committed.

The imported official snapshot contains the manager/team label, locked gameweek, 15 picks, captain, vice-captain, bench order, last locked bank and team value, rank, points, active chip and chip history. The UI calls these fields **locked** or **historical**. It does not present them as the manager's current pre-deadline state.

The public API does not expose current free transfers, pending transfers, purchase prices or exact selling prices. The application does not derive selling price from current market price. Current bank and free transfers are explicit planning inputs; selling price is captured per planned transfer when known. Missing values remain `null` and visibly marked as needed.

## Local planning state

Each Team ID has a separate versioned browser-storage key. Its planning copy supports:

- same-position player replacements without claiming transfer legality;
- current bank and free-transfer confirmation;
- captain and vice-captain selection;
- squad locks and target exclusions;
- undo, reset to official, JSON export and validated JSON import;
- persistence across reloads.

Official and planned squads remain separate. Re-import refreshes timestamps when the locked squad is unchanged. When a new official squad differs and the existing plan contains edits, the application stages it as `pendingOfficial` and asks whether to retain the plan or restart from the new official squad. It never silently overwrites local edits. Switching Team IDs changes context without deleting another team's saved plan.

The transfer editor enforces unique players and an unchanged FPL position so the stored object remains structurally complete. It deliberately does not claim budget, club-limit, formation, hit or chip legality; those checks belong to the shared Phase 4 rules engine.

## Verification

- TypeScript and Vite production build passes.
- 12 frontend boundary tests pass: five publication/storage tests and seven squad-state tests.
- The complete Python model/publication suite remains unchanged and passing from V4 delivery.
- Browser QA passes 21 route/viewport overflow checks with zero page exceptions.
- A live local proxy check imported Team ID `3795318`, verified 11 starters plus four bench players, preserved a planned move and manual bank/free-transfer inputs over reload, and captured desktop review output.

The live API check is point-in-time integration evidence, not a permanent guarantee of upstream availability. Netlify redirect behavior remains prepared configuration until the user-authorized deployment in Phase 9.
