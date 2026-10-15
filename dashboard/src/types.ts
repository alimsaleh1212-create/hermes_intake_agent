// Mirrors the response schemas in app/schemas/intake.py.

export type IntakeStatus =
  | "processing"
  | "awaiting_approval"
  | "approved"
  | "changes_requested"
  | "failed";

export type Verdict = "yes" | "partial" | "no";

export interface ArchitectureComponent {
  name: string;
  purpose: string;
}

export interface AccessItem {
  system: string;
  access: string;
}

export interface FeasibilityVerdict {
  integration: string;
  verdict: Verdict;
  reason: string;
}

export interface IntakeOutput {
  current_systems: string[];
  architecture: ArchitectureComponent[];
  access_checklist: AccessItem[];
  feasibility: FeasibilityVerdict[];
}

export interface IntakeSummary {
  id: string;
  client_name: string;
  status: IntakeStatus;
  error: string | null;
  model_used: string | null;
  fallback_used: boolean;
  fallback_reason: string | null;
  injection_flagged: boolean;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  est_cost_usd: number | null;
  duration_ms: number | null;
  approved_by: string | null;
  decided_at: string | null;
  change_reason: string | null;
  created_at: string;
}

export interface IntakeDetail extends IntakeSummary {
  transcript_redacted: string;
  transcript_hash: string;
  output: IntakeOutput | null;
  slack_ts: string | null;
}
