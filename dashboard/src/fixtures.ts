import type { IntakeDetail, IntakeSummary } from "./types";

export function makeSummary(over: Partial<IntakeSummary> = {}): IntakeSummary {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    client_name: "Acme Corp",
    status: "awaiting_approval",
    error: null,
    model_used: "openai/gpt-oss-120b",
    fallback_used: false,
    fallback_reason: null,
    injection_flagged: false,
    tokens_in: 1000,
    tokens_out: 500,
    cost_usd: 0,
    est_cost_usd: 0.0123,
    duration_ms: 4200,
    approved_by: null,
    decided_at: null,
    created_at: "2026-10-14T10:00:00Z",
    ...over,
  };
}

export function makeDetail(over: Partial<IntakeDetail> = {}): IntakeDetail {
  return {
    ...makeSummary(),
    transcript_redacted: "Hi, I am [EMAIL_1] and we run Shopify.",
    transcript_hash: "abc",
    slack_ts: null,
    output: {
      current_systems: ["Shopify", "QuickBooks"],
      architecture: [{ name: "Sync service", purpose: "Mirror orders" }],
      access_checklist: [{ system: "Shopify", access: "Admin API token" }],
      feasibility: [
        { integration: "Shopify to QB", verdict: "yes", reason: "Native API" },
        { integration: "Legacy ERP", verdict: "partial", reason: "CSV only" },
        { integration: "Fax gateway", verdict: "no", reason: "No API" },
      ],
    },
    ...over,
  };
}
