import { ArrowRight, Plus, ShieldAlert, Shuffle } from "lucide-react";
import { type ReactNode, useRef } from "react";

import { fetchIntakes } from "./api";
import { formatAgo, formatCost, formatDuration, formatTime } from "./format";
import StatusBadge from "./StatusBadge";
import type { IntakeSummary } from "./types";
import { usePolling } from "./usePolling";

export const REFRESH_MS = 5000;

function Overview({ intakes }: { intakes: IntakeSummary[] }) {
  const count = (status: IntakeSummary["status"]) =>
    intakes.filter((i) => i.status === status).length;
  const processing = count("processing");
  const awaiting = count("awaiting_approval");
  const spent = intakes.reduce((sum, i) => sum + (i.cost_usd ?? 0), 0);
  const estimated = intakes.reduce((sum, i) => sum + (i.est_cost_usd ?? 0), 0);
  return (
    <dl className="overview">
      <div>
        <dt>Intakes</dt>
        <dd>{intakes.length}</dd>
      </div>
      <div>
        <dt>Processing</dt>
        <dd>{processing}</dd>
      </div>
      <div className={awaiting > 0 ? "overview-attention" : undefined}>
        <dt>Awaiting approval in Slack</dt>
        <dd>{awaiting}</dd>
      </div>
      <div>
        <dt>Spent</dt>
        <dd>
          {spent === 0 ? "$0" : `$${spent.toFixed(2)}`}
          <span className="overview-note">≈ ${estimated.toFixed(4)} at paid rates</span>
        </dd>
      </div>
    </dl>
  );
}

function SkeletonRows() {
  return (
    <div className="table-card" aria-busy="true">
      <span className="visually-hidden">Loading intakes…</span>
      {Array.from({ length: 4 }, (_, n) => (
        <div key={n} className="skeleton-row" aria-hidden>
          <span className="skeleton skeleton-wide" />
          <span className="skeleton" />
          <span className="skeleton" />
          <span className="skeleton skeleton-narrow" />
        </div>
      ))}
    </div>
  );
}

export default function IntakesTable() {
  const result = usePolling(fetchIntakes, REFRESH_MS, []);
  // Ids seen on an earlier refresh; anything else is new and animates in.
  const seen = useRef<Set<string> | null>(null);

  let body: ReactNode;
  if (result.state === "loading") {
    body = <SkeletonRows />;
  } else if (result.state === "error") {
    body = (
      <div className="callout callout-error" role="alert">
        <strong>Could not load intakes. Retrying every 5 seconds…</strong>
        <p>Check that the API is running and that VITE_API_URL points at it.</p>
      </div>
    );
  } else if (result.data.length === 0) {
    body = (
      <div className="empty">
        <h2>No intakes yet</h2>
        <p>
          Submit a Client's first-call Transcript. It is redacted, drafted into an Intake
          Output by the agent, and sent to Slack for Approval.
        </p>
        <a href="#/new" className="button button-primary">
          <Plus aria-hidden size={16} strokeWidth={2.5} />
          New intake
        </a>
      </div>
    );
  } else {
    const previous = seen.current;
    seen.current = new Set(result.data.map((i) => i.id));
    body = (
      <>
        <Overview intakes={result.data} />
        <div className="table-card">
          <table className="intakes">
            <thead>
              <tr>
                <th>Client</th>
                <th>Status</th>
                <th>Model</th>
                <th>Fallback</th>
                <th>Injection Flag</th>
                <th>Cost</th>
                <th className="num">Duration</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {result.data.map((i) => {
                const classes = [
                  i.fallback_used ? "row-fallback" : "",
                  i.injection_flagged ? "row-flagged" : "",
                  previous && !previous.has(i.id) ? "row-new" : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <tr key={i.id} className={classes || undefined}>
                    <td className="cell-client">
                      <a href={`#/intakes/${i.id}`} className="row-link">
                        {i.client_name}
                      </a>
                      <ArrowRight aria-hidden size={16} className="row-arrow" />
                    </td>
                    <td>
                      <StatusBadge status={i.status} />
                    </td>
                    <td className="cell-model" title={i.model_used ?? undefined}>
                      {i.model_used ?? "—"}
                    </td>
                    <td>
                      {i.fallback_used ? (
                        <span className="badge badge-fallback">
                          <Shuffle aria-hidden size={13} strokeWidth={2.25} />
                          Fallback
                        </span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      {i.injection_flagged ? (
                        <span className="badge badge-flagged">
                          <ShieldAlert aria-hidden size={13} strokeWidth={2.25} />
                          Flagged
                        </span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="cell-cost">{formatCost(i.cost_usd, i.est_cost_usd)}</td>
                    <td className="num">{formatDuration(i.duration_ms)}</td>
                    <td className="cell-time" title={formatTime(i.created_at)}>
                      {formatAgo(i.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </>
    );
  }

  return (
    <section className="list-page">
      <div className="page-head">
        <h1>Intakes</h1>
        <p className="page-lede">
          Every Transcript submitted, from redaction to Approval in Slack.
        </p>
      </div>
      {body}
    </section>
  );
}
