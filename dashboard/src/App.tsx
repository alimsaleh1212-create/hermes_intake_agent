import { Plus } from "lucide-react";
import { useEffect, useState } from "react";

import type { Submission } from "./api";
import IntakeDetailView from "./IntakeDetailView";
import IntakesTable from "./IntakesTable";
import NewIntakeView from "./NewIntakeView";

type Route = { name: "list" } | { name: "new" } | { name: "detail"; id: string };

function currentRoute(): Route {
  const hash = window.location.hash;
  if (hash === "#/new") return { name: "new" };
  const match = hash.match(/^#\/intakes\/(.+)$/);
  return match ? { name: "detail", id: match[1] } : { name: "list" };
}

export default function App() {
  const [route, setRoute] = useState<Route>(currentRoute);
  // The last submission, so its detail page can say whether it was new or a duplicate.
  const [lastSubmission, setLastSubmission] = useState<Submission | null>(null);

  useEffect(() => {
    const onChange = () => {
      setRoute(currentRoute());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const onSubmitted = (submission: Submission) => {
    setLastSubmission(submission);
    window.location.hash = `#/intakes/${submission.intake.id}`;
  };

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <a href="#/" className="wordmark">
            Hermes Intake
          </a>
          <nav className="topnav" aria-label="Main">
            <a href="#/" aria-current={route.name === "list" ? "page" : undefined}>
              Intakes
            </a>
          </nav>
          <span className="live" title="The dashboard refreshes on its own">
            <span className="live-dot" aria-hidden />
            Live
          </span>
          {route.name !== "new" && (
            <a href="#/new" className="button button-primary">
              <Plus aria-hidden size={16} strokeWidth={2.5} />
              New intake
            </a>
          )}
        </div>
      </header>
      <main className="page">
        {route.name === "new" && <NewIntakeView onSubmitted={onSubmitted} />}
        {route.name === "detail" && (
          <IntakeDetailView
            key={route.id}
            id={route.id}
            submission={lastSubmission?.intake.id === route.id ? lastSubmission : null}
          />
        )}
        {route.name === "list" && <IntakesTable />}
      </main>
    </div>
  );
}
