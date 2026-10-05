import hashlib
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request

from app.domains.run import gadir, replay, sidecar

FAKE = "fake-" + "sidecar-" + "xyz"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
FIX = os.path.join(ROOT, "fixtures", "monitor")


def script():
    with open(os.path.join(FIX, "script.json"), encoding="utf-8") as f:
        return json.load(f)


def dump(events):
    return "".join(json.dumps(e, separators=(",", ":"), sort_keys=True) + "\n" for e in events)


def tree_state(root):
    out = {}
    for d, _, files in os.walk(root):
        for n in files:
            p = os.path.join(d, n)
            with open(p, "rb") as f:
                out[p] = (os.stat(p).st_mtime_ns, hashlib.sha256(f.read()).hexdigest())
    return out


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.td.name, ".ga")
        os.makedirs(self.root)
        self.rd, self.events = replay.replay(script(), self.root, gadir.GaDirReader)

    def tearDown(self):
        self.td.cleanup()

    def kinds(self):
        return [e["kind"] for e in self.events]

    def test_expected_kinds_in_order(self):
        k = self.kinds()
        first = [x for x in k if not x.startswith("derived:")]
        self.assertEqual(first[:4], ["file:pool.round", "file:queue.added", "file:queue.added", "file:pool.live.claimed"])
        self.assertLess(k.index("l0:node.started"), k.index("file:node.budget.grow"))
        self.assertLess(k.index("file:node.budget.grow"), k.index("l0:peer.message.sent"))
        for want in ("file:node.state.consults", "file:node.pi", "l0:work.accepted", "file:usage.snapshot", "l0:run.end",
                     "file:queue.done", "file:node.state.done", "l0:work.dropped", "l0:node.retired", "derived:all_done"):
            self.assertIn(want, k)
        self.assertLess(k.index("l0:work.accepted"), k.index("l0:run.end"))
        self.assertLess(k.index("l0:run.end"), k.index("l0:work.dropped"))
        self.assertLess(k.index("l0:work.dropped"), k.index("l0:node.retired"))
        self.assertEqual([e["seq"] for e in self.events], list(range(1, len(self.events) + 1)))
        self.assertTrue(all(e["observed_at"].endswith("Z") and e["provenance"] for e in self.events))

    def test_backfill_flag_only_on_first_poll(self):
        bf = [e for e in self.events if e["data"].get("backfill")]
        self.assertTrue(bf)
        self.assertTrue(all(e["observed_at"] == "2026-01-01T00:00:00.000Z" for e in bf))

    def test_truncated_last_line_deferred_not_lost(self):
        runs = [e for e in self.events if e["kind"] == "l0:run.end"]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["data"]["run_duration_ms"], 900)
        self.assertEqual(runs[0]["observed_at"], "2026-01-01T00:00:07.000Z")  # not at t=6000
        self.assertEqual(self.rd.skipped_lines, 0)

    def test_snapshot_and_moods(self):
        s = self.rd.full_snapshot()
        self.assertEqual({t["id"]: t["shelf"] for t in s["tiles"]}, {"w1": "done", "w2": "done", "w3": "done"})
        self.assertEqual(s["meters"]["budget_use_permille"], 400)
        self.assertEqual(s["edges"], [{"a": "n1", "b": "n2", "pi_permille": 750, "messages": 3}])
        self.assertTrue(s["mood"]["all_done"])
        self.assertEqual({f["state"] for f in s["figures"]}, {"retired"})
        self.assertEqual([f["shape_index"] for f in s["figures"]], [0, 1])
        self.assertIn(("derived:collaboration"), self.kinds())

    def test_recording_golden(self):
        with open(os.path.join(FIX, "recording.jsonl"), encoding="utf-8") as f:
            self.assertEqual(f.read(), dump(self.events))

    def test_snapshot_is_a_fold_of_events(self):
        from app.domains.run.snapshot import Snapshot
        s = Snapshot()
        for e in self.events:
            s.apply(e)
        self.assertEqual(s.to_dict(replay.BASE_MS + 10000), self.rd.full_snapshot())

    def test_reader_never_writes(self):
        before = tree_state(self.root)
        r2 = gadir.GaDirReader(self.root, lambda: replay.BASE_MS)
        r2.poll()
        list(gadir.read(self.root))
        self.assertEqual(before, tree_state(self.root))

    def test_stall_after_silence(self):
        with tempfile.TemporaryDirectory() as td:
            clock = [replay.BASE_MS]
            os.makedirs(os.path.join(td, "queue"))
            with open(os.path.join(td, "queue", "001-a.json"), "w") as f:
                json.dump({"id": "a", "role": "r"}, f)
            r = gadir.GaDirReader(td, lambda: clock[0])
            r.poll()
            clock[0] += 130_000
            ev = r.poll()
            self.assertIn(("derived:stall", True), [(e["kind"], e["data"]["value"]) for e in ev])


class SidecarTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.td.name, ".ga")
        os.makedirs(self.root)
        replay.replay(script(), self.root, gadir.GaDirReader)
        self.srv, self.mon = sidecar.serve(self.root, FAKE, poll_ms=50, heartbeat_s=0.2)
        import threading
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}/v1/workspaces/{sidecar.NIL_WS}/monitor/sources"

    def tearDown(self):
        self.mon.stop = True
        self.srv.shutdown()
        self.srv.server_close()
        self.td.cleanup()

    def req(self, url, method="GET", token=FAKE, headers=None):
        h = dict(headers or {})
        if token:
            h["Authorization"] = "Bearer " + token
        try:
            return urllib.request.urlopen(urllib.request.Request(url, method=method, headers=h, data=b"{}" if method != "GET" else None), timeout=5)
        except urllib.error.HTTPError as e:
            return e

    def test_refuses_missing_or_wrong_token(self):
        self.assertEqual(self.req(self.base, token=None).code, 401)
        self.assertEqual(self.req(self.base, token="nope").code, 401)

    def test_refuses_non_get(self):
        for m in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertEqual(self.req(self.base, method=m).code, 405, m)

    def test_get_paths(self):
        src = json.load(self.req(self.base))[0]
        sid = src["id"]
        self.assertTrue(src["reachable"])
        snap = json.load(self.req(f"{self.base}/{sid}/snapshot"))
        self.assertIn("figures", snap)
        recs = json.load(self.req(f"{self.base}/{sid}/recordings"))
        body = self.req(f"{self.base}/{sid}/recordings/{recs[0]['id']}").read().decode()
        self.assertEqual(len(body.splitlines()), recs[0]["events"])
        self.assertEqual(self.req(f"{self.base}/other/snapshot").code, 404)
        self.assertEqual(json.load(self.req(self.base + "?" + "tok" + "en=" + FAKE, token=None))[0]["id"], sid)

    def test_sse_resume_with_last_event_id(self):
        sid = json.load(self.req(self.base))[0]["id"]
        total = len(self.mon.reader.events)
        r = self.req(f"{self.base}/{sid}/events", headers={"Last-Event-ID": str(total - 2)})
        ids = []
        while len(ids) < 2:
            line = r.readline().decode()
            if line.startswith("id: "):
                ids.append(int(line[4:]))
        r.close()
        self.assertEqual(ids, [total - 1, total])

    def test_never_writes_in_ga_dir(self):
        before = tree_state(self.root)
        sid = json.load(self.req(self.base))[0]["id"]
        self.req(f"{self.base}/{sid}/snapshot").read()
        self.assertEqual(before, tree_state(self.root))

    def test_loopback_only(self):
        with self.assertRaises(ValueError):
            sidecar.serve(self.root, "x", host="0.0.0.0")


if __name__ == "__main__":
    unittest.main()
