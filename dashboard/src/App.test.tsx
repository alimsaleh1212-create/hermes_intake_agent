import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { makeDetail, makeSummary } from "./fixtures";
import { formatCost } from "./format";

type Handler = (
  init?: RequestInit,
) => { status?: number; body: unknown } | Promise<never>;

/** Routes are keyed by path for GET and by "METHOD path" otherwise. */
function mockApi(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input).replace(/^https?:\/\/[^/]+/, "");
    const method = init?.method ?? "GET";
    const handler = routes[method === "GET" ? url : `${method} ${url}`];
    if (!handler) throw new Error(`unmocked ${method} ${url}`);
    const { status = 200, body } = (await handler(init)) as {
      status?: number;
      body: unknown;
    };
    return new Response(JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => {
  window.location.hash = "";
  window.localStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("formatCost", () => {
  it("shows $0 with the estimated paid-rate cost", () => {
    expect(formatCost(0, 0.0123)).toBe("$0 (≈ $0.0123 at paid rates)");
  });
  it("shows a dash when cost is unknown", () => {
    expect(formatCost(null, null)).toBe("—");
  });
  it("shows a real cost when nonzero", () => {
    expect(formatCost(0.5, 0.5)).toBe("$0.50 (≈ $0.5000 at paid rates)");
  });
});

describe("Intakes table", () => {
  it("renders a row per intake with its fields", async () => {
    mockApi({
      "/intakes": () => ({ body: [makeSummary()] }),
    });
    render(<App />);
    const row = (await screen.findByText("Acme Corp")).closest("tr")!;
    expect(within(row).getByText("Awaiting approval")).toBeInTheDocument();
    expect(within(row).getByText("openai/gpt-oss-120b")).toBeInTheDocument();
    expect(
      within(row).getByText("$0 (≈ $0.0123 at paid rates)"),
    ).toBeInTheDocument();
    expect(within(row).getByText("4.2 s")).toBeInTheDocument();
  });

  it("highlights fallback and flagged intakes", async () => {
    mockApi({
      "/intakes": () => ({
        body: [
          makeSummary({ id: "a", client_name: "Plain" }),
          makeSummary({ id: "b", client_name: "Fell", fallback_used: true }),
          makeSummary({ id: "c", client_name: "Sus", injection_flagged: true }),
        ],
      }),
    });
    render(<App />);
    const plain = (await screen.findByText("Plain")).closest("tr")!;
    const fell = screen.getByText("Fell").closest("tr")!;
    const sus = screen.getByText("Sus").closest("tr")!;
    expect(plain).not.toHaveClass("row-fallback");
    expect(plain).not.toHaveClass("row-flagged");
    expect(fell).toHaveClass("row-fallback");
    expect(within(fell).getByText("Fallback")).toBeInTheDocument();
    expect(sus).toHaveClass("row-flagged");
    expect(within(sus).getByText("Flagged")).toBeInTheDocument();
  });

  it("shows Fallback and the Injection Flag in their own columns", async () => {
    mockApi({
      "/intakes": () => ({
        body: [
          makeSummary({
            client_name: "Both",
            fallback_used: true,
            injection_flagged: true,
          }),
        ],
      }),
    });
    render(<App />);
    const row = (await screen.findByText("Both")).closest("tr")!;
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    const cells = within(row).getAllByRole("cell");
    expect(cells[headers.indexOf("Fallback")]).toHaveTextContent("Fallback");
    expect(cells[headers.indexOf("Injection Flag")]).toHaveTextContent("Flagged");
  });

  it("refreshes every 5 seconds and picks up a status change", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let status: "awaiting_approval" | "approved" = "awaiting_approval";
    const fn = mockApi({
      "/intakes": () => ({ body: [makeSummary({ status })] }),
    });
    render(<App />);
    expect(await screen.findByText("Awaiting approval")).toBeInTheDocument();
    status = "approved";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(await screen.findByText("Approved")).toBeInTheDocument();
    expect(fn.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("shows a loading state, then an empty state", async () => {
    mockApi({ "/intakes": () => ({ body: [] }) });
    render(<App />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(await screen.findByText(/no intakes yet/i)).toBeInTheDocument();
  });

  it("shows an error state when the API fails", async () => {
    mockApi({ "/intakes": () => ({ status: 500, body: { detail: "boom" } }) });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not load/i);
  });
});

describe("Intake detail", () => {
  const id = "11111111-1111-1111-1111-111111111111";

  it("renders every section from the table link", async () => {
    mockApi({
      "/intakes": () => ({ body: [makeSummary()] }),
      [`/intakes/${id}`]: () => ({ body: makeDetail() }),
    });
    window.location.hash = `#/intakes/${id}`;
    render(<App />);
    await screen.findByRole("heading", { name: /current systems/i });
    expect(screen.getByText("QuickBooks")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /architecture doc/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Sync service")).toBeInTheDocument();
    expect(screen.getByText("Mirror orders")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /access checklist/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Admin API token")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /feasibility verdicts/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Yes").className).toContain("verdict-yes");
    expect(screen.getByText("Partial").className).toContain("verdict-partial");
    expect(screen.getByText("No").className).toContain("verdict-no");
    expect(
      screen.getByRole("heading", { name: /redacted transcript/i }),
    ).toBeInTheDocument();
    const placeholder = screen.getByText("[EMAIL_1]");
    expect(placeholder.tagName).toBe("MARK");
    expect(placeholder.closest("p")).toHaveTextContent(
      "Hi, I am [EMAIL_1] and we run Shopify.",
    );
  });

  it("navigates from a table row to the detail view", async () => {
    mockApi({
      "/intakes": () => ({ body: [makeSummary()] }),
      [`/intakes/${id}`]: () => ({ body: makeDetail() }),
    });
    render(<App />);
    (await screen.findByRole("link", { name: "Acme Corp" })).click();
    expect(
      await screen.findByRole("heading", { name: /current systems/i }),
    ).toBeInTheDocument();
  });

  it("handles an intake still processing (no output yet)", async () => {
    mockApi({
      [`/intakes/${id}`]: () => ({
        body: makeDetail({ status: "processing", output: null }),
      }),
    });
    window.location.hash = `#/intakes/${id}`;
    render(<App />);
    expect(await screen.findByText(/no output yet/i)).toBeInTheDocument();
  });

  it("shows an error state on 404", async () => {
    mockApi({ [`/intakes/${id}`]: () => ({ status: 404, body: {} }) });
    window.location.hash = `#/intakes/${id}`;
    render(<App />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/could not load/i),
    );
  });
});

describe("New intake", () => {
  const id = "11111111-1111-1111-1111-111111111111";

  function openForm() {
    window.location.hash = "#/new";
    render(<App />);
  }

  it("submits a demo Transcript with the API key and opens its Intake", async () => {
    const user = userEvent.setup();
    const posted: RequestInit[] = [];
    mockApi({
      "POST /intakes": (init) => {
        posted.push(init!);
        return { status: 202, body: makeDetail({ status: "processing", output: null }) };
      },
      [`/intakes/${id}`]: () => ({
        body: makeDetail({ status: "processing", output: null }),
      }),
    });
    openForm();

    const submit = screen.getByRole("button", { name: /submit intake/i });
    expect(submit).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /mike's roofing/i }));
    expect(screen.getByLabelText("Client name")).toHaveValue("Mike's Roofing");
    expect((screen.getByLabelText("Transcript") as HTMLTextAreaElement).value).toContain(
      "WordPress",
    );
    await user.type(screen.getByLabelText("API key"), "secret-key");
    await user.click(submit);

    expect(await screen.findByText(/no output yet/i)).toBeInTheDocument();
    expect(window.location.hash).toBe(`#/intakes/${id}`);
    expect(screen.getByRole("status")).toHaveTextContent(/submitted/i);
    expect(posted).toHaveLength(1);
    expect((posted[0].headers as Record<string, string>)["X-API-Key"]).toBe(
      "secret-key",
    );
    const body = JSON.parse(String(posted[0].body));
    expect(body.client_name).toBe("Mike's Roofing");
    expect(body.transcript).toContain("Jobber");
    expect(window.localStorage.getItem("hermes-intake.api-key")).toBe("secret-key");
  });

  it("says when the Transcript was already submitted", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("hermes-intake.api-key", "secret-key");
    mockApi({
      "POST /intakes": () => ({ status: 200, body: makeDetail() }),
      [`/intakes/${id}`]: () => ({ body: makeDetail() }),
    });
    openForm();
    expect(screen.getByText(/api key saved in this browser/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /clearflow plumbing/i }));
    await user.click(screen.getByRole("button", { name: /submit intake/i }));
    expect(await screen.findByRole("status")).toHaveTextContent(/already submitted/i);
  });

  it("asks for the key again when the API rejects it", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("hermes-intake.api-key", "wrong");
    mockApi({ "POST /intakes": () => ({ status: 401, body: {} }) });
    openForm();
    await user.type(screen.getByLabelText("Client name"), "Acme");
    await user.type(screen.getByLabelText("Transcript"), "We use Shopify.");
    await user.click(screen.getByRole("button", { name: /submit intake/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/api key was rejected/i);
    expect(screen.getByLabelText("API key")).toHaveValue("wrong");
    expect(window.location.hash).toBe("#/new");
  });
});
