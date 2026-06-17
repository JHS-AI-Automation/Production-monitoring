import { describe, it, expect } from "vitest";
import {
  MACHINE_STATES,
  REASON_GROUPS,
  statesByReason,
  stateByCode,
} from "./machineStates";

describe("machine states (PackML)", () => {
  it("dekt alle 17 codes precies één keer", () => {
    const codes = MACHINE_STATES.map((s) => s.code).sort((a, b) => a - b);
    expect(codes).toEqual(Array.from({ length: 17 }, (_, i) => i + 1));
  });

  it("heeft geldige hex-kleuren voor elke toestand", () => {
    for (const s of MACHINE_STATES) {
      expect(s.color).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  it("merkt alleen Execute aan als productief", () => {
    const produceert = statesByReason("produceert");
    expect(produceert).toHaveLength(1);
    expect(produceert[0].name).toBe("Execute");
    expect(produceert[0].code).toBe(6);
  });

  it("verdeelt elke toestand over precies één reden-groep", () => {
    const total = REASON_GROUPS.reduce(
      (sum, g) => sum + statesByReason(g.reason).length,
      0,
    );
    expect(total).toBe(MACHINE_STATES.length);
  });

  it("classificeert storing en blokkade volgens PackML-semantiek", () => {
    expect(statesByReason("storing").map((s) => s.code).sort((a, b) => a - b)).toEqual([8, 9]);
    // Suspended-familie = externe stop (geen aanvoer), niet verward met operator-pauze (Held).
    expect(statesByReason("geblokkeerd").map((s) => s.name)).toContain("Suspended");
    expect(statesByReason("pauze").map((s) => s.name)).toContain("Held");
  });

  it("zoekt een toestand op code", () => {
    expect(stateByCode(2)?.name).toBe("Stopped");
    expect(stateByCode(99)).toBeUndefined();
  });
});
