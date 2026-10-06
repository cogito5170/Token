"""Acceptance test for CMD-TKG17 (written by baseline; the executor may not edit it)."""
import unittest
import uuid

from app.domains.workspace.service import MemoryStore, WorkspaceError, WorkspaceService


class T(unittest.TestCase):
    def test_non_int_repo_size_loc_rejected(self):
        svc = WorkspaceService(MemoryStore())
        u = str(uuid.uuid4())
        w, _ = svc.create_workspace(u, "Acme")
        for bad in ("big", 1.5, True):
            with self.assertRaises(WorkspaceError, msg=repr(bad)):
                svc.create_project(w.id, u, "p", repo_size_loc=bad)
        svc.create_project(w.id, u, "ok", repo_size_loc=0)
