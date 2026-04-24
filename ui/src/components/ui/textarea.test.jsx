// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Textarea } from "./textarea.jsx";

describe("Textarea", () => {
  it("renders a textarea element", () => {
    render(<Textarea placeholder="Enter content" />);
    expect(screen.getByPlaceholderText("Enter content")).toBeTruthy();
  });

  it("merges extra className", () => {
    render(<Textarea className="extra" placeholder="x" />);
    expect(screen.getByPlaceholderText("x").className).toContain("extra");
  });

  it("passes extra props", () => {
    render(<Textarea data-testid="my-textarea" />);
    expect(screen.getByTestId("my-textarea")).toBeTruthy();
  });

  it("forwards ref", () => {
    const ref = { current: null };
    render(<Textarea ref={ref} placeholder="ref-area" />);
    expect(ref.current).toBeTruthy();
    expect(ref.current.tagName).toBe("TEXTAREA");
  });
});
