// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-navy text-white hover:opacity-90",
        brand:
          "bg-brand text-white hover:bg-brand-light",
        outline:
          "border border-white/30 bg-transparent text-white/80 hover:text-white hover:border-white/50",
        ghost:
          "bg-transparent hover:bg-white/10 text-white/75 hover:text-white",
        danger:
          "bg-red-600 text-white hover:opacity-90",
        secondary:
          "border border-[var(--border)] bg-transparent text-[var(--text)] hover:bg-[var(--surface)]",
        nav:
          "border border-white/60 bg-transparent text-white/80 hover:text-white hover:border-white",
      },
      size: {
        default: "px-4 py-2",
        sm:      "px-3 py-1.5 text-xs",
        lg:      "px-9 py-3.5 text-base font-semibold rounded-lg",
        icon:    "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

function Button({ className, variant, size, asChild = false, ...props }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
