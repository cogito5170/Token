# ADR-0008 Desktop shell for the live monitor: Electron + read-only Python sidecar

- Status: adopted (phase 1b, spec 3.1)
- Decision:
  - **Web first.** The live monitor is a Next.js screen (`frontend/src/app/(app)/live/`). The web build reads a `.ga` registered on the server through the Run domain API (snapshot + SSE + recordings).
  - **Desktop = the same components inside Electron.** The renderer is the same static Next.js export.
  - **Local reading through a sidecar.** The desktop shell spawns the Run domain reader as a sidecar on `127.0.0.1`: `python3 -m app.domains.run.sidecar --ga-dir PATH --port 0`, which prints its port and a one-time token. The sidecar serves only the GET paths of `/v1/workspaces/{ws}/monitor/*`, with ws = nil UUID.
  - **Read-only.** The sidecar opens files read-only and takes no locks. There is no control action anywhere.
- Why Electron over Tauri:
  1. The monitor is a continuously animated Canvas 2D stage ("interactive art", spec 3.1.1). Electron ships one Chromium everywhere, so frame pacing, canvas filters, blend modes and `prefers-reduced-motion` behave exactly as in the web build. Tauri uses the system WebView (WebKitGTK on Linux, WKWebView on macOS, WebView2 on Windows). WebKitGTK in particular has weaker canvas performance and differs in compositing, so it would split the visual tests three ways.
  2. Visual tests: Playwright drives Electron (`_electron.launch`) with the same Chromium as the web tests, so one set of golden scenes covers both. Tauri has no comparable first-party driver.
  3. Tauri's main strengths are a small binary and a Rust-side permission model. They matter less here because the shell holds no secrets and does no writing: the renderer has no Node or file access, and all file reading sits in the read-only sidecar.
  - Cost accepted: a bundle of ~100+ MB and higher memory use.
- Why a Python sidecar rather than a TypeScript reader:
  - There is one reader implementation, the one the web API also uses, so the two cannot drift.
  - ga users already have Python 3.10+ (ga is Python).
  - The reader is standard library only, so the sidecar needs no installs beyond the backend package's `app.domains.run` module, which is vendored into the app bundle as plain .py files.
- Hardening:
  - `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`.
  - The preload script exposes only `{sidecarUrl, token}`.
  - CSP `connect-src` allows `http://127.0.0.1:<port>` only.
  - The sidecar binds to loopback only, requires the token header, and rejects any method other than GET/HEAD.
- Revisit if: Tauri gains a stable Playwright-grade driver and WebKitGTK canvas performance is adequate. The renderer code would not change.
