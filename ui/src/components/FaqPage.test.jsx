// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import FaqPage from "./FaqPage.jsx";

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("FaqPage", () => {
  it("renders the heading", async () => {
    await act(async () => renderInRouter(<FaqPage />));
    expect(screen.getByText(/Frequently asked questions/)).toBeTruthy();
  });

  it("renders all FAQ questions", async () => {
    await act(async () => renderInRouter(<FaqPage />));
    expect(screen.getByText(/Is my data private/)).toBeTruthy();
    expect(screen.getByText(/What are the usage limits/)).toBeTruthy();
    expect(screen.getByText(/Which MCP clients are supported/)).toBeTruthy();
    expect(screen.getByText(/How do I delete my account/)).toBeTruthy();
    expect(screen.getByText(/What happens if the service goes down/)).toBeTruthy();
    expect(screen.getByText(/Is this free forever/)).toBeTruthy();
    expect(screen.getByText(/How do I connect my MCP client/)).toBeTruthy();
    expect(screen.getByText(/Does Hive work offline/)).toBeTruthy();
  });

  it("answers are hidden by default", async () => {
    await act(async () => renderInRouter(<FaqPage />));
    expect(screen.queryByText(/Your memories are scoped to your account/)).toBeFalsy();
  });

  it("clicking a question reveals the answer", async () => {
    await act(async () => renderInRouter(<FaqPage />));
    fireEvent.click(screen.getByText(/Is my data private/));
    expect(screen.getByText(/Your memories are scoped to your account/)).toBeTruthy();
  });

  it("clicking an open question hides the answer again", async () => {
    await act(async () => renderInRouter(<FaqPage />));
    const btn = screen.getByText(/Is my data private/).closest("button");
    fireEvent.click(btn);
    expect(screen.getByText(/Your memories are scoped to your account/)).toBeTruthy();
    fireEvent.click(btn);
    expect(screen.queryByText(/Your memories are scoped to your account/)).toBeFalsy();
  });

  it("multiple questions can be open simultaneously", async () => {
    await act(async () => renderInRouter(<FaqPage />));
    fireEvent.click(screen.getByText(/Is my data private/));
    fireEvent.click(screen.getByText(/What are the usage limits/));
    expect(screen.getByText(/Your memories are scoped to your account/)).toBeTruthy();
    expect(screen.getByText(/up to 500 memories/)).toBeTruthy();
  });

  it("renders docs link", async () => {
    await act(async () => renderInRouter(<FaqPage />));
    expect(screen.getByText(/Read the docs/)).toBeTruthy();
  });
});
