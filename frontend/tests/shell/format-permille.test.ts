import { describe, expect, it } from "vitest";
import { formatPermille as f } from "../../src/lib/format";

describe("formatPermille negatives (CMD-TKG2)", () => {
  it("formats negative permille with one sign", () => {
    expect(f(-5)).toBe("-0.5%");
    expect(f(-875)).toBe("-87.5%");
    expect(f(-10)).toBe("-1%");
  });
  it("keeps existing behaviour", () => {
    expect(f(875)).toBe("87.5%");
    expect(f(1000)).toBe("100%");
    expect(f(0)).toBe("0%");
    expect(f(874.6)).toBe("87.5%");
    expect(f(null)).toBe("—");
  });
});
