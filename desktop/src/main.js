// CMD-IF1: desktop shell (ADR-0008). Usage: electron . --ga-dir PATH   (or GA_DIR=PATH)
const { app, BrowserWindow, protocol, session, net } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { WEB_PREFERENCES, csp, inlineScriptHashes, allowedProxy, allowedNavigation } = require("./security");
const { startSidecar } = require("./sidecar");

protocol.registerSchemesAsPrivileged([
  { scheme: "app", privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } },
]);

const RENDERER = process.env.GA_RENDERER_DIR || path.join(__dirname, "..", "renderer");
// packaged (scripts/pack.mjs): the vendored reader sits next to src/; from the repo: ../../backend
const VENDORED = path.join(__dirname, "..", "backend");
const BACKEND = process.env.GA_BACKEND_DIR
  || (fs.existsSync(path.join(VENDORED, "app", "domains", "run", "sidecar.py")) ? VENDORED : path.join(__dirname, "..", "..", "backend"));
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2", ".txt": "text/plain" };

function argGaDir() {
  const i = process.argv.indexOf("--ga-dir");
  return (i > 0 && process.argv[i + 1]) || process.env.GA_DIR || "";
}

let sidecar = null;
let win = null;

function serveStatic(pathname) {
  let rel = decodeURIComponent(pathname);
  if (rel.endsWith("/")) rel += "index.html";
  const file = path.resolve(RENDERER, "." + rel);
  if (file !== RENDERER && !file.startsWith(RENDERER + path.sep)) return new Response("forbidden", { status: 403 });
  let data;
  try { data = fs.readFileSync(file); } catch { return new Response("not found", { status: 404 }); }
  const ext = path.extname(file);
  const headers = { "content-type": MIME[ext] || "application/octet-stream", "cache-control": "no-store" };
  if (ext === ".html") headers["content-security-policy"] = csp(inlineScriptHashes(data.toString("utf8")));
  return new Response(data, { headers });
}

async function proxy(req, url) {
  if (!allowedProxy(req.method, url.pathname)) return new Response('{"error":"read_only"}', { status: 405, headers: { allow: "GET" } });
  const info = await sidecar.ready;
  const upstream = `http://127.0.0.1:${info.port}${url.pathname}${url.search}`;
  const headers = { authorization: `Bearer ${sidecar.token}` };
  for (const h of ["accept", "last-event-id"]) if (req.headers.get(h)) headers[h] = req.headers.get(h);
  return net.fetch(upstream, { method: req.method, headers, signal: req.signal, bypassCustomProtocolHandlers: true });
}

async function createWindow() {
  const gaDir = path.resolve(argGaDir());
  const python = process.env.GA_PYTHON || "python3";
  sidecar = startSidecar({ gaDir, python, backendDir: BACKEND });
  global.__gaSidecarPid = sidecar.child.pid; // read by tests only
  const ses = session.defaultSession;
  ses.setPermissionRequestHandler((_wc, _perm, cb) => cb(false));
  ses.protocol.handle("app", (req) => {
    const url = new URL(req.url);
    return url.pathname.startsWith("/v1/") ? proxy(req, url) : serveStatic(url.pathname);
  });
  const info = await sidecar.ready;
  win = new BrowserWindow({
    width: 1280, height: 800, show: process.env.GA_SHOW !== "0", backgroundColor: "#000000",
    webPreferences: { ...WEB_PREFERENCES, preload: path.join(__dirname, "preload.js") },
  });
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (e, url) => { if (!allowedNavigation(url)) e.preventDefault(); });
  win.webContents.on("will-attach-webview", (e) => e.preventDefault());
  const q = new URLSearchParams({ source: info.source, api: "app://app", ws: info.ws });
  await win.loadURL(`app://app/live/?${q}`);
  global.__gaWindow = win;
}

app.on("window-all-closed", () => app.quit());
app.on("will-quit", () => sidecar && sidecar.stop());
process.on("exit", () => sidecar && sidecar.stop());
for (const s of ["SIGINT", "SIGTERM"]) process.on(s, () => app.quit());

app.whenReady().then(createWindow).catch((e) => {
  console.error("startup failed:", e.message); // never include the token
  app.exit(1);
});
