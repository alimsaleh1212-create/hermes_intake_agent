import {
  ArrowLeft,
  Check,
  CircleAlert,
  Clock,
  EyeOff,
  KeyRound,
  LoaderCircle,
  MessageSquareCheck,
  ShieldAlert,
  Shuffle,
  Sparkles,
  Undo2,
} from "lucide-react";
import type { ReactNode } from "react";

import { fetchIntake, type Submission } from "./api";
import { formatAgo, formatCost, formatDuration, formatTime, formatTokens } from "./format";
import { VERDICT_LABEL } from "./labels";
import StatusBadge from "./StatusBadge";
import Transcript, { countPlaceholders } from "./Transcript";
import type { IntakeDetail, IntakeOutput } from "./types";
import { usePolling } from "./usePolling";

// Faster than the table so the status flip after a Slack click shows quickly.
const DETAIL_REFRESH_MS = 3000;

// Slack sends the reviewer's user ID (e.g. U0C9EE2NNAW), which means nothing on screen.
function reviewer(approvedBy: string | null): string {
  if (!approvedBy || /^[UW][A-Z0-9]{6,}$/.test(approvedBy)) return "by a reviewer in Slack";
  return `by ${approvedBy}`;
}

type StepState = "done" | "active" | "waiting" | "failed";

interface Step {
  key: string;
  title: string;
  detail: string;
  state: StepState;
  icon: typeof Check;
}

function steps(intake: IntakeDetail): Step[] {
  const redacted = countPlaceholders(intake.transcript_redacted);
  const s = intake.status;
  const agent: Step =
    s === "processing"
      ? { key: "agent", title: "Agent drafting", detail: "Writing the Intake Output…", state: "active", icon: Sparkles }
      : s === "failed"
        ? { key: "agent", title: "Agent failed", detail: "Both models were tried", state: "failed", icon: Sparkles }
        : {
            key: "agent",
            title: "Drafted",
            detail: `${intake.fallback_used ? "Fallback · " : ""}${formatDuration(intake.duration_ms)}`,
            state: "done",
            icon: Sparkles,
          };
  const approval: Step =
    s === "approved"
      ? { key: "slack", title: "Approved", detail: reviewer(intake.approved_by), state: "done", icon: MessageSquareCheck }
      : s === "changes_requested"
        ? { key: "slack", title: "Changes requested", detail: reviewer(intake.approved_by), state: "done", icon: Undo2 }
        : s === "awaiting_approval"
          ? { key: "slack", title: "Awaiting Approval", detail: "Sent to Slack for a reviewer", state: "active", icon: MessageSquareCheck }
          : { key: "slack", title: "Approval in Slack", detail: s === "failed" ? "Not sent" : "Next", state: "waiting", icon: MessageSquareCheck };
  return [
    {
      key: "redact",
      title: "Redacted",
      detail: redactedLabel(redacted),
      state: "done",
      icon: EyeOff,
    },
    agent,
    approval,
  ];
}

function redactedLabel(count: number): string {
  return count === 0 ? "No PII found" : `${count} value${count === 1 ? "" : "s"} redacted`;
}

function StepIcon({ step }: { step: Step }) {
  if (step.state === "done") return <Check aria-hidden size={16} strokeWidth={2.75} />;
  if (step.state === "failed") return <CircleAlert aria-hidden size={16} strokeWidth={2.5} />;
  if (step.state === "active" && step.key === "agent") {
    return <LoaderCircle aria-hidden size={16} strokeWidth={2.5} className="spin" />;
  }
  if (step.state === "active") return <Clock aria-hidden size={16} strokeWidth={2.5} />;
  const Icon = step.icon;
  return <Icon aria-hidden size={16} strokeWidth={2.25} />;
}

function Progress({ intake }: { intake: IntakeDetail }) {
  return (
    <ol className="progress" aria-label="Progress">
      {steps(intake).map((step) => (
        <li key={step.key} className={`step step-${step.state}`}>
          <span className="step-icon">
            <StepIcon step={step} />
          </span>
          <span className="step-text">
            <span className="step-title">{step.title}</span>
            <span className="step-detail">{step.detail}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function Section({ title, count, children }: { title: string; count?: ReactNode; children: ReactNode }) {
  return (
    <section className="doc-section">
      <div className="doc-head">
        <h2>{title}</h2>
        {count !== undefined && <span className="doc-count">{count}</span>}
      </div>
      {children}
    </section>
  );
}

function OutputDocs({ out }: { out: IntakeOutput }) {
  const tally = { yes: 0, partial: 0, no: 0 };
  for (const f of out.feasibility) tally[f.verdict] += 1;
  const issues = tally.no;
  return (
    <>
      <Section title="Current Systems" count={out.current_systems.length}>
        <ul className="chips">
          {out.current_systems.map((s) => (
            <li key={s} className="chip">
              {s}
            </li>
          ))}
        </ul>
      </Section>

      <Section
        title="Feasibility Verdicts"
        count={
          <>
            {tally.yes} yes · {tally.partial} partial ·{" "}
            <span className={issues > 0 ? "doc-count-issue" : undefined}>
              {issues} {issues === 1 ? "Issue" : "Issues"}
            </span>
          </>
        }
      >
        <ul className="verdicts">
          {out.feasibility.map((f) => (
            <li key={f.integration} className={`verdict-row verdict-row-${f.verdict}`}>
              <span className={`verdict verdict-${f.verdict}`}>{VERDICT_LABEL[f.verdict]}</span>
              <div>
                <strong>{f.integration}</strong>
                <p>{f.reason}</p>
              </div>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Architecture Doc" count={out.architecture.length}>
        <ul className="arch">
          {out.architecture.map((c) => (
            <li key={c.name}>
              <strong>{c.name}</strong>
              <p>{c.purpose}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Access Checklist" count={out.access_checklist.length}>
        <ul className="access">
          {out.access_checklist.map((a) => (
            <li key={`${a.system}:${a.access}`}>
              <KeyRound aria-hidden size={16} className="access-icon" />
              <strong>{a.system}</strong>
              <p>{a.access}</p>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

function PendingDocs({ failed }: { failed: boolean }) {
  if (failed) {
    return (
      <div className="empty empty-inline">
        <h2>No output</h2>
        <p>This Intake failed before the agent returned a valid Intake Output.</p>
      </div>
    );
  }
  return (
    <div className="pending-docs">
      <p className="pending-note">
        <LoaderCircle aria-hidden size={16} className="spin" />
        No output yet. The agent is drafting the Intake Output; this page updates on its own.
      </p>
      {["Current Systems", "Feasibility Verdicts", "Architecture Doc", "Access Checklist"].map((t) => (
        <div key={t} className="doc-section doc-ghost" aria-hidden>
          <span className="ghost-title">{t}</span>
          <span className="skeleton skeleton-wide" />
          <span className="skeleton" />
        </div>
      ))}
    </div>
  );
}

export default function IntakeDetailView({ id, submission }: { id: string; submission: Submission | null }) {
  const result = usePolling(() => fetchIntake(id), DETAIL_REFRESH_MS, [id]);

  if (result.state === "loading") {
    return (
      <div className="detail-loading" aria-busy="true">
        <span className="skeleton skeleton-title" />
        <span className="skeleton skeleton-wide" />
        <span className="visually-hidden">Loading intake…</span>
      </div>
    );
  }
  if (result.state === "error") {
    return (
      <div className="detail">
        <a href="#/" className="back">
          <ArrowLeft aria-hidden size={16} /> All intakes
        </a>
        <div className="callout callout-error" role="alert">
          <strong>Could not load this intake.</strong>
          <p>It may not exist, or the API is not reachable. Retrying every few seconds.</p>
        </div>
      </div>
    );
  }

  const intake = result.data;
  return (
    <article className="detail">
      <a href="#/" className="back">
        <ArrowLeft aria-hidden size={16} /> All intakes
      </a>

      {submission && (
        <p className="notice" role="status">
          {submission.created
            ? "Submitted. Follow it here: the status changes as the agent finishes and the reviewer decides in Slack."
            : "This Transcript was already submitted, so this is its existing Intake."}
        </p>
      )}

      <header className="detail-head">
        <div className="detail-title">
          <h1>{intake.client_name}</h1>
          <StatusBadge status={intake.status} />
        </div>
        <dl className="meta">
          <div>
            <dt>Model</dt>
            <dd>{intake.model_used ?? "—"}</dd>
          </div>
          <div>
            <dt>Cost</dt>
            <dd>{formatCost(intake.cost_usd, intake.est_cost_usd)}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{formatDuration(intake.duration_ms)}</dd>
          </div>
          <div>
            <dt>Tokens</dt>
            <dd>{formatTokens(intake.tokens_in, intake.tokens_out)}</dd>
          </div>
          <div>
            <dt>Submitted</dt>
            <dd title={formatTime(intake.created_at)}>{formatAgo(intake.created_at)}</dd>
          </div>
        </dl>
      </header>

      <Progress intake={intake} />

      {(intake.injection_flagged || intake.fallback_used || intake.error) && (
        <div className="flags">
          {intake.injection_flagged && (
            <div className="callout callout-warn">
              <ShieldAlert aria-hidden size={18} />
              <div>
                <strong>Injection Flag</strong>
                <p>
                  The Transcript contains phrases that try to instruct the agent. It was still
                  processed as data only; the reviewer should look closer.
                </p>
              </div>
            </div>
          )}
          {intake.fallback_used && (
            <div className="callout callout-info">
              <Shuffle aria-hidden size={18} />
              <div>
                <strong>Fallback</strong>
                <p>
                  Completed by the secondary model
                  {intake.fallback_reason ? `: ${intake.fallback_reason}` : "."}
                </p>
              </div>
            </div>
          )}
          {intake.error && (
            <div className="callout callout-error" role="status">
              <CircleAlert aria-hidden size={18} />
              <div>
                <strong>Error</strong>
                <p>{intake.error}</p>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="detail-grid">
        <div className="docs">
          {intake.output === null ? (
            <PendingDocs failed={intake.status === "failed"} />
          ) : (
            <OutputDocs out={intake.output} />
          )}
        </div>
        <aside className="transcript-panel">
          <div className="doc-head">
            <h2>Redacted Transcript</h2>
            <span className="doc-count">
              {redactedLabel(countPlaceholders(intake.transcript_redacted))}
            </span>
          </div>
          <Transcript text={intake.transcript_redacted} />
        </aside>
      </div>
    </article>
  );
}
