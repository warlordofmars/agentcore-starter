// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useCallback, useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { api } from "../api.js";
import EmptyState from "./EmptyState.jsx";
import { AlertDialog } from "./ui/alert-dialog.jsx";
import { Button } from "./ui/button.jsx";
import { Card } from "./ui/card.jsx";
import { Input } from "./ui/input.jsx";
import { Label } from "./ui/label.jsx";
import { Select } from "./ui/select.jsx";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table.jsx";

export default function ClientManager() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    client_name: "",
    redirect_uris: "",
    scope: "memories:read memories:write",
    token_endpoint_auth_method: "none",
  });
  const [newClient, setNewClient] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);

  function handleCopyId(id) {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.listClients();
      setClients(data.items ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(e) {
    e.preventDefault();
    try {
      const resp = await api.createClient({
        client_name: form.client_name,
        redirect_uris: form.redirect_uris.split(",").map((u) => u.trim()).filter(Boolean),
        scope: form.scope,
        token_endpoint_auth_method: form.token_endpoint_auth_method,
      });
      setNewClient(resp);
      setCreating(false);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    try {
      await api.deleteClient(id);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setPendingDelete(null);
    }
  }

  return (
    <div>
      <AlertDialog
        open={pendingDelete !== null}
        title="Delete OAuth client?"
        description="This will permanently remove the client and invalidate all its tokens."
        onConfirm={() => handleDelete(pendingDelete)}
        onCancel={() => setPendingDelete(null)}
      />

      <div className="flex items-center mb-4 gap-2.5">
        <h2 className="flex-1 text-lg font-semibold">OAuth Clients</h2>
        <Button onClick={() => { setCreating(true); setNewClient(null); }}>
          + Register Client
        </Button>
      </div>

      {error && <p className="text-[var(--danger)] mb-3">{error}</p>}

      {newClient && (
        <Card className="mb-4 border-l-4 border-l-[var(--success)]">
          <strong>Client registered successfully.</strong>
          <p className="mt-2 text-[13px]">
            <b>Client ID:</b> <code>{newClient.client_id}</code>
          </p>
          {newClient.client_secret && (
            <p className="mt-1 text-[13px] text-[var(--danger)]">
              <b>Client Secret (save now, not shown again):</b>{" "}
              <code>{newClient.client_secret}</code>
            </p>
          )}
          <Button variant="secondary" className="mt-3" onClick={() => setNewClient(null)}>
            Dismiss
          </Button>
        </Card>
      )}

      {creating && (
        <Card className="mb-4">
          <h3 className="mb-4 text-[15px] font-semibold">Register New Client (RFC 7591)</h3>
          <form onSubmit={handleCreate}>
            <div className="mb-2.5">
              <Label htmlFor="client-name">Client Name</Label>
              <Input
                id="client-name"
                required
                value={form.client_name}
                onChange={(e) => setForm({ ...form, client_name: e.target.value })}
                placeholder="My Agent"
              />
            </div>
            <div className="mb-2.5">
              <Label htmlFor="client-redirect-uris">Redirect URIs (comma-separated)</Label>
              <Input
                id="client-redirect-uris"
                value={form.redirect_uris}
                onChange={(e) => setForm({ ...form, redirect_uris: e.target.value })}
                placeholder="http://localhost:3000/callback"
              />
            </div>
            <div className="mb-2.5">
              <Label htmlFor="client-scope">Scope</Label>
              <Input
                id="client-scope"
                value={form.scope}
                onChange={(e) => setForm({ ...form, scope: e.target.value })}
              />
            </div>
            <div className="mb-4">
              <Label htmlFor="client-auth-method">Auth Method</Label>
              <Select
                id="client-auth-method"
                value={form.token_endpoint_auth_method}
                onChange={(e) => setForm({ ...form, token_endpoint_auth_method: e.target.value })}
              >
                <option value="none">none (public)</option>
                <option value="client_secret_post">client_secret_post</option>
                <option value="client_secret_basic">client_secret_basic</option>
              </Select>
            </div>
            <div className="flex gap-2">
              <Button type="submit">Register</Button>
              <Button variant="secondary" type="button" onClick={() => setCreating(false)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {loading && <p className="text-[var(--text-muted)]">Loading…</p>}

      <Card className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Client ID</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Scope</TableHead>
              <TableHead>Registered</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {clients.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={6} className="p-0">
                  <EmptyState
                    variant="clients"
                    title="No clients registered"
                    description="Register an OAuth client to connect your MCP agent to Hive."
                  />
                </TableCell>
              </TableRow>
            )}
            {clients.map((c) => (
              <TableRow key={c.client_id}>
                <TableCell><strong>{c.client_name}</strong></TableCell>
                <TableCell>
                  <span className="inline-flex items-center gap-1">
                    <code className="text-xs">{c.client_id}</code>
                    <button
                      onClick={() => handleCopyId(c.client_id)}
                      className="bg-transparent p-[2px_4px] text-[var(--text-muted)] border-none cursor-pointer"
                      aria-label="Copy client ID"
                    >
                      {copiedId === c.client_id ? <Check size={13} /> : <Copy size={13} />}
                    </button>
                  </span>
                </TableCell>
                <TableCell>{c.token_endpoint_auth_method === "none" ? "public" : "confidential"}</TableCell>
                <TableCell>{c.scope}</TableCell>
                <TableCell>{new Date(c.client_id_issued_at * 1000).toLocaleDateString()}</TableCell>
                <TableCell>
                  <Button variant="danger" size="sm" onClick={() => setPendingDelete(c.client_id)}>
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
