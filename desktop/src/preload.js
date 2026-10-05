// Sandboxed preload: exposes only the (token-free) base URL of the in-app read-only proxy.
const { contextBridge } = require("electron");

// The web Shell redirects to /login unless it finds an access token in sessionStorage. The desktop has no account;
// a fixed placeholder (not a secret, and not the sidecar token, which stays in main) lets the monitor screen render.
// Baseline request: let the Shell skip the login redirect for /live when window.gaDesktop is present.
try { window.sessionStorage.setItem("gc.access", "desktop-local-placeholder"); } catch {}

contextBridge.exposeInMainWorld("gaDesktop", Object.freeze({ sidecarUrl: "app://app" }));
