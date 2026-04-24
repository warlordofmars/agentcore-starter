// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MemoryDiff from "./MemoryDiff.jsx";

describe("MemoryDiff", () => {
  it("renders the diff container with the test id anchor", () => {
    render(<MemoryDiff before="hello" after="hello" />);
    expect(screen.getByTestId("memory-diff")).toBeTruthy();
  });

  it("renders additions in an <ins> element", () => {
    const { container } = render(
      <MemoryDiff before="hello world" after="hello beautiful world" />,
    );
    const ins = container.querySelector("ins");
    expect(ins).not.toBeNull();
    expect(ins.textContent).toContain("beautiful");
  });

  it("renders removals in a <del> element", () => {
    const { container } = render(
      <MemoryDiff before="hello old world" after="hello world" />,
    );
    const del = container.querySelector("del");
    expect(del).not.toBeNull();
    expect(del.textContent).toContain("old");
  });

  it("renders unchanged text without ins/del markup", () => {
    const { container } = render(
      <MemoryDiff before="shared text" after="shared text" />,
    );
    expect(container.querySelector("ins")).toBeNull();
    expect(container.querySelector("del")).toBeNull();
    expect(container.textContent).toContain("shared text");
  });

  it("falls back to empty-string when before is null/undefined", () => {
    const { container } = render(<MemoryDiff before={null} after="new" />);
    // Entire text is an addition — rendered inside <ins>.
    expect(container.querySelector("ins")?.textContent).toContain("new");
  });

  it("falls back to empty-string when after is null/undefined", () => {
    const { container } = render(<MemoryDiff before="old" after={undefined} />);
    // Entire text is a removal — rendered inside <del>.
    expect(container.querySelector("del")?.textContent).toContain("old");
  });
});
