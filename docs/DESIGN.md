# The Dugout visual contract

Reference: user-provided dashboard image, locally retained as `docs/reference/ui-reference.png` (excluded from public Git). The visual review checkpoint is the implemented local prototype, not a screenshot of an unfinished component library.

Original identity: a mint rounded-square D, with the overhead line suggesting a dugout roof/pitch sideline; lowercase wordmark. `web/public/brand/mark.svg` also serves as the favicon. No raster image generation or remote image dependency.

Palette: deep purple navigation (#240b3b family), light canvas (#f6f7fc), white panels, purple actions (#7018bd), green data emphasis (#008553) and mint highlights. System fonts keep first render fast and remove external font requests. Typography separates main decisions, compact labels and detailed research.

Desktop hierarchy follows the reference: sidebar, search/deadline header, gameweek hero, three decision cards, squad pitch, source briefing, watchlist. Illustrative team data and future planner controls are explicitly labeled. Original shirt drawings take the place of unlicensed photos/badges. Mobile has a bottom navigation, horizontally scrollable decision cards, stacked panels and research tables with sticky player columns.

Functional preview routes: Home; My Team sample; Discover (search/filter/sort/pagination); player detail dialog; comparison; fixtures; watchlist; optimizer layout; methodology and simulated loading/empty/stale/offline/error states. No button implies that a transfer or optimization actually happened.

Accessibility foundation: semantic landmarks, skip link, visible focus, native dialog Escape behavior, accessible names, keyboard input, status messages and reduced-motion support. Browser QA covers 390/768/1440px widths and no horizontal page overflow. This is not a claim of completed WCAG certification; full accessibility regression remains in Phase 9.

Asset authorship: mark, wordmark, icons, shirts and pitch were created in this repository. No copied product logo or third-party icon library is included. The GitHub repository path retains its existing name; visible product branding is The Dugout.
