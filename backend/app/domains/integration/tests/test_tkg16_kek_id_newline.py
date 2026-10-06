"""Acceptance test for CMD-TKG16 (written by baseline; the executor may not edit it)."""
import unittest
from app.domains.integration import crypto


class T(unittest.TestCase):
    def test_trailing_newline_kek_id_rejected(self):
        for kid in ("k1\n", "k1\n\n"):
            with self.assertRaises(crypto.KeyUnavailable, msg=repr(kid)):
                crypto.kek_env_name(kid)
            with self.assertRaises(crypto.KeyUnavailable, msg=repr(kid)):
                crypto.EnvKeyring({"GC_KEK_ID": kid}).current_id()
        self.assertEqual(crypto.kek_env_name("k1"), "GC_KEK_k1")
