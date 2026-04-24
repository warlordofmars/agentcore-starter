// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Label } from "./label.jsx";

describe("Label", () => {
  it("renders children", () => {
    render(<Label>My Label</Label>);
    expect(screen.getByText("My Label")).toBeTruthy();
  });

  it("merges extra className", () => {
    const { container } = render(<Label className="extra">x</Label>);
    expect(container.firstChild.className).toContain("extra");
  });

  it("passes htmlFor prop", () => {
    render(<Label htmlFor="my-input">Label text</Label>);
    expect(screen.getByText("Label text").htmlFor).toBe("my-input");
  });
});
