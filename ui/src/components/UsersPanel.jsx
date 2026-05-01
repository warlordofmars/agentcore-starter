// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { formatBytes } from "../lib/limits.js";
import EmptyState from "./EmptyState.jsx";
import { AlertDialog } from "./ui/alert-dialog.jsx";
import { Badge } from "./ui/badge.jsx";
import { Button } from "./ui/button.jsx";
import { Card } from "./ui/card.jsx";
import { Input } from "./ui/input.jsx";
import { Label } from "./ui/label.jsx";
import { Select } from "./ui/select.jsx";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table.jsx";

export default function UsersPanel() {
  const [users, setUsers] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [emailFilter, setEmailFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [selectedUser, setSelectedUser] = useState(null);
  const [userStats, setUserStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [roleUpdating, setRoleUpdating] = useState(false);
  const [userLimits, setUserLimits] = useState(null);
  const [editMemoryLimit, setEditMemoryLimit] = useState("");
  const [editStorageBytesLimit, setEditStorageBytesLimit] = useState("");
  const [limitsSaving, setLimitsSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNextCursor(null);
    try {
      const data = await api.listUsers({ limit: 50 });
      setUsers(data ? data.items : []);
      setNextCursor(data?.next_cursor ?? null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function loadMore() {
    /* v8 ignore next */
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const data = await api.listUsers({ cursor: nextCursor });
      setUsers((prev) => [...prev, ...(data?.items ?? [])]);
      setNextCursor(data?.next_cursor ?? null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleDelete(userId) {
    try {
      await api.deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.user_id !== userId));
      if (selectedUser?.user_id === userId) setSelectedUser(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setPendingDelete(null);
    }
  }

  async function openDetail(user) {
    setSelectedUser(user);
    setUserStats(null);
    setUserLimits(null);
    setStatsLoading(true);
    const [statsResult, limitsResult] = await Promise.allSettled([
      api.getUserStats(user.user_id),
      api.getUserLimits(user.user_id),
    ]);
    try {
      setUserStats(statsResult.status === "fulfilled" ? statsResult.value : null);
      if (limitsResult.status === "fulfilled") {
        const limits = limitsResult.value;
        setUserLimits(limits);
        setEditMemoryLimit(limits?.memory_limit != null ? String(limits.memory_limit) : "");
        setEditStorageBytesLimit(
          limits?.storage_bytes_limit != null ? String(limits.storage_bytes_limit) : ""
        );
      } else {
        setUserLimits(null);
        setEditMemoryLimit("");
        setEditStorageBytesLimit("");
      }
    } finally {
      setStatsLoading(false);
    }
  }

  async function handleRoleChange(userId, newRole) {
    setRoleUpdating(true);
    setError(null);
    try {
      const updated = await api.updateUserRole(userId, newRole);
      setUsers((prev) => prev.map((u) => (u.user_id === userId ? updated : u)));
      setSelectedUser(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setRoleUpdating(false);
    }
  }

  async function handleSaveLimits() {
    setLimitsSaving(true);
    setError(null);
    try {
      const body = {
        memory_limit: editMemoryLimit !== "" ? parseInt(editMemoryLimit, 10) : null,
        storage_bytes_limit:
          editStorageBytesLimit !== "" ? parseInt(editStorageBytesLimit, 10) : null,
      };
      const updated = await api.updateUserLimits(selectedUser.user_id, body);
      setUserLimits(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setLimitsSaving(false);
    }
  }

  const filtered = users.filter((u) => {
    const emailMatch = !emailFilter || u.email.toLowerCase().includes(emailFilter.toLowerCase());
    const roleMatch = !roleFilter || u.role === roleFilter;
    return emailMatch && roleMatch;
  });

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="text-[var(--danger)]">{error}</p>;

  return (
    <div className="flex flex-col md:flex-row gap-5">
      <AlertDialog
        open={pendingDelete !== null}
        title="Delete user?"
        description="This will permanently remove the user account."
        onConfirm={() => handleDelete(pendingDelete)}
        onCancel={() => setPendingDelete(null)}
      />

      <div className="flex-1">
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <h2 className="flex-1 font-semibold text-lg">Users</h2>
          <Input
            data-testid="email-search"
            className="w-48"
            placeholder="Search by email…"
            value={emailFilter}
            onChange={(e) => setEmailFilter(e.target.value)}
          />
          <Select
            data-testid="role-filter"
            className="w-32"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="">All roles</option>
            <option value="admin">admin</option>
            <option value="user">user</option>
          </Select>
        </div>

        {users.length === 0 ? (
          <EmptyState
            variant="users"
            title="No users found"
            description="Users appear here after they sign in for the first time via Google OAuth."
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Joined</TableHead>
                    <TableHead>Last Login</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-[var(--text-muted)] text-sm py-6">
                        No users match your filters.
                      </TableCell>
                    </TableRow>
                  )}
                  {filtered.map((u) => (
                    <TableRow
                      key={u.user_id}
                      className="cursor-pointer"
                      onClick={() => openDetail(u)}
                    >
                      <TableCell>{u.email}</TableCell>
                      <TableCell>
                        <Badge>{u.role}</Badge>
                      </TableCell>
                      <TableCell className="text-[var(--text-muted)] text-xs whitespace-nowrap">
                        {new Date(u.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-[var(--text-muted)] text-xs whitespace-nowrap">
                        {new Date(u.last_login_at).toLocaleString()}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Button variant="danger" size="sm" onClick={() => setPendingDelete(u.user_id)}>
                          Delete
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {nextCursor && (
              <div className="text-center mt-4">
                <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? "Loading…" : "Load more"}
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {selectedUser && (
        <div className="w-full md:w-[300px]">
          <Card data-testid="user-detail">
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-base font-semibold">User Detail</h3>
              <button
                type="button"
                aria-label="Close detail panel"
                className="bg-transparent border-none cursor-pointer text-[var(--text-muted)] p-0"
                onClick={() => setSelectedUser(null)}
              >
                ✕
              </button>
            </div>
            <p className="text-sm font-medium">{selectedUser.display_name}</p>
            <p className="text-xs text-[var(--text-muted)] mb-3">{selectedUser.email}</p>

            {statsLoading && <p className="text-xs text-[var(--text-muted)]">Loading stats…</p>}
            {userStats && (
              <div className="flex gap-4 mb-3">
                <div className="text-center flex-1">
                  <div className="text-lg font-bold">{userStats.memory_count}</div>
                  <div className="text-xs text-[var(--text-muted)]">Memories</div>
                </div>
                <div className="text-center flex-1">
                  <div className="text-lg font-bold">{userStats.client_count}</div>
                  <div className="text-xs text-[var(--text-muted)]">Clients</div>
                </div>
              </div>
            )}

            <div className="text-xs text-[var(--text-muted)] mb-1">
              Joined {new Date(selectedUser.created_at).toLocaleDateString()}
            </div>
            <div className="text-xs text-[var(--text-muted)] mb-4">
              Last login {new Date(selectedUser.last_login_at).toLocaleString()}
            </div>

            <Label htmlFor="detail-role">Role</Label>
            <div className="flex gap-2 mt-1">
              <Select
                id="detail-role"
                value={selectedUser.role}
                disabled={roleUpdating}
                onChange={(e) => handleRoleChange(selectedUser.user_id, e.target.value)}
              >
                <option value="user">user</option>
                <option value="admin">admin</option>
              </Select>
            </div>

            {userLimits && (
              <div className="mt-4" data-testid="limits-section">
                <p className="text-xs font-semibold mb-1">Quota overrides</p>
                <p className="text-xs text-[var(--text-muted)] mb-2">
                  Effective: {userLimits.effective_memory_limit} memories /{" "}
                  {formatBytes(userLimits.effective_storage_bytes_limit)}
                </p>
                <div className="flex flex-col gap-2">
                  <div>
                    <Label htmlFor="mem-limit-input" className="text-xs">
                      Memory limit (blank = default)
                    </Label>
                    <Input
                      id="mem-limit-input"
                      data-testid="memory-limit-input"
                      type="number"
                      min="1"
                      placeholder={String(userLimits.effective_memory_limit)}
                      value={editMemoryLimit}
                      onChange={(e) => setEditMemoryLimit(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="storage-limit-input" className="text-xs">
                      Storage limit bytes (blank = default)
                    </Label>
                    <Input
                      id="storage-limit-input"
                      data-testid="storage-limit-input"
                      type="number"
                      min="1"
                      placeholder={String(userLimits.effective_storage_bytes_limit)}
                      value={editStorageBytesLimit}
                      onChange={(e) => setEditStorageBytesLimit(e.target.value)}
                    />
                  </div>
                  <Button
                    size="sm"
                    data-testid="save-limits-btn"
                    onClick={handleSaveLimits}
                    disabled={limitsSaving}
                  >
                    {limitsSaving ? "Saving…" : "Save limits"}
                  </Button>
                </div>
              </div>
            )}

            <Button
              variant="danger"
              size="sm"
              className="mt-4 w-full"
              onClick={() => { setPendingDelete(selectedUser.user_id); setSelectedUser(null); }}
            >
              Delete user
            </Button>
          </Card>
        </div>
      )}
    </div>
  );
}
