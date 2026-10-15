export function formatCost(
  costUsd: number | null,
  estCostUsd: number | null,
): string {
  if (costUsd === null && estCostUsd === null) return "—";
  const paid = costUsd === null || costUsd === 0 ? "$0" : `$${costUsd.toFixed(2)}`;
  if (estCostUsd === null) return paid;
  return `${paid} (≈ $${estCostUsd.toFixed(4)} at paid rates)`;
}

export function formatDuration(ms: number | null): string {
  return ms === null ? "—" : `${(ms / 1000).toFixed(1)} s`;
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

/** "just now", "4 min ago", "3 h ago", then the date. */
export function formatAgo(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function formatTokens(tokensIn: number | null, tokensOut: number | null): string {
  if (tokensIn === null && tokensOut === null) return "—";
  const fmt = (n: number | null) => (n === null ? "—" : n.toLocaleString());
  return `${fmt(tokensIn)} in · ${fmt(tokensOut)} out`;
}
