PY ?= python3
COMPOSE ?= docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: test check backtest schema-check db-up db-down migrate secret-scan

test:            ## unit tests (runner: unittest)
	$(PY) -m unittest discover -s tests -t .
	cd backend && $(PY) -m unittest discover -s tests -t .
	$(PY) -m unittest discover -s infra/tests -t .

check:           ## contract checks + secret grep
	$(PY) scripts/check_docs.py
	$(PY) scripts/validate_openapi.py
	$(PY) infra/secret_scan.py

secret-scan:     ## secret-pattern grep over the tree
	$(PY) infra/secret_scan.py

backtest:
	$(PY) scripts/backtest_estimator.py

db-up:           ## start postgres:16 (needs .env, see .env.example)
	$(COMPOSE) up -d --wait db

db-down:
	$(COMPOSE) down

migrate:         ## apply backend/migrations/*.sql in order (needs psql; DATABASE_URL)
	@test -n "$$DATABASE_URL" || { echo "DATABASE_URL is not set"; exit 1; }
	@for f in $$(ls backend/migrations/*.sql | sort); do echo "apply $$f"; psql "$$DATABASE_URL" -v ON_ERROR_STOP=1 -qf $$f || exit 1; done

schema-check:    ## apply docs/schema.sql to a throwaway database (needs GC_SCHEMA_TEST_DSN)
	$(PY) -m unittest tests.test_schema
