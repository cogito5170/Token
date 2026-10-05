import { describe, expect, it } from "vitest";
import { formatMicroUsd, formatTokens, formatTokensCompact, formatPermille, formatMetric } from "../../src/lib/format";

describe("formatters", () => {
  it("turns 1234 micro-USD into $0.0012", () => expect(formatMicroUsd(1234)).toBe("$0.0012"));
  it("formats larger amounts with 2 decimals", () => {
    expect(formatMicroUsd(1_000_000)).toBe("$1.00");
    expect(formatMicroUsd(12_345_678_900)).toBe("$12,345.68");
    expect(formatMicroUsd(999_950)).toBe("$1.00");
    expect(formatMicroUsd(0)).toBe("$0.0000");
  });
  it("renders null as an em dash, never zero", () => {
    expect(formatMicroUsd(null)).toBe("—");
    expect(formatTokens(null)).toBe("—");
    expect(formatTokensCompact(undefined)).toBe("—");
    expect(formatPermille(null)).toBe("—");
    expect(formatMetric({ value: null, unit: "microusd" })).toBe("—");
  });
  it("formats tokens", () => {
    expect(formatTokens(1234567)).toBe("1,234,567");
    expect(formatTokensCompact(1500)).toBe("1.5K");
    expect(formatTokensCompact(3_400_000)).toBe("3.4M");
    expect(formatTokensCompact(12)).toBe("12");
  });
  it("formats permille and metrics by unit", () => {
    expect(formatPermille(875)).toBe("87.5%");
    expect(formatPermille(1000)).toBe("100%");
    expect(formatMetric({ value: 1234, unit: "microusd" })).toBe("$0.0012");
    expect(formatMetric({ value: 5000, unit: "tokens" })).toBe("5,000");
  });
});
