// Acceptance test for CMD-TKG10 (written by baseline; the executor may not edit it).
import { describe, expect, it } from "vitest";
import { formatMicroUsd, formatTokens } from "../../src/lib/format";

describe("no negative zero (CMD-TKG10)", () => {
  it("prints zero without a sign", () => {
    expect(formatMicroUsd(-40)).toBe("$0.0000");
    expect(formatTokens(-0.5)).toBe("0");
    expect(formatTokens(-0)).toBe("0");
  });
  it("keeps real negatives", () => {
    expect(formatMicroUsd(-1234)).toBe("-$0.0012");
    expect(formatMicroUsd(-2_500_000)).toBe("-$2.50");
    expect(formatTokens(-1234)).toBe("-1,234");
  });
});
