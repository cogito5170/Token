#!/usr/bin/env python3
"""Deterministic consistency check of the ga Console contract docs (CMD-GC0 S6). Standard library only.

    python3 scripts/check_docs.py [--root DIR]

Checks (each problem is one line; exit 1 if any):
  domains     the 15 domains of spec section 8 are the `## \\`id\\`` sections of docs/domain-model.md, each is a row of
              the domain table in docs/architecture.md and has a `backend/app/domains/<id>/**` row in docs/ownership.md
  tables      every CREATE TABLE in docs/schema.sql is owned by exactly one domain (owned_tables lines), agrees with
              its `-- owner:` comment, and every owned table exists; package OWNED_TABLES agree when present
  openapi     every path in docs/api/openapi.yaml has exactly one x-domain naming a known domain
  screens     docs/visualization.md has the 9 screens of spec section 3, each with >= 1 `api:` line naming an
              existing METHOD + path of openapi.yaml
  advisor     docs/consulting.md has rules R1..R7, each with a detector, a savings formula and a fixture file that
              exists and holds {rule, calls, expect{fires, evidence_call_ids, savings_p50_microusd}}
  ownership   docs/ownership.md rows parse, roles are known, every repo file matches exactly one pattern
  work        docs/roadmap.md work items: ids, roles, depends acyclic, files inside an ownership row of the same role
              (contract rows only for kind=contract, never baseline rows), no shared files between independent items,
              done_when is an argv list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DOMAINS = ("identity", "workspace", "source", "ingestion", "usage", "quota", "estimation", "advisor",
           "simulation", "profile", "report", "notification", "audit", "integration", "run")
SCREENS = ("overview", "token_mix", "call_size", "node_timeline", "task_flow", "peer_network", "verdicts",
           "config_compare", "budget_burn")
RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
ROLES = ("frontend", "core-backend", "ingestion-analytics", "consulting", "infra")
OWNER_ROLES = ROLES + ("baseline",)
METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".next", ".ga"}
ITEM_ID = re.compile(r"^CMD-[A-Z]+\d+$")


class Check:
    def __init__(self, root: Path):
        self.root = root
        self.problems: list[str] = []

    def bad(self, area: str, msg: str) -> None:
        self.problems.append(f"{area}: {msg}")

    def read(self, rel: str) -> str:
        p = self.root / rel
        if not p.is_file():
            self.bad("files", f"missing {rel}")
            return ""
        return p.read_text(encoding="utf-8")


# ----------------------------------------------------------------------------------------------- parsing helpers
def domain_sections(text: str) -> dict[str, str]:
    return {d: body for d, body in re.findall(r"^## `(\w+)` — .+?$(.*?)(?=^## `|\Z)", text, re.M | re.S)}


def owned_tables(body: str) -> list[str] | None:
    m = re.search(r"^- owned_tables: (.*)$", body, re.M)
    return re.findall(r"`(\w+)`", m.group(1)) if m else None


def schema_tables(sql: str) -> dict[str, str | None]:
    """table -> owner from the `-- owner:` comment directly above it (None if missing)."""
    out: dict[str, str | None] = {}
    owner = None
    for line in sql.splitlines():
        m = re.match(r"\s*--\s*owner:\s*(\w+)\s*$", line)
        if m:
            owner = m.group(1)
            continue
        m = re.match(r"\s*CREATE TABLE (?:IF NOT EXISTS )?(\w+)", line, re.I)
        if m:
            out[m.group(1)] = owner
            owner = None
    return out


def openapi_paths(text: str) -> dict[str, dict]:
    """Line-based reader for docs/api/openapi.yaml (2-space indent, as written): path -> {domains, methods}."""
    out: dict[str, dict] = {}
    in_paths = False
    cur = None
    for line in text.splitlines():
        if re.match(r"^\S", line):
            in_paths = line.rstrip() == "paths:"
            cur = None
            continue
        if not in_paths:
            continue
        m = re.match(r"^  (/\S*):\s*$", line)
        if m:
            cur = out.setdefault(m.group(1), {"domains": [], "methods": set()})
            continue
        if cur is None:
            continue
        m = re.match(r"^    x-domain:\s*(\S+)\s*$", line)
        if m:
            cur["domains"].append(m.group(1))
            continue
        m = re.match(r"^    (\w+):", line)
        if m and m.group(1) in METHODS:
            cur["methods"].add(m.group(1))
    return out


def glob_re(pattern: str) -> re.Pattern:
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def sample(pattern: str) -> str:
    """A concrete path a pattern stands for (used to test containment and overlap of patterns)."""
    return pattern.replace("**", "zz/sample.txt").replace("*", "sample")


def ownership_rows(text: str) -> list[tuple[str, str, bool]]:
    rows = []
    for m in re.finditer(r"^\|\s*`([^`]+)`\s*\|\s*([\w-]+)\s*\|\s*(yes|no)\s*\|\s*$", text, re.M):
        rows.append((m.group(1), m.group(2), m.group(3) == "yes"))
    return rows


def work_items(text: str):
    m = re.search(r"^```work-items\s*\n(.*?)^```", text, re.M | re.S)
    if not m:
        return None
    return json.loads(m.group(1))


# ----------------------------------------------------------------------------------------------- checks
def check_domains(c: Check, sections: dict[str, str]) -> None:
    if tuple(sections) != DOMAINS:
        missing = [d for d in DOMAINS if d not in sections]
        extra = [d for d in sections if d not in DOMAINS]
        c.bad("domains", f"domain-model.md sections differ from spec section 8 (missing {missing}, extra {extra})")
    arch = c.read("docs/architecture.md")
    m = re.search(r"^## 2\. .*?$(.*?)(?=^## |\Z)", arch, re.M | re.S)  # the domain section only
    rows = set(re.findall(r"^\|\s*`(\w+)`\s*\|", m.group(1) if m else "", re.M))
    own = c.read("docs/ownership.md")
    for d in DOMAINS:
        if d not in rows:
            c.bad("domains", f"{d} has no row in the architecture.md domain table")
        if f"`backend/app/domains/{d}/**`" not in own:
            c.bad("domains", f"{d} has no backend/app/domains/{d}/** row in ownership.md")
    for d in sorted(rows - set(DOMAINS)):
        c.bad("domains", f"architecture.md domain table names unknown domain {d}")


def check_tables(c: Check, sections: dict[str, str]) -> None:
    sql = schema_tables(c.read("docs/schema.sql"))
    owners: dict[str, list[str]] = {}
    for d, body in sections.items():
        tables = owned_tables(body)
        if tables is None:
            c.bad("tables", f"{d} has no owned_tables line")
            continue
        for t in tables:
            owners.setdefault(t, []).append(d)
            if t not in sql:
                c.bad("tables", f"{d} owns {t}, which is not in schema.sql")
        init = c.root / "backend" / "app" / "domains" / d / "__init__.py"
        if init.is_file():
            m = re.search(r"^OWNED_TABLES = \((.*?)\)", init.read_text(encoding="utf-8"), re.M | re.S)
            got = re.findall(r"['\"](\w+)['\"]", m.group(1)) if m else None
            if got != tables:
                c.bad("tables", f"backend/app/domains/{d}/__init__.py OWNED_TABLES {got} != domain-model.md {tables}")
    for t, comment_owner in sql.items():
        who = owners.get(t, [])
        if len(who) != 1:
            c.bad("tables", f"table {t} has {len(who)} owners {who} (must be exactly one)")
        elif comment_owner != who[0]:
            c.bad("tables", f"table {t}: schema.sql says owner {comment_owner}, domain-model.md says {who[0]}")


def check_openapi(c: Check) -> dict[str, dict]:
    paths = openapi_paths(c.read("docs/api/openapi.yaml"))
    if not paths:
        c.bad("openapi", "no paths found")
    for p, info in paths.items():
        if len(info["domains"]) != 1:
            c.bad("openapi", f"{p} has {len(info['domains'])} x-domain entries (must be exactly one)")
        elif info["domains"][0] not in DOMAINS:
            c.bad("openapi", f"{p} x-domain {info['domains'][0]} is not a domain")
        if not info["methods"]:
            c.bad("openapi", f"{p} has no operation")
    return paths


def check_screens(c: Check, paths: dict[str, dict]) -> None:
    text = c.read("docs/visualization.md")
    blocks = dict(re.findall(r"^## screen: (\w+) — .+?$(.*?)(?=^## |\Z)", text, re.M | re.S))
    if tuple(blocks) != SCREENS:
        c.bad("screens", f"visualization.md screens {list(blocks)} != spec section 3 {list(SCREENS)}")
    for s, body in blocks.items():
        apis = re.findall(r"^- api: `(\w+) ([^`]+)`", body, re.M)
        if not apis:
            c.bad("screens", f"{s} names no api")
        for method, path in apis:
            info = paths.get(path)
            if info is None:
                c.bad("screens", f"{s} reads {method} {path}, which is not in openapi.yaml")
            elif method.lower() not in info["methods"]:
                c.bad("screens", f"{s} reads {method} {path}, but openapi.yaml has only {sorted(info['methods'])}")
        for key in ("question", "chart", "units", "provenance"):
            if not re.search(rf"^- {key}: \S", body, re.M):
                c.bad("screens", f"{s} has no {key} line")


def check_advisor(c: Check) -> None:
    text = c.read("docs/consulting.md")
    blocks = dict(re.findall(r"^### (R\d+) \w+.*?$(.*?)(?=^### |^## |\Z)", text, re.M | re.S))
    for r in RULES:
        body = blocks.get(r)
        if body is None:
            c.bad("advisor", f"rule {r} missing from consulting.md")
            continue
        if not re.search(r"^- detector: `advisor\.rules\.\w+\.detect`", body, re.M):
            c.bad("advisor", f"{r} has no detector")
        if not re.search(r"^- savings: .*\bp50\b", body, re.M):
            c.bad("advisor", f"{r} has no savings formula (needs a p50 expression)")
        m = re.search(r"^- fixture: `([^`]+)`", body, re.M)
        if not m:
            c.bad("advisor", f"{r} has no fixture")
            continue
        fx = c.root / m.group(1)
        if not fx.is_file():
            c.bad("advisor", f"{r} fixture {m.group(1)} does not exist")
            continue
        try:
            data = json.loads(fx.read_text(encoding="utf-8"))
            e = data["expect"]
            ok = (data["rule"] == r and isinstance(data["calls"], list) and data["calls"]
                  and isinstance(e["fires"], bool) and isinstance(e["evidence_call_ids"], list)
                  and isinstance(e["savings_p50_microusd"], int))
            if not ok:
                c.bad("advisor", f"{r} fixture {m.group(1)} has the wrong shape")
            elif e["fires"] and not (e["savings_p10_microusd"] <= e["savings_p50_microusd"] <= e["savings_p90_microusd"]):
                c.bad("advisor", f"{r} fixture savings are not ordered p10 <= p50 <= p90")
        except (ValueError, KeyError, TypeError) as err:
            c.bad("advisor", f"{r} fixture {m.group(1)} unreadable: {err!r}")
    for r in sorted(set(blocks) - set(RULES)):
        c.bad("advisor", f"unknown rule {r} in consulting.md")


def repo_files(root: Path) -> list[str]:
    out = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or not p.is_file():
            continue
        out.append(rel.as_posix())
    return out


def check_ownership(c: Check) -> list[tuple[str, str, bool]]:
    rows = ownership_rows(c.read("docs/ownership.md"))
    if not rows:
        c.bad("ownership", "no rows parsed")
    seen = set()
    for pat, role, _ in rows:
        if role not in OWNER_ROLES:
            c.bad("ownership", f"{pat}: unknown role {role}")
        if pat in seen:
            c.bad("ownership", f"{pat} listed twice")
        seen.add(pat)
    compiled = [(glob_re(p), p) for p, _, _ in rows]
    for f in repo_files(c.root):
        hits = [p for rx, p in compiled if rx.match(f)]
        if len(hits) != 1:
            c.bad("ownership", f"{f} matches {len(hits)} patterns {hits} (must be exactly one)")
    return rows


def check_work(c: Check, rows: list[tuple[str, str, bool]]) -> None:
    try:
        items = work_items(c.read("docs/roadmap.md"))
    except ValueError as e:
        c.bad("work", f"work-items block is not JSON: {e}")
        return
    if not items:
        c.bad("work", "no work-items block")
        return
    ids = [i.get("id") for i in items]
    byid = {i.get("id"): i for i in items}
    if len(set(ids)) != len(ids):
        c.bad("work", "duplicate work item ids")
    compiled = [(glob_re(p), p, role, contract) for p, role, contract in rows]
    for it in items:
        iid = it.get("id")
        if not isinstance(iid, str) or not ITEM_ID.match(iid):
            c.bad("work", f"bad id {iid!r}")
        if it.get("role") not in ROLES:
            c.bad("work", f"{iid}: unknown role {it.get('role')!r}")
        if it.get("kind") not in ("feature", "contract"):
            c.bad("work", f"{iid}: kind must be feature or contract")
        if not str(it.get("goal", "")).strip():
            c.bad("work", f"{iid}: empty goal")
        dw = it.get("done_when")
        if not (isinstance(dw, list) and dw and all(isinstance(x, str) for x in dw)):
            c.bad("work", f"{iid}: done_when must be a non-empty argv list")
        for dep in it.get("depends_on", []):
            if dep not in byid:
                c.bad("work", f"{iid}: depends on unknown {dep}")
        files = it.get("files") or []
        if not files:
            c.bad("work", f"{iid}: owns no files")
        for f in files:
            s = sample(f)
            hits = [(p, role, contract) for rx, p, role, contract in compiled if rx.match(s)]
            if len(hits) != 1:
                c.bad("work", f"{iid}: file {f} is not inside exactly one ownership row ({[h[0] for h in hits]})")
                continue
            p, role, contract = hits[0]
            if role != it.get("role"):
                c.bad("work", f"{iid}: file {f} belongs to {role} ({p}), item role is {it.get('role')}")
            if contract and it.get("kind") != "contract":
                c.bad("work", f"{iid}: file {f} is a contract file ({p}); only a contract item may own it")
    # acyclic + transitive deps
    deps: dict[str, set[str]] = {}

    def closure(i: str, stack: tuple = ()) -> set[str]:
        if i in deps:
            return deps[i]
        if i in stack:
            c.bad("work", f"dependency cycle through {i}")
            return set()
        out: set[str] = set()
        for d in byid.get(i, {}).get("depends_on", []):
            if d in byid:
                out |= {d} | closure(d, stack + (i,))
        deps[i] = out
        return out

    for i in byid:
        closure(i)
    # no shared files between items that are not ordered by dependency
    for a in items:
        for b in items:
            if a["id"] >= b["id"] or a["id"] in deps.get(b["id"], set()) or b["id"] in deps.get(a["id"], set()):
                continue
            for fa in a.get("files", []):
                for fb in b.get("files", []):
                    if glob_re(fa).match(sample(fb)) or glob_re(fb).match(sample(fa)):
                        c.bad("work", f"{a['id']} and {b['id']} both own {fa} / {fb} and neither depends on the other")


def run(root: Path) -> list[str]:
    c = Check(root)
    sections = domain_sections(c.read("docs/domain-model.md"))
    check_domains(c, sections)
    check_tables(c, sections)
    paths = check_openapi(c)
    check_screens(c, paths)
    check_advisor(c)
    rows = check_ownership(c)
    check_work(c, rows)
    return c.problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    problems = run(Path(args.root))
    for p in problems:
        print(p)
    print(f"check_docs: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
