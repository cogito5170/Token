"""Builds a fixture .ga dir from fixtures/monitor/script.json (the CMD-RN1 replay tool). Usage: make_fixture.py DIR"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
from app.domains.run import gadir, replay  # noqa: E402

with open(os.path.join(ROOT, "fixtures", "monitor", "script.json"), encoding="utf-8") as f:
    script = json.load(f)
os.makedirs(sys.argv[1], exist_ok=True)
replay.replay(script, sys.argv[1], gadir.GaDirReader)
