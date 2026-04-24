// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        "bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius)] py-[7px] px-[10px] text-[13px] outline-none w-full font-[inherit] focus:border-[var(--amber)]",
        className,
      )}
      {...props}
    />
  );
});

export { Input };
