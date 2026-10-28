# VORAFuel result videos

The results are embedded in the existing flagship project lineup at `index.html#github`.
The old project-page URL redirects to that section; there is no separate landing page.

The two 36-second films show the same four selected validation examples. Actual
GPS positions are rendered over Natural Earth 1:50m land boundaries, with vessel
operating values, forecast wave height and saved fuel predictions. Future
operating observations and GT are displayed for replay and comparison, not fed
into the original forecast. The highlighted prediction is the corresponding
30-minute bin of one saved forecast, not a new online prediction.

The source dataset, raw coordinate records, renderer inputs and trained weights
are not included in this repository. The films contain the selected geographic
tracks and physical fuel results requested for the public demonstration, with
absolute dates and vessel identifiers omitted. Code is linked to hbp001/VORAFuel.

## Selection

Four non-overlapping windows were selected after evaluation from eight qualifying
cases among 75 complete validation windows. Each selected case improves both
bin MAE and absolute total-consumption error over RF and fuel-only Chronos-2.
This is a success-case gallery, not aggregate performance evidence. VORAFuel/RF
use seed 13 and Chronos-2 uses seed 0. See `selection.json` for the selection rule.

## Map attribution

Natural Earth, public-domain 1:50m land polygons:
https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_land.geojson
This is a geographic illustration, not a navigation chart. GPS gaps are not interpolated.
