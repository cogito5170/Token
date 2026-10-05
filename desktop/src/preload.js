// Sandboxed preload: exposes only the (token-free) base URL of the in-app read-only proxy.
// The web Shell/live page detect window.gaDesktop themselves (no login, no placeholder token).
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("gaDesktop", Object.freeze({ sidecarUrl: "app://app" }));
