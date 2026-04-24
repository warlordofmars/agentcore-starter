// Copyright (c) 2026 John Carter. All rights reserved.
import { act, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SubprocessorsPage from "./SubprocessorsPage.jsx";

function renderInRouter() {
  return render(
    <MemoryRouter>
      <SubprocessorsPage />
    </MemoryRouter>,
  );
}

describe("SubprocessorsPage", () => {
  it("renders heading and last-updated date", async () => {
    await act(async () => renderInRouter());
    expect(screen.getByRole("heading", { name: "Subprocessors" })).toBeTruthy();
    expect(screen.getByText(/Last updated: April 2026/)).toBeTruthy();
  });

  it("lists each current subprocessor in the table", async () => {
    const { container } = await act(async () => renderInRouter());
    const table = container.querySelector("table");
    expect(table).not.toBeNull();
    const tableBody = within(table);
    // AWS + two Google entries expected
    expect(tableBody.getAllByText("Amazon Web Services")).toHaveLength(1);
    expect(tableBody.getAllByText("Google LLC").length).toBeGreaterThanOrEqual(2);
    expect(
      tableBody.getByText("Google OAuth 2.0"),
    ).toBeTruthy();
    expect(
      tableBody.getByText("Google Analytics 4"),
    ).toBeTruthy();
    expect(
      tableBody.getByText(/DynamoDB, Lambda/),
    ).toBeTruthy();
    expect(tableBody.getByText("us-east-1 (United States)")).toBeTruthy();
  });

  it("renders column headers", async () => {
    await act(async () => renderInRouter());
    expect(screen.getByText("Subprocessor")).toBeTruthy();
    expect(screen.getByText("Purpose")).toBeTruthy();
    expect(screen.getByText("Data processed")).toBeTruthy();
    expect(screen.getByText("Location")).toBeTruthy();
  });

  it("includes the change-notification commitment", async () => {
    await act(async () => renderInRouter());
    expect(screen.getByText(/Notification of changes/)).toBeTruthy();
    expect(screen.getByText(/30 days' advance notice/)).toBeTruthy();
  });

  it("links back to the Privacy Policy", async () => {
    const { container } = await act(async () => renderInRouter());
    const main = container.querySelector("main");
    const link = within(main).getByText("Privacy Policy");
    expect(link.getAttribute("href")).toBe("/privacy");
  });
});
