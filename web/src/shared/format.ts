export const pct = (x: number | null | undefined, digits = 1): string =>
  x === null || x === undefined ? "n/a" : `${(100 * x).toFixed(digits)}%`;

export const num = (x: number, digits = 0): string =>
  x.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const hours = (x: number | null): string => (x === null ? "never" : x < 1 ? "<1 h" : `${num(x)} h`);

const EVIDENCE: Record<string, string> = {
  name: "loop number",
  pid: "P&ID",
  description: "description",
  signal: "signal",
  type_misfit: "type misfit",
};
export const evidenceLabel = (k: string): string => EVIDENCE[k] ?? k;
