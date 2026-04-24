// Copyright (c) 2026 John Carter. All rights reserved.
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Skeleton } from "./skeleton.jsx";

describe("Skeleton", () => {
  it("renders a div with animate-pulse class", () => {
    const { container } = render(<Skeleton />);
    expect(container.firstChild.className).toContain("animate-pulse");
  });

  it("merges extra className", () => {
    const { container } = render(<Skeleton className="w-32 h-6" />);
    expect(container.firstChild.className).toContain("w-32");
    expect(container.firstChild.className).toContain("h-6");
  });

  it("sets aria-hidden", () => {
    const { container } = render(<Skeleton />);
    expect(container.firstChild.getAttribute("aria-hidden")).toBe("true");
  });
});
