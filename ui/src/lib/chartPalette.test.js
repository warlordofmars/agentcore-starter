// Copyright (c) 2026 John Carter. All rights reserved.
import { describe, expect, it } from "vitest";
import { SLICE_COLORS } from "./chartPalette.js";

describe("SLICE_COLORS", () => {
  it("exports an 8-slot palette of hex strings", () => {
    // Eight slots cover the ranked slice colours consumed by
    // TagDistribution and ClientContribution (the "Other" bucket uses
    // OTHER_COLOR, not SLICE_COLORS) — keeping the length locked
    // prevents a silent reshuffle if a colour is ever inserted in the
    // middle.
    expect(SLICE_COLORS).toHaveLength(8);
    for (const c of SLICE_COLORS) {
      expect(c).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it("leads with the brand orange so the primary slice always reads consistently", () => {
    expect(SLICE_COLORS[0]).toBe("#e8a020");
  });
});
