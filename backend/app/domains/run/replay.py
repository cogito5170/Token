"""Build a fixture .ga tree by replaying a scripted pool (fixtures/monitor/script.json) into a dir. Test/fixture tool."""
from __future__ import annotations

import json
import os
import shutil

BASE_MS = 1767225600000  # 2026-01-01T00:00:00Z


def _apply(root, op):
    p = os.path.join(root, *op["path"].split("/"))
    k = op["op"]
    if k == "write_json":
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(op["content"], f)
        os.replace(p + ".tmp", p)
    elif k == "append_jsonl":
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "ab") as f:
            for rec in op["content"]:
                f.write(json.dumps(rec).encode() + b"\n")
    elif k == "append_raw":
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "ab") as f:
            f.write(op["content"].encode())
    elif k == "move":
        dst = os.path.join(root, *op["to"].split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(p, dst)
    else:
        raise ValueError(k)


def replay(script, root, reader_factory):
    """Apply each step then poll with the clock at BASE_MS + t. Returns (reader, events)."""
    clock = [BASE_MS]
    rd = reader_factory(root, lambda: clock[0])
    out = []
    for step in script["steps"]:
        clock[0] = BASE_MS + step["t"]
        for op in step.get("ops", []):
            _apply(root, op)
        out.extend(rd.poll())
    return rd, out
