import unittest
from datetime import datetime, timezone

from app.core.events import EventBus
from app.domains.notification.service import (EVENT_KINDS, MemoryStore, NotificationError,
                                              NotificationService)
from app.domains.notification.wiring import subscribe

WS = "00000000-0000-4000-8000-0000000000a1"
U1 = "00000000-0000-4000-8000-000000000001"
U2 = "00000000-0000-4000-8000-000000000002"
PAYLOADS = {
    "quota.alert.raised": {"workspace_id": WS, "alert_id": "a1", "threshold_pct": 80},
    "ingestion.job.finished": {"workspace_id": WS, "job_id": "j1"},
    "ingestion.job.failed": {"workspace_id": WS, "job_id": "j2"},
    "advisor.proposal.created": {"workspace_id": WS, "proposal_id": "p1"},
}


def make(members=(U1, U2)):
    store = MemoryStore()
    svc = NotificationService(store, lambda ws: list(members) if ws == WS else [],
                              lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    bus = EventBus()
    subscribe(bus, svc)
    return svc, store, bus


class EventTest(unittest.TestCase):
    def test_each_event_yields_one_notification_per_recipient(self):
        for name in EVENT_KINDS:
            svc, store, bus = make(members=(U1,))
            bus.publish(name, PAYLOADS[name])
            rows = svc.list(U1)
            self.assertEqual(len(rows), 1, name)
            self.assertEqual((rows[0].kind, rows[0].workspace_id), (name, WS))
        svc, _, bus = make()
        bus.publish("quota.alert.raised", PAYLOADS["quota.alert.raised"])
        self.assertEqual((len(svc.list(U1)), len(svc.list(U2))), (1, 1))

    def test_user_payload_targets_that_user_only(self):
        svc, _, bus = make()
        bus.publish("ingestion.job.failed", {"user_id": U2, "job_id": "j9"})
        self.assertEqual((len(svc.list(U1)), len(svc.list(U2))), (0, 1))
        self.assertEqual(svc.list(U2)[0].ref, "j9")

    def test_unaddressed_or_unknown_event_is_ignored(self):
        svc, store, bus = make()
        bus.publish("ingestion.job.finished", {"job_id": "j1"})
        self.assertEqual(svc.on_event("report.report.generated", {"user_id": U1}), [])
        self.assertEqual(store.rows, [])

    def test_text_never_echoes_free_payload_text(self):
        svc, _, bus = make()
        bus.publish("ingestion.job.failed", {"user_id": U1, "job_id": "j1", "error": "secret-ish prompt body"})
        self.assertNotIn("prompt body", svc.list(U1)[0].text)


class PrefTest(unittest.TestCase):
    def test_disabled_pref_suppresses_only_that_kind_and_user(self):
        svc, _, bus = make()
        svc.put_prefs(U1, [{"kind": "ingestion.job.finished", "channel": "in_app", "enabled": False}])
        bus.publish("ingestion.job.finished", PAYLOADS["ingestion.job.finished"])
        bus.publish("ingestion.job.failed", PAYLOADS["ingestion.job.failed"])
        self.assertEqual([n.kind for n in svc.list(U1)], ["ingestion.job.failed"])
        self.assertEqual(len(svc.list(U2)), 2)

    def test_reenable_and_other_channel_does_not_suppress(self):
        svc, _, bus = make()
        svc.put_prefs(U1, [{"kind": "quota.alert.raised", "channel": "email", "enabled": False}])
        bus.publish("quota.alert.raised", PAYLOADS["quota.alert.raised"])
        self.assertEqual(len(svc.list(U1)), 1)
        svc.put_prefs(U1, [{"kind": "advisor.proposal.created", "channel": "in_app", "enabled": False}])
        svc.put_prefs(U1, [{"kind": "advisor.proposal.created", "channel": "in_app", "enabled": True}])
        bus.publish("advisor.proposal.created", PAYLOADS["advisor.proposal.created"])
        self.assertEqual(len(svc.list(U1)), 2)

    def test_get_prefs_defaults_and_validation(self):
        svc, _, _ = make()
        d = svc.get_prefs(U1)
        self.assertEqual({p["kind"] for p in d}, set(EVENT_KINDS))
        self.assertTrue(all(p["enabled"] and p["channel"] == "in_app" for p in d))
        for bad in ({"kind": "x", "channel": "sms", "enabled": True}, {"kind": "x", "channel": "email"},
                    {"kind": "", "channel": "email", "enabled": True}):
            with self.assertRaises(NotificationError) as c:
                svc.put_prefs(U1, [bad])
            self.assertEqual(c.exception.status, 422)


class ReadTest(unittest.TestCase):
    def test_mark_read_and_unread_filter(self):
        svc, _, bus = make()
        bus.publish("ingestion.job.finished", PAYLOADS["ingestion.job.finished"])
        bus.publish("ingestion.job.failed", PAYLOADS["ingestion.job.failed"])
        a, b = svc.list(U1)
        self.assertIsNone(a.read_at)
        svc.mark_read(U1, a.id)
        svc.mark_read(U1, a.id)  # idempotent
        self.assertEqual([n.id for n in svc.list(U1, unread=True)], [b.id])
        self.assertEqual(len(svc.list(U1)), 2)
        self.assertIsNotNone([n for n in svc.list(U1) if n.id == a.id][0].read_at)

    def test_mark_read_unknown_or_foreign_is_404(self):
        svc, _, bus = make()
        bus.publish("ingestion.job.finished", PAYLOADS["ingestion.job.finished"])
        mine = svc.list(U1)[0]
        for who, nid in ((U2, mine.id), (U1, "00000000-0000-4000-8000-0000000000ff"), (U1, "nope")):
            with self.assertRaises(NotificationError) as c:
                svc.mark_read(who, nid)
            self.assertEqual(c.exception.status, 404)
        self.assertIsNone(svc.list(U1)[0].read_at)


class WiringTest(unittest.TestCase):
    def test_member_lookup_override(self):
        from app.domains.notification import wiring
        wiring.set_member_lookup(lambda ws: [U1, U2])
        try:
            self.assertEqual(wiring._workspace_members(WS), [U1, U2])
        finally:
            wiring.set_member_lookup(None)


class RouterTest(unittest.TestCase):
    def test_routes_present(self):
        try:
            from app.domains.notification.router import router
        except ImportError:
            self.skipTest("fastapi/psycopg not installed")
        paths = {r.path for r in router.routes}
        self.assertEqual(paths, {"/v1/notifications", "/v1/notifications/{notification}/read", "/v1/notification-prefs"})


if __name__ == "__main__":
    unittest.main()
