// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import EmptyState from "./EmptyState.jsx";

describe("EmptyState", () => {
  it("renders title", () => {
    render(<EmptyState variant="memories" title="No memories yet" />);
    expect(screen.getByText("No memories yet")).toBeTruthy();
  });

  it("renders description when provided", () => {
    render(<EmptyState variant="clients" title="No clients" description="Register one to get started." />);
    expect(screen.getByText("Register one to get started.")).toBeTruthy();
  });

  it("does not render description when omitted", () => {
    const { container } = render(<EmptyState variant="activity" title="No activity" />);
    expect(container.querySelectorAll("p").length).toBe(1); // only title
  });

  it("renders action when provided", () => {
    render(<EmptyState variant="users" title="No users" action={<button>Add</button>} />);
    expect(screen.getByText("Add")).toBeTruthy();
  });

  it("renders all four variants without error", () => {
    for (const variant of ["memories", "clients", "activity", "users"]) {
      const { container, unmount } = render(<EmptyState variant={variant} title="Test" />);
      expect(container.querySelector("svg")).toBeTruthy();
      unmount();
    }
  });

  it("falls back to memories illustration for unknown variant", () => {
    const { container } = render(<EmptyState variant="unknown" title="Test" />);
    expect(container.querySelector("svg")).toBeTruthy();
  });
});
