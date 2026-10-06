"""Acceptance test for CMD-TKG4 (written by baseline; the executor may not edit it)."""
import math
import unittest

from app.domains.ingestion.adapters.common import drop_bodies


class DropBodiesInLists(unittest.TestCase):
    def test_dicts_in_lists_lose_bodies(self):
        self.assertEqual(drop_bodies({"turns": [{"text": "SECRET", "n": 1}]}), {"turns": [{"n": 1}]})
        self.assertEqual(drop_bodies({"a": {"b": [[{"prompt": "p", "k": 2}]]}}), {"a": {"b": [[{"k": 2}]]}})

    def test_other_values_kept(self):
        self.assertEqual(drop_bodies({"tags": ["text", 1, None], "n": 3}), {"tags": ["text", 1, None], "n": 3})
        self.assertEqual(drop_bodies({"text": "x", "m": {"content": "y", "z": 1}}), {"m": {"z": 1}})
        self.assertEqual(drop_bodies("plain"), "plain")
