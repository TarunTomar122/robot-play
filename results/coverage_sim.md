# Coverage of the registered Q1 interval (simulation)

Real `analysis.paired_difference`, nominal 97.5%, 10 run seeds x 3 jobs x 4 held-out episodes, 400 repetitions per row, 5000 bootstrap resamples per repetition (the report uses 10,000). Notebook-arm episodes within a run share a success probability drawn from a beta distribution with intraclass correlation rho; fresh-arm episodes are independent; the two arms are separate runs. Monte Carlo error of each figure is at most +-2.5 points.

| scenario | rho (notebook arm) | true difference | coverage | mean half-width |
|---|---|---|---|---|
| no effect, mixed rates (0.3 / 0.7 / 0.99 in both arms) | 0.0 | +0.0 pp | 98.8% | 13.7 pp |
| no effect, mixed rates (0.3 / 0.7 / 0.99 in both arms) | 0.3 | +0.0 pp | 98.8% | 14.5 pp |
| no effect, every arm at 0.97 | 0.0 | +0.0 pp | 99.5% | 5.5 pp |
| no effect, every arm at 0.97 | 0.3 | +0.0 pp | 98.8% | 6.1 pp |
| Haiku-like: one job with a large gain (0.3 to 1.0), two at 0.99 | 0.0 | +23.3 pp | 99.8% | 9.0 pp |
| Haiku-like: one job with a large gain (0.3 to 1.0), two at 0.99 | 0.3 | +23.3 pp | 100.0% | 9.1 pp |
| small gap, every arm near ceiling (0.95 against 0.99) | 0.0 | +4.0 pp | 98.0% | 5.4 pp |
| small gap, every arm near ceiling (0.95 against 0.99) | 0.3 | +4.0 pp | 98.5% | 5.7 pp |
| Luna-like: fresh 0.96 against a notebook at the ceiling (1.0) | 0.0 | +4.0 pp | 95.8% | 4.7 pp |
| Luna-like: fresh 0.96 against a notebook at the ceiling (1.0) | 0.3 | +4.0 pp | 96.8% | 4.7 pp |
| tiny gap at the ceiling: 0.98 against 1.0 | 0.0 | +2.0 pp | 100.0% | 3.8 pp |
| tiny gap at the ceiling: 0.98 against 1.0 | 0.3 | +2.0 pp | 100.0% | 3.8 pp |
| one-sided: no effect in two jobs at 0.97, a gain of 0.07 in one (0.93 to 1.0) | 0.0 | +2.3 pp | 98.2% | 5.6 pp |
| one-sided: no effect in two jobs at 0.97, a gain of 0.07 in one (0.93 to 1.0) | 0.3 | +2.3 pp | 98.5% | 6.1 pp |
| moderate gain in every job (0.5 to 0.8) | 0.0 | +30.0 pp | 98.2% | 14.2 pp |
| moderate gain in every job (0.5 to 0.8) | 0.3 | +30.0 pp | 97.5% | 16.0 pp |

Reading: quote the lowest coverage in the table, not the nominal 97.5%. The sampling-noise floor treats episodes as independent (design effect 1), so a strongly shared notebook (rho above 0) can make it too narrow; the rows with rho > 0 show how much.
