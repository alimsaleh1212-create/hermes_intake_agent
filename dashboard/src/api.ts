import type { IntakeDetail, IntakeSummary } from "./types";

const API_URL: string = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) throw new Error(`GET ${path} failed: ${response.status}`);
  return (await response.json()) as T;
}

export function fetchIntakes(): Promise<IntakeSummary[]> {
  return getJson<IntakeSummary[]>("/intakes");
}

export function fetchIntake(id: string): Promise<IntakeDetail> {
  return getJson<IntakeDetail>(`/intakes/${encodeURIComponent(id)}`);
}
