# Skeleton targets (CMD-GC0). CMD-GC11 adds db-up / migrate / CI wiring.
PY ?= python3

.PHONY: test check backtest schema-check

test:            ## the skeleton's test command
	$(PY) -m unittest discover -s tests -t .
	cd backend && $(PY) -m unittest discover -s tests -t .

check:           ## contract checks
	$(PY) scripts/check_docs.py
	$(PY) scripts/validate_openapi.py

backtest:
	$(PY) scripts/backtest_estimator.py

schema-check:    ## apply docs/schema.sql to a throwaway database (needs psql + a reachable server)
	$(PY) -m unittest tests.test_schema
