import { describe, it, expect } from "vitest";
import { SEVERITY_BADGE, SEVERITY_CHART, SEVERITY_BADGE_FALLBACK } from "./colors";

describe("severity colors", () => {
  it("heeft badge-klassen voor de bekende severities", () => {
    expect(SEVERITY_BADGE.Error).toContain("red");
    expect(SEVERITY_BADGE.Warning).toContain("yellow");
    expect(SEVERITY_BADGE.Info).toContain("blue");
  });

  it("heeft hex-kleuren voor de grafieken", () => {
    expect(SEVERITY_CHART.Error).toMatch(/^#[0-9a-fA-F]{6}$/);
  });

  it("heeft een fallback-badge", () => {
    expect(SEVERITY_BADGE_FALLBACK).toBeTruthy();
  });
});
