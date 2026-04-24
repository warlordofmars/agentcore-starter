// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { cn } from "@/lib/utils";

function Label({ className, ...props }) {
  return (
    <label
      className={cn("block text-sm text-[var(--text)] mb-1", className)}
      {...props}
    />
  );
}

export { Label };
