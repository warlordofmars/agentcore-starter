// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ErrorBoundary from "./ErrorBoundary.jsx";

function Boom() {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  let consoleError;

  beforeEach(() => {
    // React logs the caught error to console.error; silence it so the
    // test output stays readable.
    consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it("renders children when no error is thrown", async () => {
    await act(async () =>
      render(
        <ErrorBoundary>
          <p>healthy</p>
        </ErrorBoundary>,
      ),
    );
    expect(screen.getByText("healthy")).toBeTruthy();
    expect(screen.queryByTestId("error-boundary")).toBeNull();
  });

  it("catches a thrown render error and shows the friendly fallback", async () => {
    await act(async () =>
      render(
        <ErrorBoundary>
          <Boom />
        </ErrorBoundary>,
      ),
    );
    const fallback = screen.getByTestId("error-boundary");
    expect(fallback).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeTruthy();
    // Reload + Contact support paths must both be visible.
    expect(screen.getByRole("button", { name: "Reload page" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Contact support" })).toBeTruthy();
    // componentDidCatch logged the error with our specific prefix.
    // React itself also logs caught errors to console.error, so we
    // can't just assert the spy was called — distinguish on the
    // "ErrorBoundary caught:" prefix to confirm our handler ran.
    expect(
      consoleError.mock.calls.some(
        ([firstArg]) =>
          typeof firstArg === "string" && firstArg.includes("ErrorBoundary caught:"),
      ),
    ).toBe(true);
  });

  it("calls window.location.reload when the Reload button is clicked", async () => {
    const reload = vi.fn();
    vi.stubGlobal("location", { reload });

    await act(async () =>
      render(
        <ErrorBoundary>
          <Boom />
        </ErrorBoundary>,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Reload page" }));
    expect(reload).toHaveBeenCalledTimes(1);

    vi.unstubAllGlobals();
  });

  it("treats undefined error.message as empty without crashing", async () => {
    // Defensive — covers the `error?.message ?? ""` branch in
    // getDerivedStateFromError.
    function ThrowsUndefined() {
      // eslint-disable-next-line no-throw-literal
      throw undefined;
    }
    await act(async () =>
      render(
        <ErrorBoundary>
          <ThrowsUndefined />
        </ErrorBoundary>,
      ),
    );
    expect(screen.getByTestId("error-boundary")).toBeTruthy();
  });
});
