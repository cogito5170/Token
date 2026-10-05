import threading
import unittest

from app.domains.ingestion import registry
from app.domains.ingestion.service import IngestError, MemoryStore

from .helpers import SRC, WS, make

GOOD = b"FAKE\nclaude-sonnet-5-5,10,5\nclaude-sonnet-5-5,20,6\n!junk\nno-such-model,1,1\n"


class PipelineTest(unittest.TestCase):
    def tearDown(self):
        registry.unregister("claude_code")

    def test_job_runs_through_states_and_counts(self):
        svc, store, _ = make({"u1": GOOD})
        jid = svc.enqueue("u1")
        self.assertEqual(svc.run_one("w1"), jid)
        j = svc.get_job(WS, jid)
        self.assertEqual((j.state, j.inserted, j.duplicates, j.rejected), ("done", 2, 0, 2))
        self.assertEqual((j.source_kind, j.parser, j.attempts), ("claude_code", "fake@0", 1))
        self.assertEqual([e.stage for e in store.events_after(jid, 0)],
                         ["queued", "parsing", "normalizing", "loading", "analyzing", "done"])
        self.assertEqual([e.seq for e in store.events_after(jid, 0)], [1, 2, 3, 4, 5, 6])
        self.assertEqual(sorted(store.rej[jid]), [(4, "bad_line"), (5, "unknown_model")])

    def test_reupload_is_duplicates_not_inserts(self):
        svc, _, _ = make({"u1": GOOD, "u2": GOOD})
        a, b = svc.enqueue("u1"), svc.enqueue("u2")
        svc.run_until_empty("w")
        self.assertEqual(svc.get_job(WS, a).inserted, 2)
        # same dedupe keys on the second job -> duplicates
        self.assertEqual((svc.get_job(WS, b).inserted, svc.get_job(WS, b).duplicates), (0, 2))

    def test_enqueue_is_idempotent_for_a_live_upload(self):
        svc, _, _ = make({"u1": GOOD})
        self.assertEqual(svc.enqueue("u1"), svc.enqueue("u1"))
        with self.assertRaises(IngestError):
            svc.enqueue("missing")

    def test_events_published(self):
        svc, _, _ = make({"u1": GOOD})
        seen = []
        svc.publish = lambda n, p: seen.append((n, p))
        svc.enqueue("u1")
        svc.run_one("w")
        self.assertEqual(seen[-1][0], "ingestion.job.finished")
        self.assertEqual(seen[-1][1]["upload_id"], "u1")
        self.assertIn("ingestion.job.progressed", [n for n, _ in seen])


class ClaimTest(unittest.TestCase):
    def tearDown(self):
        registry.unregister("claude_code")

    def test_two_workers_never_claim_one_job(self):
        files = {f"u{i}": GOOD.replace(b"10,5", f"{i},5".encode()) for i in range(40)}
        svc, store, _ = make(files)
        for u in files:
            svc.enqueue(u)
        got, lock = [], threading.Lock()

        def work(name):
            while True:
                c = store.claim(name)
                if c is None:
                    return
                with lock:
                    got.append(c.id)

        ts = [threading.Thread(target=work, args=(f"w{i}",)) for i in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(got), 40)
        self.assertEqual(len(set(got)), 40)
        self.assertTrue(all(j.attempts == 1 for j in store.rows.values()))

    def test_claimed_job_is_not_claimed_again(self):
        svc, store, _ = make({"u1": GOOD})
        svc.enqueue("u1")
        self.assertIsNotNone(store.claim("a"))
        self.assertIsNone(store.claim("b"))


class FailureTest(unittest.TestCase):
    def tearDown(self):
        registry.unregister("claude_code")

    def test_failed_job_has_code_and_no_content(self):
        svc, store, _ = make({"u1": b"FAKE\nBOOM\n"}, max_attempts=3)
        jid = svc.enqueue("u1")
        svc.run_until_empty("w")
        j = svc.get_job(WS, jid)
        self.assertEqual((j.state, j.attempts, j.last_error_code), ("failed", 3, "internal_error"))
        dump = repr([vars(e) for e in store.events_after(jid, 0)]) + repr(vars(j)) + repr(store.rej.get(jid))
        self.assertNotIn("sk-ant", dump)
        self.assertNotIn("prompt text", dump)
        self.assertEqual(store.events_after(jid, 0)[-1].stage, "failed")

    def test_retry_until_max_then_failed_and_event_published_once(self):
        svc, _, _ = make({"u1": b"FAKE\nBOOM\n"}, max_attempts=2)
        seen = []
        svc.publish = lambda n, p: seen.append(n)
        jid = svc.enqueue("u1")
        self.assertEqual(svc.run_one("w"), jid)
        self.assertEqual(svc.get_job(WS, jid).state, "queued")
        self.assertEqual(svc.run_one("w"), jid)
        self.assertEqual(svc.get_job(WS, jid).state, "failed")
        self.assertEqual(seen.count("ingestion.job.failed"), 1)
        self.assertIsNone(svc.run_one("w"))

    def test_unsupported_format_code(self):
        svc, _, _ = make({"u1": b"nothing known"}, max_attempts=1)
        jid = svc.enqueue("u1")
        svc.run_one("w")
        self.assertEqual(svc.get_job(WS, jid).last_error_code, "unsupported_format")

    def test_retry_then_success(self):
        files = {"u1": b"FAKE\nBOOM\n"}
        svc, _, _ = make(files)
        jid = svc.enqueue("u1")
        svc.run_one("w")
        files["u1"] = GOOD
        svc.run_one("w")
        j = svc.get_job(WS, jid)
        self.assertEqual((j.state, j.attempts, j.inserted), ("done", 2, 2))


class StreamTest(unittest.TestCase):
    def tearDown(self):
        registry.unregister("claude_code")

    def _ids(self, frames):
        return [int(f.split("\n")[0][4:]) for f in frames if f.startswith("id: ")]

    def test_resume_after_last_event_id_has_no_gaps(self):
        svc, _, _ = make({"u1": GOOD})
        jid = svc.enqueue("u1")
        svc.run_one("w")
        full = list(svc.stream(WS, jid))
        self.assertEqual(self._ids(full), [1, 2, 3, 4, 5, 6])
        for k in range(0, 7):
            self.assertEqual(self._ids(svc.stream(WS, jid, k)), list(range(k + 1, 7)), k)

    def test_event_names_and_close(self):
        svc, _, _ = make({"u1": GOOD})
        jid = svc.enqueue("u1")
        svc.run_one("w")
        frames = list(svc.stream(WS, jid))
        self.assertTrue(frames[0].startswith("id: 1\nevent: progress\n"))
        self.assertIn("event: done\n", frames[-1])
        self.assertEqual(list(svc.stream(WS, jid, 6)), [])  # already done: closes at once

    def test_failed_stream_ends_with_failed_event(self):
        svc, _, _ = make({"u1": b"FAKE\nBOOM\n"}, max_attempts=1)
        jid = svc.enqueue("u1")
        svc.run_one("w")
        self.assertIn("event: failed\n", list(svc.stream(WS, jid))[-1])

    def test_follows_live_events(self):
        svc, _, _ = make({"u1": GOOD})
        jid = svc.enqueue("u1")
        out = []
        t = threading.Thread(target=lambda: out.extend(svc.stream(WS, jid, 0, wait_s=0.05)))
        t.start()
        svc.run_one("w")
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertEqual(self._ids(out), [1, 2, 3, 4, 5, 6])

    def test_other_workspace_is_not_found(self):
        svc, _, _ = make({"u1": GOOD})
        jid = svc.enqueue("u1")
        with self.assertRaises(IngestError):
            list(svc.stream("00000000-0000-4000-8000-0000000000ee", jid))

    def test_heartbeat_while_idle(self):
        svc, _, _ = make({"u1": GOOD})
        jid = svc.enqueue("u1")
        t = iter([0.0, 0.0, 1.0, 20.0, 40.0, 60.0])
        g = svc.stream(WS, jid, 1, heartbeat_s=15, wait_s=0.01, clock=lambda: next(t))
        self.assertEqual(next(g), ": heartbeat\n\n")


if __name__ == "__main__":
    unittest.main()


class BoundaryTest(unittest.TestCase):
    def test_ingestion_code_does_not_query_other_domains_tables(self):
        import re
        from pathlib import Path

        pat = re.compile(r"\b(FROM|JOIN|INTO|UPDATE)\s+(uploads|sources|usage_\w+|workspaces|users)\b", re.I)
        root = Path(__file__).resolve().parents[1]
        bad = [f"{f.name}: {m.group(0)}" for f in root.glob("*.py") for m in pat.finditer(f.read_text())]
        self.assertEqual(bad, [])
