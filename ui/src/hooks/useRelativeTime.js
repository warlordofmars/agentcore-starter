// Copyright (c) 2026 John Carter. All rights reserved.
import { useEffect, useState } from "react";

/**
 * Returns a human-readable relative time string for `date` (e.g. "just now",
 * "3 mins ago", "2 hours ago"). Updates automatically every 30 seconds.
 * Returns null when date is null/undefined.
 */
export function formatRelativeTime(date) {
  if (!date) return null;
  const secs = Math.floor((Date.now() - date.getTime()) / 1000);
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins} ${mins === 1 ? "min" : "mins"} ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} ${days === 1 ? "day" : "days"} ago`;
}

export function useRelativeTime(date) {
  const [_tick, setTick] = useState(0);

  useEffect(() => {
    if (!date) return;
    const id = setInterval(() => setTick((n) => n + 1), 30_000);
    return () => clearInterval(id);
  }, [date]);

  return formatRelativeTime(date);
}
