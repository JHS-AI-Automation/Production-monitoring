import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorBoundary from "./ErrorBoundary";

function Boom(): never {
  throw new Error("kapot");
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // fetch (foutrapportage) stubben en React's error-console dempen.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("toont de children als er geen fout is", () => {
    render(
      <ErrorBoundary>
        <p>alles goed</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("alles goed")).toBeInTheDocument();
  });

  it("toont een nette fallback bij een render-fout", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Er ging iets mis")).toBeInTheDocument();
    expect(screen.getByText("kapot")).toBeInTheDocument();
  });

  it("rapporteert de fout naar /api/client-log", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(fetch).toHaveBeenCalledWith("/api/client-log", expect.objectContaining({ method: "POST" }));
  });
});
