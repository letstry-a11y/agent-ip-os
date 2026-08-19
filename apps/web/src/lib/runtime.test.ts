import { describe, expect, it } from "vitest";

import { runtimeBoundary } from "./runtime";

describe("runtimeBoundary", () => {
  it("keeps external effects disabled in the M0 baseline", () => {
    expect(runtimeBoundary).toEqual({
      providerMode: "mock",
      platformMode: "package-only",
      externalSideEffectsEnabled: false,
    });
  });
});
