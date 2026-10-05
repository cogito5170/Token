import unittest

from app.core.events import EventBus
from app.domains.workspace.service import MemoryStore, WorkspaceError, WorkspaceService

U1, U2, U3 = ("00000000-0000-4000-8000-00000000000%d" % i for i in (1, 2, 3))


def make():
    store, audit = MemoryStore(), []
    store.emails = {"a@example.com": U1, "b@example.com": U2, "c@example.com": U3}
    return WorkspaceService(store, audit=lambda a, u, d: audit.append((a, u, d))), store, audit


class BoundaryTest(unittest.TestCase):
    def test_non_member_gets_404_on_another_workspace(self):
        svc, *_ = make()
        w, _ = svc.create_workspace(U1, "Team A")
        for call in (lambda: svc.get_workspace(w.id, U2), lambda: svc.members(w.id, U2),
                     lambda: svc.projects(w.id, U2), lambda: svc.create_project(w.id, U2, "p"),
                     lambda: svc.add_member(w.id, U2, "c@example.com", "viewer")):
            with self.assertRaises(WorkspaceError) as c:
                call()
            self.assertEqual(c.exception.status, 404)

    def test_malformed_or_unknown_ws_is_404(self):
        svc, *_ = make()
        for ws in ("not-a-uuid", "11111111-1111-4111-8111-111111111111"):
            with self.assertRaises(WorkspaceError) as c:
                svc.require_member(ws, U1)
            self.assertEqual(c.exception.status, 404)

    def test_viewer_cannot_create_project(self):
        svc, *_ = make()
        w, _ = svc.create_workspace(U1, "Team A")
        svc.add_member(w.id, U1, "b@example.com", "viewer")
        with self.assertRaises(WorkspaceError) as c:
            svc.create_project(w.id, U2, "p")
        self.assertEqual(c.exception.status, 403)
        self.assertEqual(svc.projects(w.id, U2), [])

    def test_role_ranks(self):
        svc, *_ = make()
        w, _ = svc.create_workspace(U1, "Team A")
        svc.add_member(w.id, U1, "b@example.com", "developer")
        self.assertEqual(svc.create_project(w.id, U2, "p").name, "p")
        with self.assertRaises(WorkspaceError) as c:  # developer is not admin
            svc.add_member(w.id, U2, "c@example.com", "viewer")
        self.assertEqual(c.exception.status, 403)
        self.assertEqual(svc.require_member(w.id, U1, "admin").role, "admin")


class PersonalWorkspaceTest(unittest.TestCase):
    def test_user_created_makes_personal_workspace_once(self):
        svc, store, _ = make()
        bus = EventBus()
        bus.subscribe("identity.user.created", svc.on_user_created)
        bus.publish("identity.user.created", {"user_id": U1})
        bus.publish("identity.user.created", {"user_id": U1})
        ws = svc.list_workspaces(U1)
        self.assertEqual(len(ws), 1)
        self.assertEqual(ws[0][1], "admin")
        self.assertEqual(ws[0][0].name, "Personal")
        self.assertEqual(svc.list_workspaces(U2), [])


class CrudTest(unittest.TestCase):
    def test_members_projects_and_conflicts(self):
        svc, _, audit = make()
        w, role = svc.create_workspace(U1, "Team A")
        self.assertEqual(role, "admin")
        svc.add_member(w.id, U1, "B@Example.com", "viewer")
        with self.assertRaises(WorkspaceError) as c:
            svc.add_member(w.id, U1, "b@example.com", "viewer")
        self.assertEqual(c.exception.status, 409)
        with self.assertRaises(WorkspaceError) as c:
            svc.add_member(w.id, U1, "nobody@example.com", "viewer")
        self.assertEqual(c.exception.status, 404)
        with self.assertRaises(WorkspaceError) as c:
            svc.add_member(w.id, U1, "c@example.com", "owner")
        self.assertEqual(c.exception.status, 422)
        svc.create_project(w.id, U1, "p", repo_size_loc=10)
        with self.assertRaises(WorkspaceError) as c:
            svc.create_project(w.id, U1, "p")
        self.assertEqual(c.exception.status, 409)
        self.assertEqual(len(svc.members(w.id, U2)), 2)
        self.assertTrue(all(set(d) <= {"workspace_id", "user_id", "role", "project_id", "personal"}
                            for _, _, d in audit))

    def test_same_name_workspaces_get_distinct_slugs(self):
        svc, *_ = make()
        a, _ = svc.create_workspace(U1, "Team")
        b, _ = svc.create_workspace(U2, "Team")
        self.assertNotEqual(a.slug, b.slug)

    def test_list_only_own(self):
        svc, *_ = make()
        svc.create_workspace(U1, "A")
        svc.create_workspace(U2, "B")
        self.assertEqual([w.name for w, _ in svc.list_workspaces(U1)], ["A"])


class HttpTest(unittest.TestCase):
    def test_routes_with_stub_identity(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi/httpx not installed")
        from app.domains.workspace._identity import current_user
        from app.domains.workspace import wiring
        from app.domains.workspace.router import router

        svc, *_ = make()
        wiring._service = svc
        who = {"id": U1}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[current_user] = lambda: type("U", (), {"id": who["id"]})()
        try:
            c = TestClient(app)
            ws = c.post("/v1/workspaces", json={"name": "T"}).json()
            self.assertEqual(c.post(f"/v1/workspaces/{ws['id']}/projects", json={"name": "p"}).status_code, 201)
            who["id"] = U2
            self.assertEqual(c.get(f"/v1/workspaces/{ws['id']}").status_code, 404)
            self.assertEqual(c.post(f"/v1/workspaces/{ws['id']}/projects", json={"name": "q"}).status_code, 404)
        finally:
            wiring._service = None


if __name__ == "__main__":
    unittest.main()


class AuditWiringTest(unittest.TestCase):
    def test_default_recorder_is_audit_api_record(self):
        try:
            from app.core import db
            from app.domains.audit.api import record
            from app.domains.workspace import wiring
        except ImportError:
            self.skipTest("runtime deps missing")
        orig_pool, orig_get = db._pool, db.get_pool
        db._pool = object()
        wiring.set_audit_recorder(None)
        try:
            self.assertIs(wiring.get_service().audit, record)
            fake = lambda a, u, d: None  # noqa: E731
            wiring.set_audit_recorder(fake)
            self.assertIs(wiring.get_service().audit, fake)
        finally:
            wiring.set_audit_recorder(None)
            db._pool = orig_pool
