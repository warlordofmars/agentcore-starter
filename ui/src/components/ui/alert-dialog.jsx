// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * AlertDialog — a confirmation dialog for destructive actions.
 *
 * Props:
 *   open         {boolean}  — controlled open state
 *   title        {string}   — dialog heading
 *   description  {string}   — body text (optional)
 *   onConfirm    {Function} — called when the user clicks the confirm button
 *   onCancel     {Function} — called when the user dismisses or clicks cancel
 *   confirmLabel {string}   — label for confirm button (default "Delete")
 *   cancelLabel  {string}   — label for cancel button (default "Cancel")
 *   className    {string}   — extra classes for the content panel
 */
function AlertDialog({
  open,
  title,
  description,
  onConfirm,
  onCancel,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  className,
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(isOpen) => { if (!isOpen) onCancel(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content
          className={cn(
            "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-[var(--surface)] border border-[var(--border)] rounded-lg p-6 w-[calc(100vw-2rem)] max-w-sm z-50 shadow-lg",
            className,
          )}
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <Dialog.Title className="font-semibold text-base mb-2 text-[var(--text)]">
            {title}
          </Dialog.Title>
          {description && (
            <Dialog.Description className="text-sm text-[var(--text-muted)] mb-6">
              {description}
            </Dialog.Description>
          )}
          <div className="flex gap-3 justify-end mt-6">
            <Button variant="secondary" onClick={onCancel}>
              {cancelLabel}
            </Button>
            <Button variant="danger" onClick={onConfirm}>
              {confirmLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export { AlertDialog };
