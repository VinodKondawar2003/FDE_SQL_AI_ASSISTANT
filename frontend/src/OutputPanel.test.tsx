import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import OutputPanel from "./OutputPanel";
import type { TurnResponse } from "./api";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
const base = {
  turn_id: "1",
  conversation_id: "1",
  request_id: "1",
  status: "completed",
  intent: "generate",
  message: "Ready",
  sql: null,
  explanation: null,
  diagnostics: [],
  clarification: null,
  optimization: null,
  error: null,
  meta: { total_duration_ms: 1, execution_available: false },
} satisfies TurnResponse;
describe("query output boundaries", () => {
  it("does not show executable controls for a refusal", () => {
    render(
      <OutputPanel
        response={{ ...base, status: "refused" }}
        busy={false}
        onError={() => {}}
        onToast={() => {}}
        onBusy={() => {}}
      />,
    );
    expect(
      screen.queryByRole("button", { name: "Copy SQL" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Keeping your workspace focused"),
    ).toBeInTheDocument();
  });
  it("only executes after an explicit click and preserves null cells", async () => {
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            execution_id: "e",
            columns: [{ name: "value", type: "null" }],
            rows: [[null]],
            returned_row_count: 1,
            truncated: false,
            limit: 200,
            duration_ms: 1,
          }),
        ),
      );
    render(
      <OutputPanel
        response={{
          ...base,
          sql: {
            artifact_id: "a",
            text: "SELECT '<script>alert(1)</script>' FROM customers",
            dialect: "sqlite",
            schema_version: "v1",
            validation: "passed",
          },
        }}
        busy={false}
        onError={() => {}}
        onToast={() => {}}
        onBusy={() => {}}
      />,
    );
    expect(fetch).not.toHaveBeenCalled();
    expect(document.querySelector("script")).toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: "Run query" }),
    );
    await waitFor(() => expect(screen.getByText("NULL")).toBeInTheDocument());
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
