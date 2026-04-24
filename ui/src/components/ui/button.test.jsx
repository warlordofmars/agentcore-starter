// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeTruthy();
  });

  it("calls onClick when clicked", () => {
    const handler = vi.fn();
    render(<Button onClick={handler}>Go</Button>);
    fireEvent.click(screen.getByText("Go"));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("is disabled when disabled prop set", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByText("Disabled").closest("button")).toBeDisabled();
  });

  it("renders as Slot when asChild is true", () => {
    render(
      <Button asChild>
        <a href="/test">Link button</a>
      </Button>
    );
    const link = screen.getByText("Link button");
    expect(link.tagName.toLowerCase()).toBe("a");
  });

  it("applies variant classes", () => {
    const { container } = render(<Button variant="brand">Brand</Button>);
    expect(container.firstChild.className).toContain("bg-brand");
  });

  it("applies size classes", () => {
    const { container } = render(<Button size="lg">Large</Button>);
    expect(container.firstChild.className).toContain("px-9");
  });

  it("merges custom className", () => {
    const { container } = render(<Button className="custom-class">Custom</Button>);
    expect(container.firstChild.className).toContain("custom-class");
  });

  it("renders all variants without error", () => {
    const variants = ["default", "brand", "outline", "ghost", "danger", "secondary", "nav"];
    variants.forEach((variant) => {
      const { unmount } = render(<Button variant={variant}>{variant}</Button>);
      expect(screen.getByText(variant)).toBeTruthy();
      unmount();
    });
  });

  it("renders all sizes without error", () => {
    const sizes = ["default", "sm", "lg", "icon"];
    sizes.forEach((size) => {
      const { unmount } = render(<Button size={size}>{size}</Button>);
      expect(screen.getByText(size)).toBeTruthy();
      unmount();
    });
  });
});
