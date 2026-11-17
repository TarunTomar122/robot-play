# Which code produced which numbers

Every run file records the hash of the code it ran under (the `robot_play/*.py` files except `analysis.py` and `render.py`, `uv.lock` and the Panda model files). The hash was computed again for each git ref below by exporting that ref and calling `robot_play.runner.code_hash()`; each of the first six and the hint row match the hash in the run files of its folders (the generated tables in [RESULTS.md](RESULTS.md) section 1 list the hashes per folder).

| run folder | what it is | git ref (tag) | commit | code hash |
|---|---|---|---|---|
| `runs/main`, `runs/control`, `runs/frontier`, `runs/frontier_exp`, `runs/main_ext`, `runs/pose` | the registered matrix and its exploratory extension | `matrix-launch` | 9e446d1 | `4d59e8f26cd2a9b6` |
| `runs/borrowed` run seeds 0 to 4 | cheap models read Fable's notebook | `code-borrowed-seeds0-4` | 7f4b501 | `1cd309b2c89e94d7` |
| `runs/borrowed` run seeds 5 to 9, `runs/borrowed_other` | the same, plus the wrong-job control | `code-borrowed-seeds5-9` | 302a7fc | `bdda918f09675319` |
| `runs/borrowed_1`, `runs/borrowed_3` | Fable's notebook after 1 or 3 practice episodes | `code-borrowed-short` | bedacd5 | `90bd12fc77ec6f43` |
| `runs/main_fixhold` | Haiku on `stack`, false-`holding` sentence fixed only | `code-fixhold` | 9d402a7 | `c694b1a45aaf30c5` |
| `runs/main_fixcollide` | Haiku on `stack`, cause fixed too | `code-fixcollide` | 8b7afe3 | `aef351c5c3033d54` |
| `runs/rep_fixed`, gates on the corrected code | the Q1 replication on fresh layouts | `code-fixed` | 2267bf8 | `8fdcf6b2491b68a3` |
| `runs/hint`, `runs/hint_generic`, `runs/prior` | one-sentence hint, generic hint and zero-practice Fable notebook, run seeds 20 to 29 | `code-hint-prior` | d06b0fc | `088c639d7139a3af` |
| `runs/labelmatch` | neutral-label text control, run seeds 20 to 29 | `code-labelmatch` | 78288de | `58b19ca1be3740fe` |
| `runs/wordsplit` | the generic sentence taken apart (Haiku, `stack`), run seeds 20 to 29 | `code-wordsplit` | df1552a | `0346eddace878d63` |
| `runs/wordsplit2` | the split repeated on fresh layouts, run seeds 30 to 39, two nested wordings | `code-wordsplit2` | 82962fd | `c44187af32043997` |
| `runs/dose` | Haiku's own notebook after 1, 3, 6, 12 practice episodes (`stack`), run seeds 20 to 39 | `code-dose` | 3a91bf9 | `33db266fef842900` |
| `runs/second` | Sonnet 5.5 with no memory and with four neutral-label texts (`stack`), run seeds 30 to 39 | `code-second` | e0427e6 | `216aab61b6c8b09e` |
| merged `main` (the code to run for anything new) | all six branches merged, plus the two sentence-split cells, the dose cell and the second-model cells | `main` (its `robot_play/` equals `code-dose` except `analysis.py`, which the hash ignores; each split tag differs from the one before only in `agent.py`, one condition tuple, and `runner.py`, the new cell and its texts) | see `git log` | `216aab61b6c8b09e` |

The registered results (main, control, frontier) come from `matrix-launch` and were produced on the simulator with the defect described in `results/deviations.md` deviation 4. The branch tips were merged into `main` after the matrix finished (the merge changes no registered run file). To reproduce the registered numbers, check out `matrix-launch`; to reproduce the corrected-simulator numbers, check out `code-fixed` (replication, gates) or `code-hint-prior` (hint cells); `main` is the corrected simulator plus every exploratory switch. Differences between hashes are intended: each exploratory cell was added while the matrix was running, from a separate checkout, so the matrix code stayed untouched (PROTOCOL.md v1.4 to v1.6).
