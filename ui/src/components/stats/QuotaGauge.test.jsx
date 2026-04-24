// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import QuotaGauge, { arcPath, fillColor } from "./QuotaGauge.jsx";

describe("arcPath", () => {
  it("starts at the left edge of the semicircle", () => {
    // fraction 0 → degenerate arc but should still start at (20, 90).
    expect(arcPath(0)).toMatch(/^M 20 90 /);
  });

  it("traces to the right edge at fraction 1", () => {
    const path = arcPath(1);
    expect(path).toContain("M 20 90");
    // End X for a semicircle at fraction 1 should be 160 (CENTER_X + R).
    expect(path).toMatch(/160\.00 90\.00/);
  });

  it("clamps inputs outside [0, 1]", () => {
    expect(arcPath(-0.5)).toBe(arcPath(0));
    expect(arcPath(1.5)).toBe(arcPath(1));
  });

  it("switches to the large-arc flag past the halfway mark", () => {
    // <= 0.5 → large-arc flag 0; > 0.5 → 1.
    expect(arcPath(0.4)).toMatch(/0 0 1/);
    expect(arcPath(0.6)).toMatch(/0 1 1/);
  });
});

describe("fillColor", () => {
  it("returns accent for low usage", () => {
    expect(fillColor(0.5)).toBe("var(--accent)");
  });

  it("returns the amber theme token in the 75–90% band", () => {
    expect(fillColor(0.8)).toBe("var(--amber)");
  });

  it("returns danger at/above 90%", () => {
    expect(fillColor(0.9)).toBe("var(--danger)");
    expect(fillColor(1.0)).toBe("var(--danger)");
  });
});

describe("QuotaGauge", () => {
  it("returns null when quota is missing", () => {
    const { container } = render(<QuotaGauge />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null when memory_count is not a number", () => {
    const { container } = render(<QuotaGauge quota={{ memory_count: "oops", memory_limit: 100 }} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a plain count when memory_limit is null (admin/exempt)", () => {
    render(<QuotaGauge quota={{ memory_count: 42, memory_limit: null }} />);
    expect(screen.getByTestId("quota-gauge-unbounded")).toBeTruthy();
    expect(screen.getByText("42")).toBeTruthy();
    expect(screen.getByText(/no quota/i)).toBeTruthy();
  });

  it("renders a gauge + count / limit + remaining when both set", () => {
    render(<QuotaGauge quota={{ memory_count: 40, memory_limit: 100 }} />);
    expect(screen.getByText("40")).toBeTruthy();
    expect(screen.getByText("/ 100")).toBeTruthy();
    expect(screen.getByText(/60 remaining/)).toBeTruthy();
  });

  it("handles memory_limit of 0 without dividing by zero", () => {
    render(<QuotaGauge quota={{ memory_count: 5, memory_limit: 0 }} />);
    // No NaN rendered; 0 remaining.
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText(/0 remaining/)).toBeTruthy();
  });

  it("renders storage row when storage_bytes is provided", () => {
    render(
      <QuotaGauge
        quota={{
          memory_count: 10,
          memory_limit: 100,
          storage_bytes: 1048576,
          storage_bytes_limit: 104857600,
        }}
      />
    );
    expect(screen.getByTestId("storage-row")).toBeTruthy();
    const bar = screen.getByTestId("storage-bar");
    expect(bar).toBeTruthy();
    expect(bar.getAttribute("role")).toBe("progressbar");
    expect(bar.getAttribute("aria-valuemin")).toBe("0");
    expect(bar.getAttribute("aria-valuemax")).toBe("100");
    expect(bar.getAttribute("aria-valuenow")).toBe("1");
    // 1 MB / 100 MB
    expect(screen.getByText(/Storage/)).toBeTruthy();
  });

  it("does not render storage row when storage_bytes is absent", () => {
    render(<QuotaGauge quota={{ memory_count: 10, memory_limit: 100 }} />);
    expect(screen.queryByTestId("storage-row")).toBeNull();
  });

  it("renders storage row in unbounded mode with storage_bytes", () => {
    render(
      <QuotaGauge
        quota={{ memory_count: 5, memory_limit: null, storage_bytes: 2097152 }}
      />
    );
    expect(screen.getByTestId("storage-unbounded")).toBeTruthy();
  });

  it("omits storage bar when storage_bytes_limit is null", () => {
    render(
      <QuotaGauge
        quota={{
          memory_count: 10,
          memory_limit: 100,
          storage_bytes: 1024,
          storage_bytes_limit: null,
        }}
      />
    );
    expect(screen.getByTestId("storage-row")).toBeTruthy();
    expect(screen.queryByTestId("storage-bar")).toBeNull();
  });

  it("clamps storage bar at 100% when over limit", () => {
    const { container } = render(
      <QuotaGauge
        quota={{
          memory_count: 10,
          memory_limit: 100,
          storage_bytes: 200 * 1024 * 1024,
          storage_bytes_limit: 100 * 1024 * 1024,
        }}
      />
    );
    const bar = container.querySelector("[data-testid='storage-bar']");
    expect(bar.style.width).toBe("100%");
  });

  it("renders storage bar at 0% when storage_bytes_limit is 0", () => {
    const { container } = render(
      <QuotaGauge
        quota={{
          memory_count: 10,
          memory_limit: 100,
          storage_bytes: 1024,
          storage_bytes_limit: 0,
        }}
      />
    );
    const bar = container.querySelector("[data-testid='storage-bar']");
    expect(bar.style.width).toBe("0%");
  });
});
