// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { cn } from "@/lib/utils";

function Table({ className, ...props }) {
  return <table className={cn("w-full border-collapse", className)} {...props} />;
}

function TableHeader({ className, ...props }) {
  return <thead className={cn("", className)} {...props} />;
}

function TableBody({ className, ...props }) {
  return <tbody className={cn("", className)} {...props} />;
}

function TableRow({ className, ...props }) {
  return (
    <tr
      className={cn("border-b border-[var(--border)]", className)}
      {...props}
    />
  );
}

function TableHead({ className, ...props }) {
  return (
    <th
      className={cn(
        "text-left py-2 px-3 text-[var(--text-muted)] font-semibold text-xs",
        className,
      )}
      {...props}
    />
  );
}

function TableCell({ className, ...props }) {
  return (
    <td className={cn("text-left py-2 px-3 text-sm", className)} {...props} />
  );
}

export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell };
