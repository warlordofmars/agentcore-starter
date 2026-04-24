// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Select } from "./select.jsx";

describe("Select", () => {
  it("renders a select element with options", () => {
    render(
      <Select aria-label="Choose">
        <option value="a">Option A</option>
        <option value="b">Option B</option>
      </Select>,
    );
    expect(screen.getByRole("combobox")).toBeTruthy();
    expect(screen.getByText("Option A")).toBeTruthy();
  });

  it("merges extra className", () => {
    render(
      <Select className="extra" aria-label="x">
        <option>x</option>
      </Select>,
    );
    expect(screen.getByRole("combobox").className).toContain("extra");
  });

  it("passes extra props", () => {
    render(
      <Select data-testid="my-select">
        <option>y</option>
      </Select>,
    );
    expect(screen.getByTestId("my-select")).toBeTruthy();
  });

  it("forwards ref", () => {
    const ref = { current: null };
    render(
      <Select ref={ref} aria-label="ref-select">
        <option>z</option>
      </Select>,
    );
    expect(ref.current).toBeTruthy();
    expect(ref.current.tagName).toBe("SELECT");
  });
});
