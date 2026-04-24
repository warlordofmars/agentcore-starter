// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { cn } from "@/lib/utils";

const Select = React.forwardRef(function Select({ className, children, ...props }, ref) {
  return (
    <select
      ref={ref}
      className={cn(
        "bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius)] py-[7px] px-[10px] text-[13px] outline-none w-full font-[inherit] focus:border-[var(--amber)] cursor-pointer",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
});

export { Select };
