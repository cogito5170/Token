#!/usr/bin/env python3
"""Export docs/roadmap.md work items as work/1 JSON lines for `ga work add -` (CMD-GC0 S5). Standard library only.

    python3 scripts/export_work.py [--id CMD-GC12 ...] | while read -r l; do echo "$l" | ga work add -; done

work/1 keys (ga/net/pool.py ITEM_KEYS): id, role, goal, check (argv), uses. The richer fields of roadmap.md
(files, depends_on, interfaces, done_when_text) are folded into `goal` so a node sees them; `check` is done_when.
Items are emitted in dependency order.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_docs import work_items  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class WorkError(Exception):
    pass


def ordered(items: list[dict]) -> list[dict]:
    byid = {i["id"]: i for i in items}
    for it in items:
        for d in it.get("depends_on", []):
            if d not in byid:
                raise WorkError(f"{it['id']}: depends_on names unknown item {d!r}")
    out, done = [], set()

    def visit(i: str) -> None:
        if i in done:
            return
        done.add(i)
        for d in byid[i].get("depends_on", []):
            visit(d)
        out.append(byid[i])

    for i in byid:
        visit(i)
    return out


def to_work(it: dict) -> dict:
    goal = (f"{it['goal']}\nOwns only: {', '.join(it['files'])}.\n"
            f"Depends on: {', '.join(it.get('depends_on', [])) or 'nothing'}; interfaces: {'; '.join(it.get('interfaces', []))}.\n"
            f"Done when: {it.get('done_when_text', '')} (runner: {it.get('runner', 'unittest')}).\n"
            f"Kind: {it['kind']}. Contracts (docs/ownership.md contract=yes) change only in a contract item.")
    return {"schema": "work/1", "id": it["id"], "role": it["role"], "goal": goal,
            "uses": ["docs/architecture.md", "docs/ownership.md"], "check": it["done_when"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", action="append", default=[])
    args = ap.parse_args(argv)
    try:
        items = ordered(work_items((ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")))
    except WorkError as e:
        print(f"export_work: {e}", file=sys.stderr)
        return 2
    for it in items:
        if not args.id or it["id"] in args.id:
            print(json.dumps(to_work(it), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
