"""Acceptance test for CMD-TKG20 (written by baseline; the executor may not edit it)."""
import unittest
from app.domains.identity.service import AuthError, normalize_email


class T(unittest.TestCase):
    def test_malformed_emails_rejected(self):
        for e in ("a@@b.com", "a@b@c.com", "a b@c.com", "a@b .com"):
            with self.assertRaises(AuthError, msg=e):
                normalize_email(e)
        self.assertEqual(normalize_email(" a@b.com "), "a@b.com")
