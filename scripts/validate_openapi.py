#!/usr/bin/env python3
"""Validate docs/api/openapi.yaml (CMD-GC0 D1).

1. The document against the official OpenAPI 3.1 structural schema (vendored: scripts/vendor/oas-3.1-schema.yaml,
   from OAI/OpenAPI-Specification branch v3.1-dev @ 551e3df1, src/schemas/validation/schema.yaml, Apache-2.0).
2. Every components schema against the JSON Schema 2020-12 meta-schema.
3. Every local $ref resolves; operationIds are unique; every {param} in a path is declared as a path parameter.

Needs PyYAML and jsonschema (dev tools, not runtime deps). Exit 0 = valid.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "api" / "openapi.yaml"
OAS = Path(__file__).resolve().parent / "vendor" / "oas-3.1-schema.yaml"
METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}


def walk(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}/{k}")
        if "$ref" in node:
            yield path, node["$ref"]
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}/{i}")


def resolve(doc, ref):
    if not ref.startswith("#/"):
        return True
    cur = doc
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def problems(doc) -> list[str]:
    out: list[str] = []
    meta = yaml.safe_load(OAS.read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(meta)
    for e in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
        out.append(f"oas3.1: /{'/'.join(map(str, e.path))}: {e.message[:200]}")
    for name, s in (doc.get("components", {}).get("schemas", {}) or {}).items():
        try:
            jsonschema.Draft202012Validator.check_schema(s)
        except jsonschema.SchemaError as e:
            out.append(f"schema {name}: {e.message[:200]}")
    for where, ref in walk(doc):
        if not resolve(doc, ref):
            out.append(f"unresolved $ref {ref} at {where}")
    seen: dict[str, str] = {}
    for p, item in (doc.get("paths") or {}).items():
        declared = set()
        for prm in item.get("parameters", []):
            if "$ref" in prm and resolve(doc, prm["$ref"]):
                prm = doc["components"]["parameters"][prm["$ref"].rsplit("/", 1)[1]]
            if prm.get("in") == "path":
                declared.add(prm["name"])
        for m, op in item.items():
            if m not in METHODS:
                continue
            oid = op.get("operationId")
            if oid in seen:
                out.append(f"duplicate operationId {oid} ({seen[oid]} and {m} {p})")
            seen[oid] = f"{m} {p}"
            names = set(declared)
            for prm in op.get("parameters", []):
                if prm.get("in") == "path":
                    names.add(prm["name"])
            for need in re.findall(r"{(\w+)}", p):
                if need not in names:
                    out.append(f"{m} {p}: path parameter {need} not declared")
    return out


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else SPEC
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = problems(doc)
    for line in out:
        print(line)
    n = sum(1 for i in doc.get("paths", {}).values() for m in i if m in METHODS)
    print(f"openapi: {len(doc.get('paths', {}))} paths, {n} operations, {len(out)} problems")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
