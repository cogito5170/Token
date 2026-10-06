import { describe, expect, it } from "vitest";
import { formatTokensCompact as f } from "../../src/lib/format";

describe("formatTokensCompact unit rollover (CMD-TKG1)", () => {
  it("moves to the next unit when rounding reaches 1000", () => {
    expect(f(999_950)).toBe("1M");
    expect(f(999_960_000)).toBe("1B");
    expect(f(-999_950)).toBe("-1M");
  });
  it("keeps values just below the boundary", () => {
    expect(f(999_949)).toBe("999.9K");
    expect(f(999)).toBe("999");
  });
  it("keeps existing behaviour", () => {
    expect(f(1500)).toBe("1.5K");
    expect(f(3_400_000)).toBe("3.4M");
    expect(f(12)).toBe("12");
    expect(f(null)).toBe("—");
  });
});
