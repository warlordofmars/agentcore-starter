// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { cn } from "@/lib/utils";

function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        "bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius)] p-4",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }) {
  return <div className={cn("flex flex-col gap-1.5 mb-4", className)} {...props} />;
}

function CardTitle({ className, ...props }) {
  return <h3 className={cn("font-semibold text-base", className)} {...props} />;
}

function CardContent({ className, ...props }) {
  return <div className={cn("", className)} {...props} />;
}

function CardFooter({ className, ...props }) {
  return <div className={cn("flex items-center mt-4", className)} {...props} />;
}

export { Card, CardHeader, CardTitle, CardContent, CardFooter };
