// Pure helpers for the shell's hardening. Kept free of Electron imports so they are unit-testable.
const crypto = require("node:crypto");

const WEB_PREFERENCES = Object.freeze({
  contextIsolation: true,
  nodeIntegration: false,
  sandbox: true,
  webSecurity: true,
  allowRunningInsecureContent: false,
  webviewTag: false,
  nodeIntegrationInWorker: false,
  nodeIntegrationInSubFrames: false,
  spellcheck: false,
});

/** Strict CSP. Inline scripts of the static export are allowed by hash only; no remote origin anywhere. */
function csp(scriptHashes = []) {
  const script = ["'self'", ...scriptHashes.map((h) => `'${h}'`)].join(" ");
  return [
    "default-src 'none'",
    `script-src ${script}`,
    "style-src 'self' 'unsafe-inline'", // React inline style attributes
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'", // the only reachable origin is app://app, which main proxies to the sidecar, GET only
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
  ].join("; ");
}

function inlineScriptHashes(html) {
  const out = [];
  const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
  let m;
  while ((m = re.exec(html))) {
    if (m[1].trim()) out.push("sha256-" + crypto.createHash("sha256").update(m[1], "utf8").digest("base64"));
  }
  return out;
}

/** The only requests main forwards to the sidecar. */
function allowedProxy(method, pathname) {
  return (method === "GET" || method === "HEAD") && /^\/v1\/workspaces\/[^/]+\/monitor\//.test(pathname);
}

/** Whether a URL may be shown in a window of the shell. */
function allowedNavigation(url) {
  return url.startsWith("app://app/");
}

module.exports = { WEB_PREFERENCES, csp, inlineScriptHashes, allowedProxy, allowedNavigation };
