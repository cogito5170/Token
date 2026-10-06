"""Acceptance test for CMD-TKG11 (written by baseline; the executor may not edit it)."""
import unittest

from app.domains.audit.service import AuditError, check_detail


class TokenCountsNumericOnly(unittest.TestCase):
    def test_numeric_counts_still_allowed(self):
        check_detail({"input_tokens": 5000, "output_tokens": 0, "cache_read_tokens": 7, "max_tokens": None})
        check_detail({"reasoning_tokens": 1.5, "usage": [{"total_tokens": 9}]})

    def test_non_numeric_tokens_values_rejected(self):
        for v in ("abc123", ["abc123"], {"value": "abc123"}, ("abc123",)):
            with self.assertRaises(AuditError, msg=repr(v)):
                check_detail({"refresh_tokens": v})
        with self.assertRaises(AuditError):
            check_detail({"usage": {"access_tokens": ["abc123", "def456"]}})

    def test_other_suffixes_unchanged(self):
        check_detail({"api_key_id": "k_123", "token_fingerprint": "ab:cd:ef", "password_last4": "1234", "has_password": True})
        check_detail({"secret_rotated_at": "2026-10-06T00:00:00Z", "token_count": 3})

    def test_secrets_still_rejected(self):
        for k in ("token", "access_token", "api_key", "refresh_token", "password"):
            with self.assertRaises(AuditError, msg=k):
                check_detail({k: "abc123"})
