import { fetchIntake } from "./api";
import { formatCost } from "./format";
import { usePolling } from "./usePolling";

export default function IntakeDetailView({ id }: { id: string }) {
  const result = usePolling(() => fetchIntake(id), 5000, [id]);

  if (result.state === "loading") return <p>Loading intake…</p>;
  if (result.state === "error") return <p role="alert">Could not load this intake.</p>;

  const intake = result.data;
  const out = intake.output;
  return (
    <article>
      <h2>{intake.client_name}</h2>
      <p>
        <span className={`status status-${intake.status}`}>{intake.status}</span>{" "}
        {formatCost(intake.cost_usd, intake.est_cost_usd)}
      </p>
      {intake.error && <p role="status">Error: {intake.error}</p>}
      {out === null ? (
        <p>No output yet.</p>
      ) : (
        <>
          <section>
            <h3>Current Systems</h3>
            <ul>
              {out.current_systems.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Architecture Doc</h3>
            <ul>
              {out.architecture.map((c) => (
                <li key={c.name}>
                  <strong>{c.name}</strong>
                  <p>{c.purpose}</p>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Access Checklist</h3>
            <ul>
              {out.access_checklist.map((a) => (
                <li key={`${a.system}:${a.access}`}>
                  <strong>{a.system}</strong>
                  <p>{a.access}</p>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Feasibility Verdicts</h3>
            <ul>
              {out.feasibility.map((f) => (
                <li key={f.integration}>
                  <strong>{f.integration}</strong>{" "}
                  <span className={`verdict verdict-${f.verdict}`}>{f.verdict}</span>
                  <p>{f.reason}</p>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
      <section>
        <h3>Redacted Transcript</h3>
        <pre>{intake.transcript_redacted}</pre>
      </section>
    </article>
  );
}
