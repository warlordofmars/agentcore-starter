// Copyright (c) 2026 John Carter. All rights reserved.
// Free tier quotas surfaced in marketing copy. Must stay in sync with
// DEFAULT_QUOTA_MAX_MEMORIES / DEFAULT_QUOTA_MAX_STORAGE_BYTES in src/hive/quota.py.
export const FREE_TIER_MEMORY_LIMIT = 500;
export const FREE_TIER_STORAGE_BYTES_LIMIT = 100 * 1024 * 1024; // 100 MB

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log2(bytes) / 10), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value % 1 === 0 ? value : value.toFixed(1)} ${units[i]}`;
}
