// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import McpClientsPage from "./McpClientsPage.jsx";

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

// jsdom doesn't implement clipboard API
Object.assign(navigator, {
  clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
});

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("McpClientsPage", () => {
  it("renders the heading", async () => {
    await act(async () => renderInRouter(<McpClientsPage />));
    expect(screen.getByText(/MCP client compatibility/)).toBeTruthy();
  });

  it("renders all client cards", async () => {
    await act(async () => renderInRouter(<McpClientsPage />));
    expect(screen.getByText("Claude Code")).toBeTruthy();
    expect(screen.getByText("Claude Desktop")).toBeTruthy();
    expect(screen.getByText("Cursor")).toBeTruthy();
    expect(screen.getByText("Continue")).toBeTruthy();
  });

  it("renders config snippets for each client", async () => {
    const { container } = await act(async () => renderInRouter(<McpClientsPage />));
    const snippets = container.querySelectorAll("pre");
    // Claude Code, Claude Desktop, ChatGPT, Cursor, Continue
    expect(snippets.length).toBe(5);
  });

  it("renders Copy buttons", async () => {
    await act(async () => renderInRouter(<McpClientsPage />));
    const copyBtns = screen.getAllByText("Copy");
    expect(copyBtns.length).toBe(5);
  });

  it("renders ChatGPT card", async () => {
    await act(async () => renderInRouter(<McpClientsPage />));
    expect(screen.getByText("ChatGPT")).toBeTruthy();
  });

  it("clicking Copy calls clipboard and shows Copied!", async () => {
    await act(async () => renderInRouter(<McpClientsPage />));
    const copyBtn = screen.getAllByText("Copy")[0];
    await act(async () => fireEvent.click(copyBtn));
    expect(navigator.clipboard.writeText).toHaveBeenCalled();
    expect(screen.getAllByText("Copied!").length).toBeGreaterThanOrEqual(1);
  });

  it("renders docs link", async () => {
    await act(async () => renderInRouter(<McpClientsPage />));
    expect(screen.getByText("docs")).toBeTruthy();
  });
});
