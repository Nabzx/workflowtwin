export function formatMetric(value: number, unit: string): string {
  if (unit === "%") return value.toFixed(value % 1 === 0 ? 0 : 1);
  if (Number.isInteger(value)) return value.toLocaleString("en-GB");
  return value.toLocaleString("en-GB", { maximumFractionDigits: 2 });
}

export function sentenceCase(value: string): string {
  return value.replaceAll("_", " ").replace(/^./, (character) => character.toUpperCase());
}

export function shortId(value: string): string {
  return value.length > 18 ? `${value.slice(0, 9)}…${value.slice(-6)}` : value;
}

