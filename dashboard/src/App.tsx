import { useEffect, useState } from "react";

import IntakeDetailView from "./IntakeDetailView";
import IntakesTable from "./IntakesTable";

function currentId(): string | null {
  const match = window.location.hash.match(/^#\/intakes\/(.+)$/);
  return match ? match[1] : null;
}

export default function App() {
  const [id, setId] = useState<string | null>(currentId);

  useEffect(() => {
    const onChange = () => setId(currentId());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return (
    <main>
      <header>
        <h1>
          <a href="#/">Hermes Intake</a>
        </h1>
      </header>
      {id ? <IntakeDetailView id={id} /> : <IntakesTable />}
    </main>
  );
}
