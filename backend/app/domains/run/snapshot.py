"""MonitorSnapshot as a fold over monitor-event/1 (docs/data-model.md 7.3). Same events -> same snapshot."""
from __future__ import annotations

import copy
from datetime import datetime, timezone


def _ms(s):
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).timestamp() * 1000)


class Snapshot:
    def __init__(self):
        self.round = None
        self.roles: list = []
        self.figures: dict = {}
        self.tiles: dict = {}
        self.edges: dict = {}
        self.meters: dict = {"tokens_total": 0, "cost_cli_microusd": 0}
        self.mood = {"pace": 0, "collaboration": False, "stall": False, "tension": False, "all_done": False}
        self.observed_at = None

    @classmethod
    def fold_copy(cls, base, events):
        s = copy.deepcopy(base)
        for e in events:
            if not e["kind"].startswith("derived:"):
                s.apply(e)
        return s

    def _fig(self, node, role=None):
        f = self.figures.get(node)
        if f is None:
            f = {"node": node, "role": role, "shape_index": 0, "state": "idle", "item": None, "since": None,
                 "_since_ms": None, "turns": 0, "tokens": 0, "cost_cli_microusd": 0, "ring": "none"}
            self.figures[node] = f
        if role and not f["role"]:
            f["role"] = role
        if f["role"] in self.roles:
            f["shape_index"] = self.roles.index(f["role"])
        return f

    def _tile(self, tid, **kw):
        t = self.tiles.setdefault(tid, {"id": tid, "role": None, "shelf": "waiting"})
        for k, v in kw.items():
            if v is not None:
                t[k] = v
        return t

    def _edge(self, a, b):
        a, b = sorted((a, b))
        return self.edges.setdefault((a, b), {"a": a, "b": b, "pi_permille": 0, "messages": 0})

    def apply(self, e):
        self.observed_at = e["observed_at"]
        k, d, node, at = e["kind"], e["data"], e.get("node"), _ms(e["observed_at"])
        if k.startswith("derived:"):
            self.mood[k[8:]] = d["value"]
        elif k == "file:pool.round":
            self.round = d.get("round")
            r = d.get("roles") or []
            self.roles = list(r)
            for f in self.figures.values():
                self._fig(f["node"])
        elif k in ("l0:node.started", "file:pool.live.claimed") and node:
            f = self._fig(node, e.get("role"))
            if f["state"] in ("idle", "retired") or k == "l0:node.started":
                f["state"] = "running"
            f["item"] = e.get("item", f["item"])
            f["since"], f["_since_ms"] = e["observed_at"], at
            if e.get("item"):
                self._tile(e["item"], shelf="held", holder=node, role=e.get("role"))
        elif k == "file:pool.live.idle" and node:
            f = self._fig(node, e.get("role"))
            f["state"] = "idle" if d.get("idle") else "running"
        elif k == "file:pool.live.retiring" and node:
            self._fig(node)["state"] = "retiring"
        elif k == "l0:node.retired" and node:
            f = self._fig(node, e.get("role"))
            f["state"], f["outcome"] = "retired", d.get("outcome")
        elif k == "l0:run.end" and node:
            f = self._fig(node)
            f["turns"] += 1
            f["since"], f["_since_ms"] = e["observed_at"], at
            f["tokens"] += d.get("tokens") if isinstance(d.get("tokens"), int) else 0
        elif k == "file:node.budget.grow" and node:
            f = self._fig(node)
            if d.get("tokens") is not None:
                f["tokens"] = d["tokens"]
            if d.get("cost_cli_microusd") is not None:
                f["cost_cli_microusd"] = d["cost_cli_microusd"]
        elif k == "file:node.state.consults" and node:
            f = self._fig(node)
            f["waiting_for"] = d.get("peers") or []
            if f["waiting_for"]:
                f["state"] = "waiting_peer"
            elif f["state"] == "waiting_peer":
                f["state"] = "running"
        elif k == "file:node.run.cont_open" and node:
            f = self._fig(node)
            if d.get("open"):
                f["state"] = "continuing"
            elif f["state"] == "continuing":
                f["state"] = "running"
        elif k == "file:node.state.done" and node:
            f = self._fig(node)
            st = d.get("status")
            f["ring"] = "verified" if d.get("verified") else (st if st in ("failed", "needs_judgement", "budget") else "none")
        elif k == "file:node.pi":
            self._edge(node, e["peer"])["pi_permille"] = d["pi_permille"]
        elif k == "l0:peer.message.sent" and node and e.get("peer"):
            self._edge(node, e["peer"])["messages"] += 1
        elif k == "file:queue.added":
            self._tile(d.get("id") or e.get("item"), shelf="waiting", role=e.get("role"), parent=d.get("parent"))
        elif k in ("file:queue.done", "file:queue.failed"):
            t = self._tile(d.get("id") or e.get("item"), role=e.get("role"), parent=d.get("parent"))
            t["shelf"] = "done" if k.endswith("done") else "failed"
            t.pop("holder", None)
        elif k == "l0:work.accepted":
            self._tile(d.get("id"), shelf="waiting", parent=e.get("item"), role=e.get("role"))
        elif k == "l0:work.failed" and e.get("item"):
            t = self._tile(e["item"])
            t["shelf"] = "failed"
            t.pop("holder", None)
        elif k == "file:usage.snapshot":
            for key in ("tokens_total", "cost_cli_microusd", "budget_microusd"):
                if d.get(key) is not None:
                    self.meters[key] = d[key]
            b = self.meters.get("budget_microusd")
            if b:
                self.meters["budget_use_permille"] = self.meters["cost_cli_microusd"] * 1000 // b

    def longest_wait_chain(self):
        best = 0
        for start in self.figures:
            seen, cur = set(), start
            while cur not in seen:
                seen.add(cur)
                w = self.figures.get(cur, {}).get("waiting_for") or []
                nxt = next((p for p in w if p in self.figures), None)
                if self.figures.get(cur, {}).get("state") != "waiting_peer" or not nxt:
                    break
                cur = nxt
            best = max(best, len(seen) - 1)
        return best

    def to_dict(self, now_ms):
        figs = []
        for f in sorted(self.figures.values(), key=lambda x: x["node"]):
            o = {k: v for k, v in f.items() if not k.startswith("_")}
            o["elapsed_ms"] = max(0, now_ms - f["_since_ms"]) if f["_since_ms"] is not None and f["state"] in (
                "running", "continuing", "waiting_peer") else 0
            figs.append(o)
        return {"observed_at": self.observed_at, "round": self.round, "figures": figs,
                "tiles": sorted(self.tiles.values(), key=lambda x: x["id"]),
                "edges": sorted(self.edges.values(), key=lambda x: (x["a"], x["b"])),
                "meters": dict(self.meters), "mood": dict(self.mood)}
