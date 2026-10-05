"""Scripted multi-node run for the desktop demo (CMD-IF2). Writes only inside its own temp dir.

    python3 replay.py [--duration 40] [--dir <path under the system temp dir>]

Prints the .ga path on the first line (flushed), then plays the run in real time using the file shapes the
read-only sidecar reader (backend/app/domains/run/gadir.py) understands: pool.json, queue/, nodes/<n>/*,
telemetry jsonl, usage.json. Nothing is ever written into a user's .ga.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

NODES = [("design", "design"), ("frontend", "frontend"), ("core-backend", "core-backend"),
         ("verifier", "verifier"), ("judge", "judge"), ("integration", "integration")]
ROLES = [r for _, r in NODES]
TOTAL_MS = 40_000


def _node(name):
    return {"node": name, "role": name}


def build_steps(total_ms: int = TOTAL_MS) -> list[dict]:
    """[{t: ms, ops: [...]}] sorted by t; ops are write_json / append_jsonl / move relative to the .ga root."""
    live: dict = {}
    state = {"round": 1}
    steps: list[dict] = []
    tel_pool: list = []

    def pool():
        return {"op": "write_json", "path": "pool.json", "content": {
            "schema": "ga-pool/1", "round": state["round"], "n": len(ROLES), "roles": ROLES, "attempts": 0,
            "live": {k: dict(v) for k, v in live.items()}}}

    def work(wid, role, parent=None):
        return {"op": "write_json", "path": f"queue/{wid[1:].zfill(3)}-{wid}.json",
                "content": {"schema": "work/1", "id": wid, "role": role, "parent": parent}}

    def qmove(wid, role, to, parent=None):
        return [{"op": "move", "path": f"queue/{wid[1:].zfill(3)}-{wid}.json", "to": f"queue/{to}/{wid[1:].zfill(3)}-{wid}.json"}]

    def claim(name, item, since):
        live[name] = {"role": name, "item": item, "since": since, "idle": False, "children": 0}
        tel_pool.append({"type": "node.started", **_node(name), "item": item})
        return [pool(), {"op": "append_jsonl", "path": "pool/telemetry.jsonl", "content": [tel_pool[-1]]}]

    def tel(name, *recs):
        return {"op": "append_jsonl", "path": f"nodes/{name}/telemetry.jsonl", "content": list(recs)}

    def turn(name, tokens):
        return tel(name, {"type": "run.end", "node": name, "run_dur_ms": 4000, "tokens": tokens})

    def msg(a, b, mid, reply=None):
        r = {"type": "peer.message.sent", "from_session": a, "to_session": b, "msg_id": mid, "bytes": 120, "tokens_est": 30}
        if reply:
            r["in_reply_to"] = reply
        return tel(a, r)

    def budget(name, tokens, cost):
        return {"op": "append_jsonl", "path": f"nodes/{name}/ga-budget.jsonl", "content": [{"tokens": tokens, "cost_cli_microusd": cost}]}

    def usage(tok, cost):
        return {"op": "write_json", "path": "usage.json", "content": {"schema": "ga-usage/1", "tokens_total": tok, "cost_cli_microusd": cost, "budget_microusd": 2_000_000}}

    def consults(name, peers):
        return {"op": "write_json", "path": f"nodes/{name}/state.json", "content": {"consults": peers, "done": {}}}

    def done(name, item, status, verified):
        return {"op": "write_json", "path": f"nodes/{name}/state.json", "content": {"consults": [], "done": {item: {"status": status, "verified": verified}}}}

    def pi(name, vals):
        return {"op": "write_json", "path": f"nodes/{name}/pi.json", "content": {"pi": vals}}

    def retire(name, outcome="done"):
        live.pop(name, None)
        return [pool(), {"op": "append_jsonl", "path": "pool/telemetry.jsonl", "content": [{"type": "node.retired", **_node(name), "outcome": outcome}]}]

    def at(sec, *ops):
        flat = []
        for o in ops:
            flat.extend(o if isinstance(o, list) else [o])
        steps.append({"t": int(sec * 1000), "ops": flat})

    at(0, pool(), work("w1", "design"), work("w2", "frontend"), work("w3", "core-backend"), work("w4", "verifier"))
    at(2, claim("design", "w1", 1), budget("design", 800, 20_000), usage(800, 20_000))
    at(5, claim("frontend", "w2", 1), claim("core-backend", "w3", 1), turn("design", 1500), budget("design", 2300, 60_000))
    at(8, msg("design", "frontend", "m1"), msg("design", "core-backend", "m2"), pi("design", {"frontend": 0.8, "core-backend": 0.6}),
       usage(4500, 120_000))
    at(11, consults("frontend", ["core-backend"]), msg("frontend", "core-backend", "m3"), turn("core-backend", 2100),
       budget("core-backend", 2100, 70_000))
    at(14, msg("core-backend", "frontend", "m4", "m3"), consults("frontend", []), pi("frontend", {"core-backend": 0.7}),
       done("design", "w1", "done", True), qmove("w1", "design", "done"), usage(9000, 260_000))
    at(17, claim("verifier", "w4", 1), turn("frontend", 2600), budget("frontend", 2600, 85_000))
    at(20, msg("verifier", "frontend", "m5"), msg("verifier", "core-backend", "m6"), pi("verifier", {"frontend": 0.5, "core-backend": 0.5}),
       usage(14_000, 400_000))
    # red judge: the judge fails the frontend's work, which is re-queued as a fix
    at(22, claim("judge", "w5", 1), work("w5", "judge"), turn("verifier", 1800), msg("judge", "frontend", "m7"))
    at(25, done("judge", "w5", "failed", False), qmove("w5", "judge", "failed"),
       tel("judge", {"type": "work.failed", "item": "w5", "reason": "tests red"}),
       tel("frontend", {"type": "work.accepted", "item": "w2", "id": "w6", "reason": "fix"}), work("w6", "frontend", "w2"),
       usage(19_000, 560_000))
    at(28, msg("judge", "frontend", "m8", "m7"), turn("frontend", 2400), budget("frontend", 5000, 160_000), work("w7", "judge"))
    # green judge
    at(31, qmove("w3", "core-backend", "done"), qmove("w6", "frontend", "done", "w2"), qmove("w2", "frontend", "done"),
       turn("judge", 1200), done("judge", "w7", "done", True), qmove("w7", "judge", "done"), usage(24_000, 700_000))
    at(33, claim("integration", "w8", 1), work("w8", "integration"), retire("design"), retire("core-backend"))
    at(35, msg("integration", "frontend", "m9"), msg("integration", "verifier", "m10"), pi("integration", {"frontend": 0.9, "verifier": 0.7}),
       qmove("w4", "verifier", "done"), turn("integration", 1600), usage(27_500, 780_000))
    at(37, done("integration", "w8", "done", True), qmove("w8", "integration", "done"), retire("frontend"), retire("verifier"),
       retire("judge"), usage(29_000, 820_000))
    at(39, retire("integration"))
    scale = total_ms / TOTAL_MS
    for s in steps:
        s["t"] = int(s["t"] * scale)
    return sorted(steps, key=lambda s: s["t"])


def apply_op(root: str, op: dict) -> None:
    """Applies one op; refuses any path that resolves outside `root`."""
    root = os.path.realpath(root)

    def inside(rel):
        if rel.startswith("/") or "\\" in rel:
            raise ValueError(f"absolute or backslash path refused: {rel}")
        p = os.path.realpath(os.path.join(root, *rel.split("/")))
        if p != root and not p.startswith(root + os.sep):
            raise ValueError(f"path escapes the replay dir: {rel}")
        return p

    p = inside(op["path"])
    kind = op["op"]
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if kind == "write_json":
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(op["content"], f)
        os.replace(p + ".tmp", p)
    elif kind == "append_jsonl":
        with open(p, "ab") as f:
            for rec in op["content"]:
                f.write(json.dumps(rec).encode() + b"\n")
    elif kind == "move":
        dst = inside(op["to"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(p, dst)
    else:
        raise ValueError(kind)


def make_dir(requested: str | None = None) -> str:
    """A fresh .ga dir under the system temp dir (a requested dir must already be inside it)."""
    tmp = os.path.realpath(tempfile.gettempdir())
    if requested:
        base = os.path.realpath(requested)
        if not base.startswith(tmp + os.sep):
            raise ValueError(f"--dir must be inside {tmp}")
        os.makedirs(base, exist_ok=True)
    else:
        base = tempfile.mkdtemp(prefix="ga-replay-", dir=tmp)
    ga = os.path.join(base, ".ga")
    os.makedirs(ga, exist_ok=True)
    return ga


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=TOTAL_MS / 1000)
    ap.add_argument("--dir")
    a = ap.parse_args(argv)
    ga = make_dir(a.dir)
    print(ga, flush=True)
    start = time.monotonic()
    for step in build_steps(int(a.duration * 1000)):
        delay = start + step["t"] / 1000 - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        for op in step["ops"]:
            apply_op(ga, op)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
