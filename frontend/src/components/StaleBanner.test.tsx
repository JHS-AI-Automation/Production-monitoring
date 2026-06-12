import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import StaleBanner from "./StaleBanner";

const noop = () => undefined;

describe("StaleBanner", () => {
  it("rendert niets wanneer de data vers is", () => {
    const { container } = render(
      <StaleBanner stale={false} refreshFailed={false} lastUpdated={Date.now()} onRetry={noop} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("toont het tijdstip van de getoonde data en de achtergrond-melding", () => {
    const tien_uur = new Date(2026, 5, 12, 10, 0).getTime();
    render(
      <StaleBanner stale={true} refreshFailed={false} lastUpdated={tien_uur} onRetry={noop} />,
    );
    expect(screen.getByText(/eerder opgehaalde gegevens/)).toBeInTheDocument();
    expect(screen.getByText(/10:00/)).toBeInTheDocument();
    expect(screen.getByText(/achtergrond/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("toont een retry-knop wanneer verversen mislukte", () => {
    const onRetry = vi.fn();
    render(
      <StaleBanner stale={true} refreshFailed={true} lastUpdated={Date.now()} onRetry={onRetry} />,
    );
    expect(screen.getByText(/Vernieuwen lukte zojuist niet/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Opnieuw proberen/ }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
