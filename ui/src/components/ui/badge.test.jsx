// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./badge.jsx";

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>memory_created</Badge>);
    expect(screen.getByText("memory_created")).toBeTruthy();
  });

  it("merges extra className", () => {
    const { container } = render(<Badge className="extra">x</Badge>);
    expect(container.firstChild.className).toContain("extra");
  });

  it("passes style prop through", () => {
    const { container } = render(<Badge style={{ color: "red" }}>x</Badge>);
    expect(container.firstChild.style.color).toBe("red");
  });

  it("passes extra props", () => {
    render(<Badge data-testid="my-badge">x</Badge>);
    expect(screen.getByTestId("my-badge")).toBeTruthy();
  });
});
