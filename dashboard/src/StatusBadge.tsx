import { Check, CircleAlert, Clock, LoaderCircle, Undo2 } from "lucide-react";

import { STATUS_LABEL } from "./labels";
import type { IntakeStatus } from "./types";

const ICON = {
  processing: LoaderCircle,
  awaiting_approval: Clock,
  approved: Check,
  changes_requested: Undo2,
  failed: CircleAlert,
} satisfies Record<IntakeStatus, unknown>;

export default function StatusBadge({ status }: { status: IntakeStatus }) {
  const Icon = ICON[status];
  return (
    <span className={`status status-${status}`}>
      <Icon aria-hidden size={14} strokeWidth={2.25} className="status-icon" />
      <span>{STATUS_LABEL[status]}</span>
    </span>
  );
}
