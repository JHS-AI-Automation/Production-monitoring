import { describe, it, expect } from "vitest";
import { formatTime, formatDate } from "./format";

describe("format helpers", () => {
  it("formatTime geeft '-' bij null", () => {
    expect(formatTime(null)).toBe("-");
  });

  it("formatTime bevat standaard seconden", () => {
    expect(formatTime("2026-06-01T13:05:09")).toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  it("formatTime zonder seconden", () => {
    expect(formatTime("2026-06-01T13:05:09", { seconds: false })).toMatch(/^\d{2}:\d{2}$/);
  });

  it("formatDate gebruikt de meegegeven opties (nl-NL)", () => {
    const out = formatDate("2026-06-01", { day: "numeric", month: "long" });
    expect(out.toLowerCase()).toContain("juni");
  });
});
