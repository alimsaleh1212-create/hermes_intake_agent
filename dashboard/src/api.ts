import type { IntakeDetail, IntakeSummary } from "./types";

const API_URL: string = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

/** A failed API call, carrying the HTTP status (0 when the server was unreachable). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) throw new ApiError(`GET ${path} failed`, response.status);
  return (await response.json()) as T;
}

export function fetchIntakes(): Promise<IntakeSummary[]> {
  return getJson<IntakeSummary[]>("/intakes");
}

export function fetchIntake(id: string): Promise<IntakeDetail> {
  return getJson<IntakeDetail>(`/intakes/${encodeURIComponent(id)}`);
}

export interface Submission {
  intake: IntakeDetail;
  /** False when the API returned an existing Intake for the same Transcript. */
  created: boolean;
}

/** POST /intakes. The API answers 202 for a new Intake and 200 for a duplicate. */
export async function submitIntake(
  apiKey: string,
  body: { client_name: string; transcript: string },
): Promise<Submission> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/intakes`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("The API could not be reached", 0);
  }
  if (!response.ok) throw new ApiError("POST /intakes failed", response.status);
  return {
    intake: (await response.json()) as IntakeDetail,
    created: response.status !== 200,
  };
}
