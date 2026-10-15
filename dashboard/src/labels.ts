import type { IntakeStatus, Verdict } from "./types";

export const STATUS_LABEL: Record<IntakeStatus, string> = {
  processing: "Processing",
  awaiting_approval: "Awaiting approval",
  approved: "Approved",
  changes_requested: "Changes requested",
  failed: "Failed",
};

export const VERDICT_LABEL: Record<Verdict, string> = {
  yes: "Yes",
  partial: "Partial",
  no: "No",
};
