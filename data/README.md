# Raw run files

`robot-play-runs.tar.xz` (8.3 MB) holds every run file behind every number in `results/RESULTS.md`: one `.jsonl` file per run (a header line with the plan and the code hash, then one line per finished episode with the full tool-call log, the memory, the usage and the verdict), grouped in the folders named in [results/code_versions.md](../results/code_versions.md), plus the spend ledger (`runs/spend/ledger.jsonl`) and the zero-practice notebooks (`runs/prior_notebooks`). Pilot and smoke-test folders that no table uses are left out (`runs/pilot20`, `pilot20b`, `pilot21`, `pilot21_pose`, `memsmoke`). The only edit is that local file-system paths inside a few zero-cost crash messages (the three-minute model-directory outage of 17 Nov, deviation 5) were replaced by `<local>`.

Regenerate the report from the files, with no network and no money:

```bash
mkdir -p /tmp/rp && tar -xJf data/robot-play-runs.tar.xz -C /tmp/rp
cd /tmp/rp && /path/to/robot-play/.venv/bin/python /path/to/robot-play/scripts/analyze.py \
    --out /tmp/rp/RESULTS.md --img /tmp/rp/img --meter runs/spend --prior-notebooks runs/prior_notebooks
/path/to/robot-play/.venv/bin/python /path/to/robot-play/scripts/check_run_files.py --reported
```

The regenerated `RESULTS.md` is identical to `results/RESULTS.md` (checked on 17 Nov, 03:40, from a clean checkout without the local logs: `diff` is empty). SHA-256 of the archive: `6c4b48525ca711c1e457ed9c9206603885eb8d2e29dde78f4060d2f07f51a959`.
