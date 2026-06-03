import { describe, it, expect } from "vitest";
import { isoDate, today, yesterday, rangeEndingYesterday } from "./date";

describe("date helpers", () => {
  it("isoDate geeft YYYY-MM-DD", () => {
    expect(isoDate(new Date("2026-06-01T10:00:00Z"))).toBe("2026-06-01");
  });

  it("yesterday ligt één dag voor today", () => {
    const diffDays = Math.round(
      (new Date(today()).getTime() - new Date(yesterday()).getTime()) / 86_400_000,
    );
    expect(diffDays).toBe(1);
  });

  it("rangeEndingYesterday eindigt op gisteren en beslaat het juiste aantal dagen", () => {
    const { from, to } = rangeEndingYesterday(7);
    expect(to).toBe(yesterday());
    const spanDays = Math.round(
      (new Date(to).getTime() - new Date(from).getTime()) / 86_400_000,
    );
    expect(spanDays).toBe(6); // 7 dagen inclusief -> verschil van 6
  });
});
