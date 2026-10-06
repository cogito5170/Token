"""Acceptance test for CMD-TKG15 (written by baseline; the executor may not edit it)."""
import unittest
import base64

from app.domains.identity import tokens


class T(unittest.TestCase):
    def test_non_object_body_is_token_error(self):
        b = lambda x: base64.urlsafe_b64encode(x).rstrip(b"=").decode()
        head = b(b'{"alg":"HS256","typ":"JWT"}')
        for raw in (b'["x"]', b'"x"', b'5'):
            body = b(raw)
            tok = f"{head}.{body}.{tokens._sign('s', head + '.' + body)}"
            with self.assertRaises(tokens.TokenError, msg=raw):
                tokens.decode_access("s", tok, now=1)
