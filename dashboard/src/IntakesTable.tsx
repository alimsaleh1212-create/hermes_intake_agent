import { fetchIntakes } from "./api";
import { formatCost, formatDuration, formatTime } from "./format";
import { usePolling } from "./usePolling";

export const REFRESH_MS = 5000;

export default function IntakesTable() {
  const result = usePolling(fetchIntakes, REFRESH_MS, []);

  if (result.state === "loading") return <p>Loading intakes…</p>;
  if (result.state === "error") {
    return <p role="alert">Could not load intakes. Retrying every 5 seconds…</p>;
  }
  if (result.data.length === 0) return <p>No intakes yet.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Client</th>
          <th>Status</th>
          <th>Model</th>
          <th>Fallback</th>
          <th>Injection Flag</th>
          <th>Cost</th>
          <th>Duration</th>
          <th>Created</th>
        </tr>
      </thead>
      <tbody>
        {result.data.map((i) => {
          const classes = [
            i.fallback_used ? "row-fallback" : "",
            i.injection_flagged ? "row-flagged" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <tr key={i.id} className={classes || undefined}>
              <td>
                <a href={`#/intakes/${i.id}`}>{i.client_name}</a>
              </td>
              <td>
                <span className={`status status-${i.status}`}>{i.status}</span>
              </td>
              <td>{i.model_used ?? "—"}</td>
              <td>
                {i.fallback_used ? (
                  <span className="badge badge-fallback">Fallback</span>
                ) : (
                  "—"
                )}
              </td>
              <td>
                {i.injection_flagged ? (
                  <span className="badge badge-flagged">Flagged</span>
                ) : (
                  "—"
                )}
              </td>
              <td>{formatCost(i.cost_usd, i.est_cost_usd)}</td>
              <td>{formatDuration(i.duration_ms)}</td>
              <td>{formatTime(i.created_at)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
