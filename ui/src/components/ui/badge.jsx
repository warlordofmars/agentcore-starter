// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { cn } from "@/lib/utils";

function Badge({ className, style, ...props }) {
  return (
    <span
      className={cn(
        "inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[var(--surface)] border border-[var(--border)] text-[var(--text)]",
        className,
      )}
      style={style}
      {...props}
    />
  );
}

export { Badge };
