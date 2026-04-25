// Copyright (c) 2026 John Carter. All rights reserved.

/**
 * Format a byte count into a human-readable string.
 * Returns null/undefined values as "—" (em dash).
 */
export function formatBytes(bytes) {
  if (bytes == null) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${i === 0 ? value : value.toFixed(1)} ${units[i]}`;
}
