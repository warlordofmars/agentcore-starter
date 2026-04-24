// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import UseCasesPage from "./UseCasesPage.jsx";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("UseCasesPage", () => {
  it("renders the heading", async () => {
    await act(async () => renderInRouter(<UseCasesPage />));
    expect(screen.getByText(/What can you do with Hive/)).toBeTruthy();
  });

  it("renders all use case titles", async () => {
    await act(async () => renderInRouter(<UseCasesPage />));
    expect(screen.getByText(/Remember project context/)).toBeTruthy();
    expect(screen.getByText(/Share team knowledge/)).toBeTruthy();
    expect(screen.getByText(/Persistent preferences/)).toBeTruthy();
    expect(screen.getByText(/Cross-tool memory/)).toBeTruthy();
  });

  it("renders code snippets", async () => {
    const { container } = await act(async () => renderInRouter(<UseCasesPage />));
    const snippets = container.querySelectorAll("pre");
    expect(snippets.length).toBe(4);
  });

  it("renders CTA button", async () => {
    await act(async () => renderInRouter(<UseCasesPage />));
    expect(screen.getByText(/Get started free/)).toBeTruthy();
  });

  it("CTA navigates to /app", async () => {
    await act(async () => renderInRouter(<UseCasesPage />));
    fireEvent.click(screen.getByText(/Get started free →/));
    expect(mockNavigate).toHaveBeenCalledWith("/app");
  });
});
