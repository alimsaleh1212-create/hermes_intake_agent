import { useEffect, useState } from "react";

export type Loadable<T> =
  | { state: "loading" }
  | { state: "error" }
  | { state: "ready"; data: T };

/** Runs `load` now and then every `intervalMs`; keeps stale data on a failed refresh. */
export function usePolling<T>(
  load: () => Promise<T>,
  intervalMs: number | null,
  deps: unknown[],
): Loadable<T> {
  const [value, setValue] = useState<Loadable<T>>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;
    setValue({ state: "loading" });
    const run = async () => {
      try {
        const data = await load();
        if (!cancelled) setValue({ state: "ready", data });
      } catch {
        if (!cancelled) {
          setValue((prev) => (prev.state === "ready" ? prev : { state: "error" }));
        }
      }
    };
    void run();
    const timer = intervalMs ? setInterval(run, intervalMs) : undefined;
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return value;
}
