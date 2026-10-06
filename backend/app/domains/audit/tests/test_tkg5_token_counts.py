"""Acceptance test for CMD-TKG5 (written by baseline; the executor may not edit it)."""
import math
import unittest

from app.domains.audit.service import AuditError, check_detail


class TokenCounts(unittest.TestCase):
    def test_token_counts_are_allowed(self):
        check_detail({"input_tokens": 5000, "output_tokens": 12, "cache_read_tokens": 7, "max_tokens": 4096})
        check_detail({"cache_write_tokens": 3, "total_tokens": 9, "reasoning_tokens": 4, "prompt_cache_tokens": 1})
        check_detail({"usage": [{"input_tokens": 1}]})

    def test_secrets_still_rejected(self):
        for k in ("token", "access_token", "api_key", "refresh_token", "password"):
            with self.assertRaises(AuditError, msg=k):
                check_detail({k: "abc123"})
