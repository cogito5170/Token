"""check_docs.py: green on the repo, red on each mutation of CMD-GC0 D2 (and a few more)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_docs  # noqa: E402

IGNORE = shutil.ignore_patterns(".git", ".venv", "node_modules", "__pycache__", ".next", ".ga")


class CheckDocsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(REPO, self.root, ignore=IGNORE)

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, rel, old, new, count=1):
        p = self.root / rel
        text = p.read_text(encoding="utf-8")
        self.assertIn(old, text, f"mutation anchor missing in {rel}")
        p.write_text(text.replace(old, new, count), encoding="utf-8")

    def problems(self):
        return check_docs.run(self.root)

    def assertCaught(self, needle):
        probs = self.problems()
        self.assertTrue(any(needle in p for p in probs), f"{needle!r} not in {probs}")

    def test_repo_is_clean(self):
        self.assertEqual(self.problems(), [])

    # ---- D2 mutations
    def test_domain_removed_from_architecture(self):
        self.edit("docs/architecture.md", "| `quota` | Quota |", "| Quota |")
        self.assertCaught("quota has no row in the architecture.md domain table")

    def test_table_with_two_owners(self):
        self.edit("docs/domain-model.md", "- owned_tables: `budgets`, `budget_alerts`",
                  "- owned_tables: `budgets`, `budget_alerts`, `usage_calls`")
        self.assertCaught("table usage_calls has 2 owners")

    def test_openapi_path_without_domain(self):
        self.edit("docs/api/openapi.yaml", "  /v1/workspaces/{ws}/quota/alerts:\n    x-domain: quota\n",
                  "  /v1/workspaces/{ws}/quota/alerts:\n")
        self.assertCaught("/v1/workspaces/{ws}/quota/alerts has 0 x-domain entries")

    def test_screen_points_at_missing_path(self):
        self.edit("docs/visualization.md", "- api: `GET /v1/workspaces/{ws}/usage/series/tokens`",
                  "- api: `GET /v1/workspaces/{ws}/usage/series/token-mix`")
        self.assertCaught("token_mix reads GET /v1/workspaces/{ws}/usage/series/token-mix, which is not in openapi.yaml")

    def test_advisor_rule_without_fixture(self):
        (self.root / "fixtures" / "advisor" / "R3.json").unlink()
        self.assertCaught("R3 fixture fixtures/advisor/R3.json does not exist")

    def test_advisor_rule_fixture_line_removed(self):
        self.edit("docs/consulting.md", "- fixture: `fixtures/advisor/R5.json`\n", "")
        self.assertCaught("R5 has no fixture")

    # ---- more
    def test_domain_removed_from_ownership(self):
        self.edit("docs/ownership.md", "| `backend/app/domains/report/**` | consulting | no |\n", "")
        self.assertCaught("report has no backend/app/domains/report/** row in ownership.md")

    def test_table_without_owner(self):
        self.edit("docs/domain-model.md", "- owned_tables: `reports`", "- owned_tables: ")
        self.assertCaught("table reports has 0 owners")

    def test_screen_wrong_method(self):
        self.edit("docs/visualization.md", "- api: `GET /v1/workspaces/{ws}/budgets/{budget}/burn`",
                  "- api: `POST /v1/workspaces/{ws}/budgets/{budget}/burn`")
        self.assertCaught("budget_burn reads POST")

    def test_unowned_file(self):
        (self.root / "stray.txt").write_text("x", encoding="utf-8")
        self.assertCaught("stray.txt matches 0 patterns")

    def test_work_item_file_outside_role(self):
        self.edit("docs/roadmap.md", '"files": ["backend/app/domains/report/**"]',
                  '"files": ["backend/app/domains/report/**", "backend/app/domains/usage/**"]')
        self.assertCaught("CMD-GC34: file backend/app/domains/usage/** belongs to ingestion-analytics")

    def test_work_item_contract_file_in_feature(self):
        self.edit("docs/roadmap.md", '"files": ["backend/app/domains/simulation/**"]',
                  '"files": ["backend/app/domains/simulation/**", "docs/schema.sql"]')
        self.assertCaught("only a contract item may own it")

    def test_independent_items_share_files(self):
        self.edit("docs/roadmap.md", '"files": ["frontend/src/app/(app)/upload/**"',
                  '"files": ["frontend/src/app/(app)/overview/**", "frontend/src/app/(app)/upload/**"')
        self.assertCaught("CMD-GC41 and CMD-GC43 both own")


if __name__ == "__main__":
    unittest.main()
