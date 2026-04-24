// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Input } from "./input.jsx";

describe("Input", () => {
  it("renders an input element", () => {
    render(<Input placeholder="Enter text" />);
    expect(screen.getByPlaceholderText("Enter text")).toBeTruthy();
  });

  it("merges extra className", () => {
    render(<Input className="extra" placeholder="x" />);
    expect(screen.getByPlaceholderText("x").className).toContain("extra");
  });

  it("passes extra props", () => {
    render(<Input data-testid="my-input" />);
    expect(screen.getByTestId("my-input")).toBeTruthy();
  });

  it("forwards ref", () => {
    const ref = { current: null };
    render(<Input ref={ref} placeholder="ref-input" />);
    expect(ref.current).toBeTruthy();
    expect(ref.current.tagName).toBe("INPUT");
  });
});
