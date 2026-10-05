# migrations

Plain SQL, applied in order. `0001_init.sql` is created by CMD-GC10 (the baseline).
Later changes come only from contract work items, each adding `NNNN_<name>.sql` and appending the same bytes to `docs/schema.sql`: all migrations concatenated in order are byte-identical to `docs/schema.sql` (tests/contract).
