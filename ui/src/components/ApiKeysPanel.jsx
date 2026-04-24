// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useCallback, useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { api } from "../api.js";
import { AlertDialog } from "./ui/alert-dialog.jsx";
import { Button } from "./ui/button.jsx";
import { Card } from "./ui/card.jsx";
import { Input } from "./ui/input.jsx";
import { Label } from "./ui/label.jsx";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table.jsx";

export default function ApiKeysPanel() {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", scope: "memories:read memories:write" });
  const [newKey, setNewKey] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);

  function handleCopy(text, id) {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.listApiKeys();
      setKeys(data ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api.createApiKey(form.name, form.scope);
      setNewKey(resp);
      setCreating(false);
      setForm({ name: "", scope: "memories:read memories:write" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    try {
      await api.deleteApiKey(id);
      setKeys((prev) => prev.filter((k) => k.key_id !== id));
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
        title="Revoke API key?"
        description="This will permanently delete the key. Any clients using it will stop working."
        onConfirm={() => handleDelete(pendingDelete)}
        onCancel={() => setPendingDelete(null)}
      />

      <div className="flex items-center mb-4 gap-2.5">
        <h2 className="flex-1 text-lg font-semibold">API Keys</h2>
        <Button onClick={() => { setCreating(true); setNewKey(null); }}>
          + New Key
        </Button>
      </div>

      <p className="text-sm text-[var(--text-muted)] mb-4">
        API keys let scripts and automation tools authenticate without the OAuth flow.
        Use <code>Authorization: Bearer hive_sk_...</code> in your requests.
      </p>

      {error && <p className="text-[var(--danger)] mb-3">{error}</p>}

      {newKey && (
        <Card className="mb-4 border-l-4 border-l-[var(--success)]" data-testid="new-key-banner">
          <strong>Key created successfully.</strong>
          <p className="mt-2 text-sm text-[var(--danger)] font-medium">
            Copy this key now — it will not be shown again.
          </p>
          <div className="mt-2 flex items-center gap-2">
            <code className="text-xs break-all flex-1">{newKey.plaintext_key}</code>
            <button
              type="button"
              aria-label="Copy API key"
              onClick={() => handleCopy(newKey.plaintext_key, "new")}
              className="bg-transparent border-none cursor-pointer text-[var(--text-muted)] p-[2px_4px]"
            >
              {copiedId === "new" ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
          <Button variant="secondary" className="mt-3" onClick={() => setNewKey(null)}>
            Dismiss
          </Button>
        </Card>
      )}

      {creating && (
        <Card className="mb-4">
          <h3 className="mb-4 text-[15px] font-semibold">New API Key</h3>
          <form onSubmit={handleCreate}>
            <div className="mb-2.5">
              <Label htmlFor="key-name">Name</Label>
              <Input
                id="key-name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="CI pipeline"
              />
            </div>
            <div className="mb-4">
              <Label htmlFor="key-scope">Scope</Label>
              <Input
                id="key-scope"
                value={form.scope}
                onChange={(e) => setForm({ ...form, scope: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit">Create</Button>
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
              <TableHead>Scope</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Expires</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {keys.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-[var(--text-muted)] text-sm py-10">
                  No API keys yet. Create one to get started.
                </TableCell>
              </TableRow>
            )}
            {keys.map((k) => (
              <TableRow key={k.key_id}>
                <TableCell><strong>{k.name}</strong></TableCell>
                <TableCell className="text-xs text-[var(--text-muted)]">{k.scope}</TableCell>
                <TableCell className="text-xs text-[var(--text-muted)] whitespace-nowrap">
                  {new Date(k.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell className="text-xs text-[var(--text-muted)] whitespace-nowrap">
                  {k.expires_at ? new Date(k.expires_at).toLocaleDateString() : "Never"}
                </TableCell>
                <TableCell>
                  <Button variant="danger" size="sm" onClick={() => setPendingDelete(k.key_id)}>
                    Revoke
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
