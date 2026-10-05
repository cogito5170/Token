"""Secret-pattern grep over a tree. `python3 infra/secret_scan.py [root]` exits 1 on a hit (prints path:line:rule, never the value)."""
import re
import subprocess
import sys
from pathlib import Path

# Patterns are assembled from parts so this file does not match itself.
RULES = {
    "private-key-block": re.compile("-----BEGIN [A-Z ]*PRIVATE" + " KEY-----"),
    "aws-access-key": re.compile(r"\bAKIA" + r"[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_" + r"[A-Za-z0-9]{30,}"),
    "anthropic-or-openai-key": re.compile(r"\bsk-(?:ant-)?" + r"[A-Za-z0-9_-]{20,}"),
    "slack-token": re.compile(r"\bxox[abprs]-" + r"[A-Za-z0-9-]{10,}"),
    "secret-assignment": re.compile(
        r"""(?i)\b(?:password|passwd|secret|api[_-]?key|token)\b["']?\s*[:=]\s*["'][A-Za-z0-9/+_\-]{16,}["']"""),
}
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".next", ".ga"}
MAX_BYTES = 2_000_000


def _files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (SKIP_DIRS & set(p.relative_to(root).parts)) and p.stat().st_size <= MAX_BYTES:
            yield p


def scan(root) -> list[tuple[str, int, str]]:
    root = Path(root)
    hits = []
    for p in _files(root):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for name, rx in RULES.items():
                if rx.search(line):
                    hits.append((str(p.relative_to(root)), n, name))
    return hits


def main(argv) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    hits = scan(root)
    for path, n, rule in hits:
        print(f"{path}:{n}: {rule}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
