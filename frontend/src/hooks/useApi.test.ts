import { describe, expect, it } from "vitest";
import { combineApi, type ApiState } from "./useApi";

function state(overrides: Partial<ApiState> = {}): ApiState {
  return {
    loading: false,
    error: null,
    stale: false,
    refreshFailed: false,
    lastUpdated: null,
    retry: () => undefined,
    ...overrides,
  };
}

describe("combineApi", () => {
  it("is stale zodra één van de bronnen stale is", () => {
    const combined = combineApi(state(), state({ stale: true }), state());
    expect(combined.stale).toBe(true);
    expect(combined.refreshFailed).toBe(false);
  });

  it("meldt refreshFailed zodra één achtergrond-refresh faalde", () => {
    const combined = combineApi(state(), state({ refreshFailed: true, stale: true }));
    expect(combined.refreshFailed).toBe(true);
  });

  it("neemt de OUDSTE lastUpdated (conservatief: data nooit verser voordoen)", () => {
    const combined = combineApi(
      state({ lastUpdated: 2_000 }),
      state({ lastUpdated: 1_000 }),
      state({ lastUpdated: null }),
    );
    expect(combined.lastUpdated).toBe(1_000);
  });

  it("geeft null lastUpdated wanneer geen enkele bron data heeft", () => {
    expect(combineApi(state(), state()).lastUpdated).toBeNull();
  });

  it("retryAll roept elke retry aan", () => {
    let calls = 0;
    const combined = combineApi(
      state({ retry: () => { calls += 1; } }),
      state({ retry: () => { calls += 1; } }),
    );
    combined.retryAll();
    expect(calls).toBe(2);
  });
});
