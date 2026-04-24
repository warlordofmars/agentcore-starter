// Copyright (c) 2026 John Carter. All rights reserved.
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({
  Toaster: ({ theme, richColors }) => (
    <div data-testid="sonner-toaster" data-theme={theme} data-rich={String(richColors)} />
  ),
}));

import { Toaster } from "./sonner.jsx";

describe("Toaster", () => {
  it("renders the Sonner Toaster with system theme", () => {
    const { getByTestId } = render(<Toaster />);
    const el = getByTestId("sonner-toaster");
    expect(el.getAttribute("data-theme")).toBe("system");
    expect(el.getAttribute("data-rich")).toBe("true");
  });

  it("passes extra props to Sonner Toaster", () => {
    const { getByTestId } = render(<Toaster position="bottom-right" />);
    expect(getByTestId("sonner-toaster")).toBeTruthy();
  });
});
