"""Read-only .ga reader -> monitor-event/1 (docs/data-model.md 7). stdlib only; never writes inside the .ga dir."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

from .snapshot import Snapshot

READER_VERSION = "1"
KIND_RE = re.compile(r"^[a-z_.]+$")
WINDOW_MS = 60_000
STALL_MS = 120_000


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def _now_ms() -> int:
    return int(time.time() * 1000)


class GaDirReader:
    """poll() returns the MonitorEvents newly observed since the last call. `now_ms` is injectable for replay."""

    def __init__(self, path, now_ms=_now_ms):
        self.root = os.fspath(path)
        self.now_ms = now_ms
        self.events: list[dict] = []
        self.snapshot = Snapshot()
        self.skipped_lines = 0
        self._seq = 0
        self._first = True
        self._sig: dict = {}      # key -> (stat sig, sha256) of last parsed json
        self._json: dict = {}     # key -> last parsed json
        self._offsets: dict = {}  # key -> byte offset of jsonl
        self._qstatus: dict = {}  # queue id -> dir
        self._times: list[int] = []
        self._last_signal = None
        self._mood: dict = {}

    # -- low-level, read-only helpers -------------------------------------------------
    def _p(self, *parts):
        return os.path.join(self.root, *parts)

    def _read_json(self, key, path):
        """Parsed json if changed since last time, else None. Parse failure keeps the previous value."""
        try:
            st = os.stat(path)
            sig = (st.st_mtime_ns, st.st_size)
            if self._sig.get(key, (None, None))[0] == sig:
                return None
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            return None
        digest = hashlib.sha256(raw).hexdigest()
        if self._sig.get(key, (None, None))[1] == digest:
            self._sig[key] = (sig, digest)
            return None
        try:
            val = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        self._sig[key] = (sig, digest)
        self._json[key] = val
        return val

    def _read_lines(self, key, path):
        """New complete jsonl records; a truncated last line is deferred to the next poll."""
        try:
            size = os.stat(path).st_size
        except OSError:
            return []
        off = self._offsets.get(key, 0)
        if size < off:
            off = 0
        if size == off:
            return []
        try:
            with open(path, "rb") as f:
                f.seek(off)
                chunk = f.read(size - off)
        except OSError:
            return []
        out = []
        pos = 0
        while pos < len(chunk):
            nl = chunk.find(b"\n", pos)
            end = len(chunk) if nl < 0 else nl
            line = chunk[pos:end]
            try:
                rec = json.loads(line.decode("utf-8")) if line.strip() else None
            except (ValueError, UnicodeDecodeError):
                if nl < 0:
                    break  # truncated tail: defer, do not advance past it
                rec = None
                self.skipped_lines += 1
            if isinstance(rec, dict):
                out.append(rec)
            elif rec is not None and line.strip():
                self.skipped_lines += 1
            pos = end + 1 if nl >= 0 else len(chunk)
        self._offsets[key] = off + min(pos, len(chunk))
        return out

    def _emit(self, kind, source_file, provenance, node=None, role=None, item=None, peer=None, **data):
        if self._first:
            data["backfill"] = True
        ev = {"seq": self._seq + 1, "observed_at": iso(self._t), "kind": kind}
        for k, v in (("node", node), ("role", role), ("item", item), ("peer", peer)):
            if v is not None:
                ev[k] = v
        ev["data"] = data
        ev["source_file"] = source_file
        ev["provenance"] = provenance
        self._seq += 1
        self._new.append(ev)
        return ev

    # -- polling ----------------------------------------------------------------------
    def poll(self) -> list[dict]:
        self._t = self.now_ms()
        self._new: list[dict] = []
        self._scan_pool()
        self._scan_queue()
        for node in self._node_names():
            self._scan_node(node)
        self._scan_l0()
        self._scan_usage()
        real = [e for e in self._new]
        if real:
            self._last_signal = self._t
            self._times.extend([self._t] * len(real))
        self._derive()
        self._first = False
        for e in self._new:
            self.snapshot.apply(e)
            self.events.append(e)
        return self._new

    def _scan_pool(self):
        pool = self._read_json("pool", self._p("pool.json"))
        if not isinstance(pool, dict):
            return
        prev = getattr(self, "_pool", {}) or {}
        self._pool = pool
        roles = pool.get("roles") or []
        if pool.get("round") != prev.get("round") or roles != prev.get("roles") or self._first:
            self._emit("file:pool.round", "pool.json", "OBSERVED", round=pool.get("round"), n=pool.get("n"),
                       roles=list(roles) if isinstance(roles, list) else sorted(roles), attempts=pool.get("attempts"))
        live, plive = pool.get("live") or {}, prev.get("live") or {}
        for node in sorted(live):
            cur, old = live[node] or {}, plive.get(node) or {}
            role, item = cur.get("role"), cur.get("item")
            if item != old.get("item") or node not in plive:
                self._emit("file:pool.live.claimed", "pool.json", "OBSERVED", node=node, role=role, item=item,
                           since=cur.get("since"), children=cur.get("children"))
            if bool(cur.get("idle")) != bool(old.get("idle")) and (cur.get("idle") or old):
                self._emit("file:pool.live.idle", "pool.json", "OBSERVED", node=node, role=role, item=item,
                           idle=bool(cur.get("idle")))
            if cur.get("retiring") and not old.get("retiring"):
                self._emit("file:pool.live.retiring", "pool.json", "OBSERVED", node=node, role=role, item=item)

    def _scan_queue(self):
        for sub, kind in (("queue", "file:queue.added"), ("queue/done", "file:queue.done"),
                          ("queue/failed", "file:queue.failed")):
            d = self._p(*sub.split("/"))
            try:
                names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
            except OSError:
                continue
            for name in names:
                stem = name[:-5]
                qid = stem.split("-", 1)[1] if "-" in stem else stem
                if self._qstatus.get(qid) == sub:
                    continue
                val = self._read_json(("q", sub, name), os.path.join(d, name))
                val = val if isinstance(val, dict) else self._json.get(("q", sub, name)) or {}
                self._qstatus[qid] = sub
                self._emit(kind, f"{sub}/{name}", "OBSERVED", role=val.get("role"), item=qid,
                           id=val.get("id", qid), parent=val.get("parent"), seq_name=stem.split("-", 1)[0])

    def _node_names(self):
        names = set()
        for base in (self._p("nodes"), self._p("nodes", "_retired")):
            try:
                for n in os.listdir(base):
                    if not n.startswith("_") and os.path.isdir(os.path.join(base, n)):
                        names.add(n)
            except OSError:
                pass
        return sorted(names)

    def _node_file(self, node, name):
        for base in (self._p("nodes", node), self._p("nodes", "_retired", node)):
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
        return None

    def _scan_node(self, node):
        run = self._json_if(node, "run.json")
        if isinstance(run, dict):
            cont = run.get("cont") or {}
            was = self._prev.get((node, "cont"))
            now_open = bool(cont.get("status")) and cont.get("status") not in ("none", "closed", "done")
            if now_open != was and (now_open or was is not None):
                self._emit("file:node.run.cont_open", f"nodes/{node}/run.json", "OBSERVED", node=node,
                           open=now_open, status=cont.get("status"), pending=len(run.get("pending") or []),
                           runs=run.get("runs"))
            self._prev[(node, "cont")] = now_open
        st = self._json_if(node, "state.json")
        if isinstance(st, dict):
            cons = st.get("consults") or {}
            peers = sorted(cons if isinstance(cons, dict) else [str(c) for c in cons])
            if peers != self._prev.get((node, "consults"), []):
                self._emit("file:node.state.consults", f"nodes/{node}/state.json", "OBSERVED", node=node,
                           peer=peers[0] if peers else None, peers=peers)
                self._prev[(node, "consults")] = peers
            done = st.get("done") or {}
            pd = self._prev.get((node, "done"), {})
            for item in sorted(done):
                v = done[item] if isinstance(done[item], dict) else {"status": done[item]}
                if v != pd.get(item):
                    self._emit("file:node.state.done", f"nodes/{node}/state.json", "OBSERVED", node=node, item=item,
                               status=v.get("status"), verified=v.get("verified"))
            self._prev[(node, "done")] = {k: (v if isinstance(v, dict) else {"status": v}) for k, v in done.items()}
        pi = self._json_if(node, "pi.json")
        if isinstance(pi, dict):
            vals = pi.get("pi") or {}
            old = self._prev.get((node, "pi"), {})
            for peer in sorted(vals):
                if vals[peer] != old.get(peer):
                    self._emit("file:node.pi", f"nodes/{node}/pi.json", "OBSERVED", node=node, peer=peer,
                               pi_permille=_permille(vals[peer]))
            self._prev[(node, "pi")] = dict(vals)
        p = self._node_file(node, "ga-budget.jsonl")
        if p:
            recs = self._read_lines(("budget", node), p)
            if recs:
                self._emit("file:node.budget.grow", f"nodes/{node}/ga-budget.jsonl", "OBSERVED", node=node,
                           records=len(recs), tokens=_last_num(recs, "tokens"),
                           cost_cli_microusd=_last_num(recs, "cost_cli_microusd"))

    @property
    def _prev(self):
        if not hasattr(self, "_prevd"):
            self._prevd = {}
        return self._prevd

    def _json_if(self, node, name):
        p = self._node_file(node, name)
        if not p:
            return None
        return self._read_json((node, name), p)

    def _scan_l0(self):
        files = [("pool/telemetry.jsonl", None)]
        for node in self._node_names():
            p = self._node_file(node, "telemetry.jsonl")
            if p:
                files.append((p, node))
        tdir = self._p("telemetry")
        try:
            files += [(os.path.join("telemetry", n), None) for n in sorted(os.listdir(tdir)) if n.endswith(".jsonl")]
        except OSError:
            pass
        for rel, node in files:
            path = rel if os.path.isabs(rel) else self._p(rel)
            key = ("l0", node or rel)
            for rec in self._read_lines(key, path):
                typ = rec.get("type") or rec.get("kind") or rec.get("event")
                if not isinstance(typ, str) or not KIND_RE.match(typ):
                    self.skipped_lines += 1
                    continue
                src = os.path.relpath(path, self.root).replace(os.sep, "/")
                data = {k: v for k, v in rec.items() if k not in ("type", "kind", "event", "node", "role", "item")}
                n = rec.get("node") or node or rec.get("from_session")
                if typ.startswith("peer.message") and rec.get("from_session"):
                    n = rec["from_session"]
                self._emit("l0:" + typ, src, "OBSERVED", node=n, role=rec.get("role"), item=rec.get("item"),
                           peer=rec.get("to_session") if typ.startswith("peer.message") else None, **data)

    def _scan_usage(self):
        u = self._read_json("usage", self._p("usage.json"))
        if isinstance(u, dict):
            self._emit("file:usage.snapshot", "usage.json", "OBSERVED",
                       tokens_total=_int(u.get("tokens_total")), cost_cli_microusd=_int(u.get("cost_cli_microusd")),
                       budget_microusd=_int(u.get("budget_microusd")))

    # -- derived moods ----------------------------------------------------------------
    def _derive(self):
        t = self._t
        self._times = [x for x in self._times if x > t - WINDOW_MS]
        snap = Snapshot.fold_copy(self.snapshot, self._new)
        msgs = sum(1 for e in self.events + self._new if e["kind"] == "l0:peer.message.sent"
                   and _ms(e["observed_at"]) > t - WINDOW_MS)
        tiles = snap.tiles.values()
        waiting = [x for x in tiles if x["shelf"] == "waiting"]
        live = [f for f in snap.figures.values() if f["state"] not in ("retired",)]
        silent = t - (self._last_signal if self._last_signal is not None else t)
        m = snap.meters
        budget = m.get("budget_use_permille")
        chain = snap.longest_wait_chain()
        mood = {
            "pace": len(self._times),
            "collaboration": msgs >= 3,
            "stall": silent >= STALL_MS and bool(waiting or live),
            "tension": (budget is not None and budget >= 800) or sum(1 for x in tiles if x["shelf"] == "failed") >= 2
            or chain >= 3,
            "all_done": not waiting and not [f for f in live if f["state"] != "idle"] and not any(
                x["shelf"] == "held" for x in tiles) and any(x["shelf"] == "done" for x in tiles),
        }
        for k in ("pace", "collaboration", "stall", "tension", "all_done"):
            if mood[k] != self._mood.get(k, None if k == "pace" else False) and (k != "pace" or self._times or self._mood):
                self._emit("derived:" + k, "", "CALCULATED", value=mood[k])
        self._mood = mood

    def full_snapshot(self) -> dict:
        return self.snapshot.to_dict(self.now_ms())


def _ms(s: str) -> int:
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).timestamp() * 1000)


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _permille(v):
    try:
        return max(0, min(1000, int(round(float(v) * 1000))))
    except (TypeError, ValueError):
        return 0


def _last_num(recs, key):
    for r in reversed(recs):
        if isinstance(r.get(key), int):
            return r[key]
    return None


def read(path, now_ms=_now_ms):
    """`gadir.read(path) -> Iterator[MonitorEvent]`: one poll of a .ga dir (everything is backfill)."""
    r = GaDirReader(path, now_ms)
    yield from r.poll()
