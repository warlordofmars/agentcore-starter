// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded bg-[var(--border)] h-4",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };
