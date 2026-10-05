import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.resetModules(); });

describe("NEXT_PUBLIC_API_MODE / NEXT_PUBLIC_API_URL (CMD-GC50)", () => {
  it("real mode uses the real client against NEXT_PUBLIC_API_URL", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "real");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test:9");
    const f = vi.fn(async () => new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", f);
    vi.resetModules();
    const { api } = await import("../../src/lib/api");
    await api().get("/v1/workspaces");
    expect(f).toHaveBeenCalledTimes(1);
    expect((f.mock.calls[0] as unknown[])[0]).toBe("http://api.test:9/v1/workspaces");
  });

  it("default and fake stay on the fake API (no network)", async () => {
    for (const mode of [undefined, "fake"]) {
      if (mode) vi.stubEnv("NEXT_PUBLIC_API_MODE", mode); else vi.unstubAllEnvs();
      const f = vi.fn();
      vi.stubGlobal("fetch", f);
      vi.resetModules();
      const { api, isFakeMode } = await import("../../src/lib/api");
      expect(isFakeMode(process.env.NEXT_PUBLIC_API_MODE)).toBe(true);
      const ws = await api().get("/v1/workspaces");
      expect(ws[0].role).toBe("admin");
      expect(f).not.toHaveBeenCalled();
    }
  });

  it("only the exact value real switches", async () => {
    const { isFakeMode } = await import("../../src/lib/api");
    expect(isFakeMode("real")).toBe(false);
    for (const v of [undefined, "", "fake", "REAL", "true"]) expect(isFakeMode(v)).toBe(true);
  });
});
