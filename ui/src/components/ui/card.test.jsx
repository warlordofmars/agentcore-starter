// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "./card.jsx";

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Hello</Card>);
    expect(screen.getByText("Hello")).toBeTruthy();
  });

  it("merges extra className", () => {
    const { container } = render(<Card className="extra">x</Card>);
    expect(container.firstChild.className).toContain("extra");
  });

  it("passes extra props", () => {
    render(<Card data-testid="my-card">x</Card>);
    expect(screen.getByTestId("my-card")).toBeTruthy();
  });
});

describe("CardHeader", () => {
  it("renders children", () => {
    render(<CardHeader>Header</CardHeader>);
    expect(screen.getByText("Header")).toBeTruthy();
  });
});

describe("CardTitle", () => {
  it("renders children", () => {
    render(<CardTitle>Title</CardTitle>);
    expect(screen.getByText("Title")).toBeTruthy();
  });
});

describe("CardContent", () => {
  it("renders children", () => {
    render(<CardContent>Content</CardContent>);
    expect(screen.getByText("Content")).toBeTruthy();
  });
});

describe("CardFooter", () => {
  it("renders children", () => {
    render(<CardFooter>Footer</CardFooter>);
    expect(screen.getByText("Footer")).toBeTruthy();
  });
});
