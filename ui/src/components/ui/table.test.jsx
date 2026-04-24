// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./table.jsx";

describe("Table components", () => {
  function BasicTable() {
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>foo</TableCell>
            <TableCell>bar</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
  }

  it("renders a table with header and body", () => {
    render(<BasicTable />);
    expect(screen.getByText("Name")).toBeTruthy();
    expect(screen.getByText("foo")).toBeTruthy();
    expect(screen.getByText("bar")).toBeTruthy();
  });

  it("Table merges className", () => {
    const { container } = render(<Table className="extra"><tbody /></Table>);
    expect(container.firstChild.className).toContain("extra");
  });

  it("TableRow merges className", () => {
    const { container } = render(
      <table><tbody><TableRow className="extra"><td>x</td></TableRow></tbody></table>,
    );
    expect(container.querySelector("tr").className).toContain("extra");
  });

  it("TableHead merges className", () => {
    const { container } = render(
      <table><thead><tr><TableHead className="extra">H</TableHead></tr></thead></table>,
    );
    expect(container.querySelector("th").className).toContain("extra");
  });

  it("TableCell merges className", () => {
    const { container } = render(
      <table><tbody><tr><TableCell className="extra">C</TableCell></tr></tbody></table>,
    );
    expect(container.querySelector("td").className).toContain("extra");
  });
});
