"""CMD-IF2 D2: the demo replay produces a monotone stream the sidecar reader accepts, and writes only in its temp dir."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(HERE, "..", "demo"))
from app.domains.run import gadir  # noqa: E402
import replay  # noqa: E402


def play(root, steps):
    clock = [1767225600000]
    rd = gadir.GaDirReader(root, lambda: clock[0])
    events = []
    for s in steps:
        clock[0] = 1767225600000 + s["t"]
        for op in s["ops"]:
            replay.apply_op(root, op)
        events.extend(rd.poll())
    return rd, events


def snapshot_files(root):
    return sorted(os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs)


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.ga = replay.make_dir()
        self.addCleanup(lambda: __import__("shutil").rmtree(os.path.dirname(self.ga), ignore_errors=True))

    def test_stream_is_monotone_and_covers_the_story(self):
        steps = replay.build_steps()
        self.assertEqual([s["t"] for s in steps], sorted(s["t"] for s in steps))
        self.assertTrue(38_000 <= steps[-1]["t"] <= 40_000)
        rd, ev = play(self.ga, steps)
        self.assertEqual(rd.skipped_lines, 0)
        self.assertEqual([e["seq"] for e in ev], list(range(1, len(ev) + 1)))
        ts = [e["observed_at"] for e in ev]
        self.assertEqual(ts, sorted(ts))
        nodes = {e["node"] for e in ev if e.get("node")}
        self.assertTrue({"design", "frontend", "core-backend", "verifier"} <= nodes)
        self.assertGreaterEqual(len(nodes), 4)
        kinds = [e["kind"] for e in ev]
        self.assertGreaterEqual(kinds.count("l0:peer.message.sent"), 8)
        self.assertGreaterEqual(kinds.count("l0:run.end"), 5)
        self.assertIn("file:queue.failed", kinds)  # red judge
        fail_i = kinds.index("file:queue.failed")
        judge_done = [i for i, e in enumerate(ev) if e["kind"] == "file:queue.done" and e.get("role") == "judge"]
        self.assertTrue(judge_done and judge_done[0] > fail_i)  # then green
        integ = [i for i, e in enumerate(ev) if e["kind"] == "file:queue.done" and e.get("role") == "integration"]
        self.assertTrue(integ and integ[0] > judge_done[0])
        self.assertTrue(rd.snapshot.mood.get("all_done"))

    def test_duration_scales(self):
        self.assertLessEqual(replay.build_steps(10_000)[-1]["t"], 10_000)

    def test_writes_only_inside_its_temp_dir(self):
        before = snapshot_files(os.path.dirname(self.ga))
        play(self.ga, replay.build_steps())
        for f in snapshot_files(os.path.dirname(self.ga)):
            self.assertTrue(os.path.realpath(f).startswith(os.path.realpath(self.ga) + os.sep))
        self.assertTrue(len(snapshot_files(os.path.dirname(self.ga))) > len(before))
        # an op that would escape is refused, and nothing appears outside
        outside = os.path.join(tempfile.gettempdir(), "ga-replay-escape.json")
        for rel in ("../../ga-replay-escape.json", "/tmp/ga-replay-escape.json", "a/../../../ga-replay-escape.json"):
            with self.assertRaises(ValueError):
                replay.apply_op(self.ga, {"op": "write_json", "path": rel, "content": {}})
        with self.assertRaises(ValueError):
            replay.apply_op(self.ga, {"op": "move", "path": "pool.json", "to": "../../x.json"})
        self.assertFalse(os.path.exists(outside))

    def test_dir_must_be_under_the_system_temp(self):
        home = os.path.expanduser("~")
        with self.assertRaises(ValueError):
            replay.make_dir(os.path.join(home, "somewhere"))
        self.assertFalse(os.path.exists(os.path.join(home, "somewhere")))
        self.assertTrue(replay.make_dir(os.path.join(tempfile.gettempdir(), "ga-replay-ok-test")).startswith(tempfile.gettempdir()))
        __import__("shutil").rmtree(os.path.join(tempfile.gettempdir(), "ga-replay-ok-test"), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
