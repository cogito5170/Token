"""Acceptance test for CMD-TKG18 (written by baseline; the executor may not edit it)."""
import unittest
from app.domains.source.service import clean_filename


class T(unittest.TestCase):
    def test_dot_names_fall_back(self):
        for n in ("..", ".", "a/..", "a/.", " .. "):
            self.assertEqual(clean_filename(n), "upload", n)
        self.assertEqual(clean_filename("x/log.jsonl"), "log.jsonl")
