# FINAL_TASK results (vendored test fixtures)

- Source: https://github.com/cogito5170/ga-sdk, branch `claude/gracious-meitner-vp49xe`,
  commit `03e8dae19132788e108602cf8b732cd670cfe6e9`, directory `bench/final_task/results/`.
- Files copied unchanged: `runs.jsonl`, `ledger.jsonl`, `SUMMARY.md`, `bulk_files.json`.
- Only these result files are copied (CMD-GC0 rule); no ga-sdk code is vendored.
- `runs.jsonl` rows with `"void": true` (12 rev-1 T2 rows) are excluded everywhere, as in SUMMARY.md.
- Use: `scripts/backtest_estimator.py` (baseline MAPE), estimation global prior, ingestion tests for ledger usage objects.
