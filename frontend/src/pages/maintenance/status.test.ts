import { describe, it, expect } from "vitest";
import { statusMeta } from "./status";

describe("statusMeta", () => {
  it("mapt bekende statussen naar labels", () => {
    expect(statusMeta("alarm").label).toBe("Alarm");
    expect(statusMeta("warn").label).toBe("Let op");
    expect(statusMeta("ok").label).toBe("Stabiel");
  });

  it("valt terug op Onbekend bij een onbekende status", () => {
    expect(statusMeta("zzz").label).toBe("Onbekend");
    expect(statusMeta("unknown").label).toBe("Onbekend");
  });
});
