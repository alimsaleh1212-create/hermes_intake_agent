import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { SAMPLES } from "./samples";

describe("demo Transcripts", () => {
  it.each(SAMPLES.map((s) => s.id))("%s matches /transcripts", (id) => {
    // Vitest runs from dashboard/; the originals sit at the repo root.
    const original = readFileSync(join(process.cwd(), "..", "transcripts", `${id}.txt`), "utf-8");
    expect(SAMPLES.find((s) => s.id === id)!.transcript).toBe(original);
  });
});
