// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import EmptyState from "./EmptyState.jsx";
import { Badge } from "./ui/badge.jsx";
import { Card } from "./ui/card.jsx";
import { Button } from "./ui/button.jsx";
import { Label } from "./ui/label.jsx";
import { Select } from "./ui/select.jsx";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table.jsx";

const EVENT_COLORS = {
  memory_created: "#34a853",
  memory_updated: "#fbbc04",
  memory_deleted: "#d93025",
  memory_recalled: "#1a73e8",
  memory_listed: "#1a73e8",
  context_summarized: "#9334e8",
  token_issued: "#00897b",
  token_revoked: "#e65100",
  client_registered: "#0277bd",
  client_deleted: "#c62828",
};

export default function ActivityLog() {
  const [events, setEvents] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [limit, setLimit] = useState(100);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stats, setStats] = useState(null);
  const [days, setDays] = useState(7);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [page, s] = await Promise.all([api.getActivity(days, { limit }), api.getStats()]);
      setEvents(page.items);
      setHasMore(page.has_more);
      setStats(s);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [days, limit]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Activity Log</h2>

      {/* Stats bar */}
      {stats && (
        <div className="flex flex-wrap gap-4 mb-5">
          {[
            { label: "Total Memories", value: stats.total_memories },
            { label: "Total Clients", value: stats.total_clients },
            { label: "Events Today", value: stats.events_today },
            { label: "Events (7 days)", value: stats.events_last_7_days },
          ].map(({ label, value }) => (
            <Card key={label} className="flex-1 min-w-[120px] text-center">
              <div className="text-[28px] font-bold">{value}</div>
              <div className="text-xs text-[var(--text-muted)] mt-1">{label}</div>
            </Card>
          ))}
        </div>
      )}

      {error && <p className="text-[var(--danger)] mb-3">{error}</p>}

      <div className="flex flex-wrap gap-2.5 items-center mb-3">
        <Label htmlFor="activity-days" className="mb-0">Show last</Label>
        <Select
          id="activity-days"
          className="w-20"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          {[1, 7, 14, 30, 90].map((d) => (
            <option key={d} value={d}>{d} days</option>
          ))}
        </Select>
        <Label htmlFor="activity-limit" className="mb-0 ml-2">Limit</Label>
        <Select
          id="activity-limit"
          className="w-20"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
        >
          {[50, 100, 250, 500].map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </Select>
        <span className="text-[var(--text-muted)] text-[13px]">
          {events.length} events{hasMore ? " (more available)" : ""}
        </span>
        <Button variant="secondary" onClick={load} className="ml-auto">Refresh</Button>
      </div>

      {loading && <p className="text-[var(--text-muted)]">Loading…</p>}

      <Card className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Event</TableHead>
              <TableHead>Client</TableHead>
              <TableHead>Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={4} className="p-0">
                  <EmptyState
                    variant="activity"
                    title="No activity in this period"
                    description="Events will appear here as your MCP clients use Hive tools."
                  />
                </TableCell>
              </TableRow>
            )}
            {events.map((e) => (
              <TableRow key={e.event_id}>
                <TableCell className="whitespace-nowrap text-[var(--text-muted)] text-xs">
                  {new Date(e.timestamp).toLocaleString()}
                </TableCell>
                <TableCell>
                  <Badge
                    style={{
                      background: `${EVENT_COLORS[e.event_type] ?? "var(--text-muted)"}20`,
                      color: EVENT_COLORS[e.event_type] ?? "var(--text-muted)",
                      border: "none",
                    }}
                  >
                    {e.event_type}
                  </Badge>
                </TableCell>
                <TableCell>
                  <code className="text-[11px]">{e.client_id.slice(0, 8)}…</code>
                </TableCell>
                <TableCell className="text-xs text-[var(--text-muted)]">
                  {Object.entries(e.metadata)
                    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
                    .join(" · ")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
