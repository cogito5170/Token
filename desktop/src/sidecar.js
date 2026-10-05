// Spawns the read-only Python sidecar (CMD-RN1) on 127.0.0.1 with a one-time token.
// The token lives only in memory here and in the child's environment; it is never logged or written to disk.
const { spawn } = require("node:child_process");
const crypto = require("node:crypto");
const path = require("node:path");

function startSidecar({ gaDir, python, backendDir, guard = path.join(__dirname, "..", "sidecar", "guard.py"), readyTimeoutMs = 20000 }) {
  const token = crypto.randomBytes(24).toString("base64url");
  // No --record-dir: the shell never writes anything, and the sidecar has no reason to either.
  const args = [guard, "--ga-dir", gaDir, "--port", "0"];
  const child = spawn(python, args, {
    env: { ...process.env, PYTHONPATH: backendDir, PYTHONDONTWRITEBYTECODE: "1", GC_SIDECAR_TOKEN: token },
    stdio: ["pipe", "pipe", "ignore"], // stdin pipe = lifeline: its closure kills the sidecar
    cwd: path.dirname(guard),
  });
  const ready = new Promise((resolve, reject) => {
    let buf = "";
    const timer = setTimeout(() => reject(new Error("sidecar did not become ready")), readyTimeoutMs);
    child.stdout.on("data", (d) => {
      buf += d;
      const nl = buf.indexOf("\n");
      if (nl < 0) return;
      clearTimeout(timer);
      try {
        const info = JSON.parse(buf.slice(0, nl));
        resolve({ port: info.port, source: info.source, ws: info.ws });
      } catch {
        reject(new Error("bad sidecar handshake"));
      }
    });
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`sidecar exited (${code})`)));
  });
  const stop = () => {
    try { child.stdin.destroy(); } catch {}
    if (child.exitCode === null) child.kill("SIGTERM");
  };
  return { child, ready, token, stop };
}

module.exports = { startSidecar };
