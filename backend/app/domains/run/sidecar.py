"""Read-only monitor sidecar: `python3 -m app.domains.run.sidecar --ga-dir PATH` (ADR-0008). GET only, 127.0.0.1, token."""
from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .gadir import READER_VERSION, GaDirReader, iso

NIL_WS = "00000000-0000-0000-0000-000000000000"
HEARTBEAT_S = 15.0


class Monitor:
    """Polls one .ga dir in a thread and keeps the event log (the recording of this session)."""

    def __init__(self, ga_dir, poll_ms=500, record_dir=None):
        self.ga_dir = os.path.abspath(ga_dir)
        self.reader = GaDirReader(self.ga_dir)
        self.source_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "file://" + self.ga_dir))
        self.recording_id = str(uuid.uuid4())
        self.started_at = iso(self.reader.now_ms())
        self.poll_s = poll_ms / 1000
        self.cond = threading.Condition()
        self.stop = False
        self.record_path = os.path.join(record_dir, self.recording_id + ".jsonl") if record_dir else None
        self.poll_once()

    def poll_once(self):
        with self.cond:
            new = self.reader.poll()
            if new and self.record_path:
                with open(self.record_path, "a", encoding="utf-8") as f:  # outside .ga, by construction of --record-dir
                    for e in new:
                        f.write(json.dumps(e, separators=(",", ":"), sort_keys=True) + "\n")
            if new:
                self.cond.notify_all()

    def run(self):
        while not self.stop:
            time.sleep(self.poll_s)
            self.poll_once()

    def events_after(self, seq):
        with self.cond:
            return [e for e in self.reader.events if e["seq"] > seq]


def make_handler(mon: Monitor, token: str, heartbeat_s=HEARTBEAT_S):
    base = "/v1/workspaces/"

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body=b"", ctype="application/json", extra=()):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, separators=(",", ":")).encode())

        def _method_not_allowed(self):
            self._send(405, b'{"error":"read_only"}', extra=[("Allow", "GET")])

        do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _method_not_allowed

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            auth = self.headers.get("Authorization", "")
            given = auth[7:] if auth.startswith("Bearer ") else (q.get("token") or [""])[0]
            if not given or not hmac.compare_digest(given.encode(), token.encode()):
                return self._json(401, {"error": "token_required"})
            parts = [p for p in u.path.split("/") if p]
            # v1 workspaces {ws} monitor sources [{source} [snapshot|events|recordings [{rec}]]]
            if len(parts) < 5 or parts[:2] != ["v1", "workspaces"] or parts[3] != "monitor" or parts[4] != "sources":
                return self._json(404, {"error": "not_found"})
            rest = parts[5:]
            if not rest:
                return self._json(200, [{"id": mon.source_id, "label": os.path.basename(mon.ga_dir) or "ga",
                                         "path": mon.ga_dir, "reachable": os.path.isdir(mon.ga_dir)}])
            if rest[0] != mon.source_id or len(rest) < 2:
                return self._json(404, {"error": "not_found"})
            what = rest[1]
            if what == "snapshot" and len(rest) == 2:
                with mon.cond:
                    return self._json(200, mon.reader.full_snapshot())
            if what == "events" and len(rest) == 2:
                return self._sse(q)
            if what == "recordings" and len(rest) == 2:
                with mon.cond:
                    n = len(mon.reader.events)
                return self._json(200, [{"id": mon.recording_id, "started_at": mon.started_at, "ended_at": None,
                                         "events": n, "reader_version": READER_VERSION}])
            if what == "recordings" and len(rest) == 3 and rest[2] == mon.recording_id:
                lines = "".join(json.dumps(e, separators=(",", ":"), sort_keys=True) + "\n"
                                for e in mon.events_after(0))
                return self._send(200, lines.encode(), "application/x-ndjson")
            return self._json(404, {"error": "not_found"})

        def _sse(self, q):
            last = self.headers.get("Last-Event-ID") or (q.get("last_event_id") or ["0"])[0]
            seq = int(last) if str(last).isdigit() else 0
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                last_beat = time.monotonic()
                while not mon.stop:
                    evs = mon.events_after(seq)
                    for e in evs:
                        self.wfile.write(f"id: {e['seq']}\nevent: {e['kind']}\ndata: "
                                         f"{json.dumps(e, separators=(',', ':'))}\n\n".encode())
                        seq = e["seq"]
                    if evs:
                        self.wfile.flush()
                        last_beat = time.monotonic()
                    elif time.monotonic() - last_beat >= heartbeat_s:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                        last_beat = time.monotonic()
                    with mon.cond:
                        mon.cond.wait(timeout=min(0.5, heartbeat_s))
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    return H


def serve(ga_dir, token, host="127.0.0.1", port=0, poll_ms=None, record_dir=None, heartbeat_s=HEARTBEAT_S):
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("sidecar binds to loopback only")
    if not token:
        raise ValueError("token required")
    poll = poll_ms if poll_ms is not None else int(os.environ.get("GC_MONITOR_POLL_MS", "500"))
    mon = Monitor(ga_dir, poll, record_dir)
    srv = ThreadingHTTPServer((host, port), make_handler(mon, token, heartbeat_s))
    srv.daemon_threads = True
    threading.Thread(target=mon.run, daemon=True).start()
    return srv, mon


def main(argv=None):
    ap = argparse.ArgumentParser(prog="app.domains.run.sidecar")
    ap.add_argument("--ga-dir", required=True)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--record-dir", default=None)
    a = ap.parse_args(argv)
    # token comes from the env (one-time, set by the desktop shell); else a fresh one is generated and announced once
    token = os.environ.get("GC_SIDECAR_TOKEN") or secrets.token_urlsafe(24)
    srv, mon = serve(a.ga_dir, token, port=a.port, record_dir=a.record_dir)
    print(json.dumps({"ready": True, "host": "127.0.0.1", "port": srv.server_address[1], "source": mon.source_id,
                      "ws": NIL_WS, "token": token if not os.environ.get("GC_SIDECAR_TOKEN") else None}), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        mon.stop = True


if __name__ == "__main__":
    main()
