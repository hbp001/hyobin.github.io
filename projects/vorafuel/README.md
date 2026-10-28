# VORAFuel portfolio showcase

Bilingual static project page for Hyobin Park. Serve the repository root over
HTTP, then open `projects/vorafuel/`. No build step or external JS dependency.

The interactive canvas and both 36-second MP4 editions use the same saved
public-showcase records. Playback reveals evaluation GT and the observed vessel
track; it does not run inference or update weights. Future GT is never an input.

## Selection and disclosure

`selection.json` documents post-hoc selection: four non-overlapping validation
windows from eight qualifying cases among 75 complete windows. Each selected
case improves both bin MAE and absolute total-consumption error over RF and
fuel-only Chronos-2. This gallery is not a claim of overall superiority.

`showcase.json` contains transformed derived patterns. Absolute dates,
geographic coordinates, physical distances and consumption scales are omitted.
Fuel curves share a per-case normalization; input variables use separate display
scales. The route is a translated, uniformly scaled schematic, not a navigation
map. Missing values are preserved. This transformation is not a guarantee of
anonymity. Source datasets and trained weights are not included and remain
private, available on request subject to provider permissions.

## Verification (2026-10-28)

- Recomputed all four MAE and total-error comparisons from the displayed arrays.
- Chrome: four case buttons, play/reset, English/Korean navigation and language
  persistence via URL passed without page errors.
- Mobile viewport (390 px): no document overflow; fullscreen control available.
- MP4: 1600 x 900, 24 fps, 36 seconds per language; no audio.
