export const EM_DASH = "—";

/** Round-half-up integer division for non-negative n. */
const divRound = (n: number, d: number) => Math.floor((n + Math.floor(d / 2)) / d);

const group = (n: number) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/**
 * Integer micro-USD -> "$0.0012". Under $1: 4 decimals; $1 and over: 2 decimals with grouping.
 * null/undefined (unknown) -> "—", never "$0".
 */
export function formatMicroUsd(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return EM_DASH;
  const sign = v < 0 ? "-" : "";
  const a = Math.abs(Math.trunc(v));
  if (a < 1_000_000) {
    const c = divRound(a, 100); // 1e-4 USD units
    if (c >= 10_000) return `${sign}$1.00`;
    return `${sign}$0.${String(c).padStart(4, "0")}`;
  }
  const cents = divRound(a, 10_000);
  return `${sign}$${group(Math.floor(cents / 100))}.${String(cents % 100).padStart(2, "0")}`;
}

/** Integer token count -> "1,234,567"; null -> "—". */
export function formatTokens(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return EM_DASH;
  return (v < 0 ? "-" : "") + group(Math.abs(Math.trunc(v)));
}

/** Compact tokens for axes: 1.2K, 3.4M, 5.6B; null -> "—". */
export function formatTokensCompact(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return EM_DASH;
  const a = Math.abs(v);
  const s = v < 0 ? "-" : "";
  for (const [d, u] of [[1e9, "B"], [1e6, "M"], [1e3, "K"]] as const) {
    if (a >= d) return `${s}${(Math.round((a / d) * 10) / 10).toString()}${u}`;
  }
  return s + String(Math.trunc(a));
}

/** permille (0..1000) -> "87.5%"; null -> "—". */
export function formatPermille(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return EM_DASH;
  const t = Math.round(v);
  const sign = t < 0 ? "-" : "";
  const abs = Math.abs(t);
  const integerPart = Math.floor(abs / 10);
  const fraction = abs % 10;
  return `${sign}${integerPart}${fraction ? "." + fraction : ""}%`;
}

export function formatCount(v: number | null | undefined): string {
  return formatTokens(v);
}
