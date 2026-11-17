# Release height against bin wall height (scripted oracle, 20 layouts per cell)

Layouts: seeds 100 to 119 of the `bins` job with the catch, wall height set by hand. Cells are layouts solved out of 20 when `place` lets go that many metres above the bin floor (the `release_height` argument).

| wall height (m) | 0.02 | 0.04 | 0.05 | 0.06 | 0.07 | 0.08 | 0.10 | 0.14 | 0.18 | 0.22 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.04 | 13 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| 0.07 | 13 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| 0.10 | 0 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| 0.12 | 0 | 0 | 0 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| 0.15 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 20 | 20 | 20 |
| 0.18 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 20 | 20 |
| 0.21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 20 |

The catch's wall is 0.12 m. For it the threshold is sharp (about 6 cm); 0.14 m, the value the hint and the audit use, is a margin of 8 cm over it. Higher release heights up to the 0.30 m limit never failed in this scan, so a model that always lets go from high up solves the job, and the job cannot tell a stored rule from a stored constant.
