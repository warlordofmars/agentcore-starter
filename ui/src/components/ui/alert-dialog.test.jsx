// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AlertDialog } from "./alert-dialog.jsx";

describe("AlertDialog", () => {
  it("renders title and description when open", () => {
    render(
      <AlertDialog
        open
        title="Delete item?"
        description="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("Delete item?")).toBeTruthy();
    expect(screen.getByText("This cannot be undone.")).toBeTruthy();
  });

  it("does not render when closed", () => {
    render(
      <AlertDialog
        open={false}
        title="Delete item?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByText("Delete item?")).toBeNull();
  });

  it("calls onConfirm when confirm button clicked", async () => {
    const onConfirm = vi.fn();
    render(
      <AlertDialog
        open
        title="Sure?"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onCancel when cancel button clicked", async () => {
    const onCancel = vi.fn();
    render(
      <AlertDialog
        open
        title="Sure?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    await act(async () => fireEvent.click(screen.getByText("Cancel")));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("renders custom button labels", () => {
    render(
      <AlertDialog
        open
        title="Confirm"
        confirmLabel="Yes, proceed"
        cancelLabel="No thanks"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("Yes, proceed")).toBeTruthy();
    expect(screen.getByText("No thanks")).toBeTruthy();
  });

  it("renders without description", () => {
    render(
      <AlertDialog open title="Confirm" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByText("Confirm")).toBeTruthy();
  });

  it("calls onCancel when Escape key pressed (onOpenChange path)", async () => {
    const onCancel = vi.fn();
    render(
      <AlertDialog open title="Sure?" onConfirm={vi.fn()} onCancel={onCancel} />,
    );
    expect(screen.getByText("Sure?")).toBeTruthy();
    // Radix Dialog listens for Escape on the document and fires onOpenChange(false)
    await act(async () => fireEvent.keyDown(document, { key: "Escape" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("merges extra className on content", () => {
    render(
      <AlertDialog
        open
        title="Test"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        className="my-extra"
      />,
    );
    const content = screen.getByText("Test").closest("[class*='my-extra']");
    expect(content).toBeTruthy();
  });

  it("does not call onCancel when Radix fires onOpenChange(true)", () => {
    // Drives the falsy branch of `if (!isOpen)` in the onOpenChange
    // handler. vitest 4's AST-aware coverage flags this as a
    // separately-coverable branch even though Radix never naturally
    // fires onOpenChange(true) in our controlled-open usage. Inspect
    // the rendered Radix Dialog.Root's props via a render-tree probe
    // so we can invoke the handler directly without source mocking.
    //
    // Why a probe instead of vi.spyOn: `@radix-ui/react-dialog` is an
    // ESM module whose namespace exports are non-configurable, so
    // vi.spyOn(Dialog, "Root") fails ("Cannot redefine property").
    // The probe reads the prop off the React tree instead.
    const onCancel = vi.fn();
    const { container } = render(
      <AlertDialog open title="Sure?" onConfirm={vi.fn()} onCancel={onCancel} />,
    );
    // Walk the React fiber tree to find the Dialog.Root and its
    // onOpenChange prop. The fiber root key on the container's first
    // child starts with `__reactContainer$`.
    const fiberKey = Object.keys(container).find((k) =>
      k.startsWith("__reactContainer$"),
    );
    expect(fiberKey).toBeTruthy();
    let fiber = container[fiberKey].stateNode.current;
    let onOpenChange;
    while (fiber) {
      const props = fiber.memoizedProps;
      if (props && typeof props.onOpenChange === "function") {
        onOpenChange = props.onOpenChange;
        break;
      }
      // Depth-first traversal.
      fiber = fiber.child || fiber.sibling || (fiber.return && fiber.return.sibling);
    }
    expect(onOpenChange).toBeTypeOf("function");
    // Simulate Radix calling onOpenChange(true) (would happen e.g. if
    // a Trigger were added later or in a focus-management edge case).
    onOpenChange(true);
    // Falsy branch — onCancel is NOT called when isOpen=true.
    expect(onCancel).not.toHaveBeenCalled();
  });
});
