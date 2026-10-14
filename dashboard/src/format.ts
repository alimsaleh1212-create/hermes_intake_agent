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
