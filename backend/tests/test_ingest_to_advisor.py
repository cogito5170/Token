"""CMD-GC24: a Claude Code fixture ingested through the adapter reaches the advisor through usage.api only,
and R2 (reread) fires on it; without hashes it stays silent."""
import unittest
from datetime import datetime, timezone

from app.domains.advisor import api as advisor_api
from app.domains.advisor import wiring as advisor_wiring
from app.domains.advisor.service import AdvisorService, MemoryStore as AdvisorMemoryStore
from app.domains.ingestion.tests.adapters.test_usage_extras import EVENTS, parse_cc
from app.domains.usage import api as usage_api
from app.domains.usage import wiring as usage_wiring
from app.domains.usage.service import MemoryStore, UsageService

WS, SRC, JOB = ("00000000-0000-4000-8000-00000000000%d" % i for i in (1, 2, 3))
NOW = datetime(2026, 3, 10, tzinfo=timezone.utc)


class IngestToAdvisorTests(unittest.TestCase):
    def setUp(self):
        usage_wiring.set_service(UsageService(MemoryStore(), now=lambda: NOW))
        advisor_wiring.set_service(AdvisorService(
            AdvisorMemoryStore(), usage_api.calls, usage_api.tasks, usage_api.prices,
            lambda *a, **k: {"allowed": True, "blocked_by": []}, lambda *a, **k: None, now=lambda: NOW))
        self.addCleanup(usage_wiring.set_service, None)
        self.addCleanup(advisor_wiring.set_service, None)

    def test_r2_fires_on_ingested_claude_code_fixture(self):
        usage_api.load_calls(WS, None, SRC, JOB, parse_cc())
        self.assertIn("R2", [r.rule_id for r in advisor_api.run_rules(WS)])
        f = next(x for x in advisor_api.list_findings(WS) if x["rule_id"] == "R2")
        self.assertTrue(f)

    def test_r2_silent_without_hashes(self):
        for e in EVENTS:
            e = {**e, "data": {k: v for k, v in e["data"].items() if k not in ("system", "messages")}}
            usage_api.load_calls(WS, None, SRC, JOB, parse_cc([e]))
        self.assertNotIn("R2", [r.rule_id for r in advisor_api.run_rules(WS)])


if __name__ == "__main__":
    unittest.main()
