// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useEffect, useState } from "react";
import { AlertTriangle, Check, Download } from "lucide-react";
import { api } from "../api.js";
import { Button } from "./ui/button.jsx";
import { Card } from "./ui/card.jsx";

const STEP1_KEY = "hive_setup_step1_done";

export default function SetupPanel() {
  const mcpUrl = import.meta.env.VITE_MCP_BASE ?? `${globalThis.location.origin}/mcp`;
  const [activeTab, setActiveTab] = useState("code");
  const [desktopMode, setDesktopMode] = useState("url"); // "url" | "json"
  const [copied, setCopied] = useState(false);
  const [urlCopied, setUrlCopied] = useState(false);
  const [step1Done, setStep1Done] = useState(() => !!localStorage.getItem(STEP1_KEY));
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null); // "ok" | "error"
  const [testError, setTestError] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [quota, setQuota] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  async function handleExport() {
    setExporting(true);
    setExportError("");
    try {
      const result = await api.exportAccount();
      if (!result) return;
      const { blob, filename } = result;
      const url = URL.createObjectURL(blob);
      const link = globalThis.document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportError(e.message ?? "Export failed");
    } finally {
      setExporting(false);
    }
  }

  useEffect(function loadQuota() {
    api.getStats().then(function handleStats(s) {
      if (s && s.memory_limit != null) setQuota(s);
    }).catch(function handleError() {});
  }, []);

  const step2Done = testResult === "ok";

  const httpConfig = JSON.stringify(
    { mcpServers: { hive: { type: "http", url: mcpUrl } } },
    null,
    2,
  );
  const mrConfig = JSON.stringify(
    { mcpServers: { hive: { command: "npx", args: ["mcp-remote", mcpUrl] } } },
    null,
    2,
  );
  const configs = {
    code: httpConfig,
    cursor: httpConfig,
    desktop: mrConfig,
  };

  function handleCopy() {
    navigator.clipboard.writeText(configs[activeTab]);
    setCopied(true);
    localStorage.setItem(STEP1_KEY, "1");
    setStep1Done(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleCopyUrl() {
    navigator.clipboard.writeText(mcpUrl);
    setUrlCopied(true);
    localStorage.setItem(STEP1_KEY, "1");
    setStep1Done(true);
    setTimeout(() => setUrlCopied(false), 2000);
  }

  async function handleDeleteAccount() {
    setDeleting(true);
    setDeleteError("");
    try {
      await api.deleteAccount();
      localStorage.removeItem("hive_mgmt_token");
      globalThis.location.replace("/");
    } catch (e) {
      setDeleteError(e.message ?? "Deletion failed");
      setDeleting(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    setTestError("");
    try {
      await api.listMemories();
      setTestResult("ok");
    } catch (e) {
      setTestResult("error");
      setTestError(e.message ?? "Connection failed");
    } finally {
      setTesting(false);
    }
  }

  function tabClassName(tab) {
    const isActive = activeTab === tab;
    return [
      "px-4 py-1.5 border border-[var(--border)] rounded-t cursor-pointer font-[inherit] text-[var(--text)]",
      "-mb-px",
      isActive
        ? "bg-[var(--bg)] border-b-[var(--bg)] font-semibold"
        : "bg-[var(--surface)]",
    ].join(" ");
  }

  return (
    <div className="max-w-[640px]">
      <h2 className="mb-6">Set up Hive</h2>

      {step1Done && step2Done && (
        <Card className="mb-6 border-l-4 border-l-[var(--success)] flex items-center gap-2.5">
          <Check size={18} className="text-[var(--success)] shrink-0" />
          <div>
            <strong>You're all set!</strong>
            <p className="mt-0.5 text-[13px] text-[var(--text-muted)]">
              Hive is connected and working. Head to the{" "}
              <button
                type="button"
                onClick={() => globalThis.dispatchEvent(new CustomEvent("hive:switch-tab", { detail: "memories" }))}
                className="bg-transparent border-none p-0 text-[var(--accent)] cursor-pointer font-inherit underline"
              >
                Memories
              </button>{" "}
              tab to get started.
            </p>
          </div>
        </Card>
      )}

      <section className="mb-8">
        <h3 className="mb-3 flex items-center gap-2">
          Step 1 — Connect your MCP client
          {step1Done && <Check size={16} className="text-[var(--success)]" />}
        </h3>
        <p className="mb-3 text-[var(--text-muted)]">
          Add Hive to your client config. OAuth is handled automatically on first use — no token
          needed.
        </p>

        <div className="flex gap-1 mb-0 flex-wrap">
          <button className={tabClassName("code")} onClick={() => setActiveTab("code")}>
            Claude Code
          </button>
          <button className={tabClassName("cursor")} onClick={() => setActiveTab("cursor")}>
            Cursor
          </button>
          <button className={tabClassName("desktop")} onClick={() => setActiveTab("desktop")}>
            Claude Desktop
          </button>
          <button className={tabClassName("chatgpt")} onClick={() => setActiveTab("chatgpt")}>
            ChatGPT
          </button>
        </div>

        <div className="border border-[var(--border)] rounded-b rounded-tr p-3 bg-[var(--bg)]">
          {(activeTab === "desktop" || activeTab === "chatgpt") && (
            <DesktopOrChatgptInstructions
              activeTab={activeTab}
              desktopMode={desktopMode}
              setDesktopMode={setDesktopMode}
              mcpUrl={mcpUrl}
              configs={configs}
              urlCopied={urlCopied}
              copied={copied}
              handleCopy={handleCopy}
              handleCopyUrl={handleCopyUrl}
            />
          )}
          {activeTab === "code" && (
            <>
              <p className="mb-2 text-[var(--text-muted)] text-[13px]">
                Add to <code>~/.claude/settings.json</code>:
              </p>
              <pre className="bg-[var(--surface)] border border-[var(--border)] rounded p-3 text-[13px] overflow-x-auto text-[var(--text)]">
                {configs[activeTab]}
              </pre>
              <Button variant="secondary" className="mt-2" onClick={handleCopy}>
                {copied ? "Copied!" : "Copy"}
              </Button>
            </>
          )}
          {activeTab === "cursor" && (
            <>
              <p className="mb-2 text-[var(--text-muted)] text-[13px]">
                Add to <code>~/.cursor/mcp.json</code> (create it if it doesn't exist):
              </p>
              <pre className="bg-[var(--surface)] border border-[var(--border)] rounded p-3 text-[13px] overflow-x-auto text-[var(--text)]">
                {configs[activeTab]}
              </pre>
              <Button variant="secondary" className="mt-2" onClick={handleCopy}>
                {copied ? "Copied!" : "Copy"}
              </Button>
            </>
          )}
        </div>
      </section>

      <section>
        <h3 className="mb-3 flex items-center gap-2">
          Step 2 — Authorise
          {step2Done && <Check size={16} className="text-[var(--success)]" />}
        </h3>
        <p className="text-[var(--text-muted)] mb-3">
          {activeTab === "code" && "Open Claude Code. The next time you use a Hive memory tool, it will prompt you to authorise access via your browser. Complete the flow and you're done."}
          {activeTab === "cursor" && "Restart Cursor. On first use it will open a browser window to complete the OAuth flow. After authorising, the connection is maintained automatically."}
          {activeTab === "desktop" && desktopMode === "url" && "After saving the connector, Claude Desktop opens your browser to complete OAuth. Confirm access and you're connected."}
          {activeTab === "desktop" && desktopMode === "json" && "Restart Claude Desktop. On first use it will open a browser window to complete the OAuth flow. After authorising, the connection is maintained automatically."}
          {activeTab === "chatgpt" && "ChatGPT opens an OAuth pop-up the first time the connector is used. Approve access and the connection is kept open until you revoke it."}
        </p>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={handleTest} disabled={testing}>
            {testing ? "Testing…" : "Test connection"}
          </Button>
          {testResult === "ok" && (
            <span className="text-[13px] text-[var(--success)] flex items-center gap-1">
              <Check size={14} /> Connected
            </span>
          )}
          {testResult === "error" && (
            <span className="text-[13px] text-[var(--danger)]">{testError}</span>
          )}
        </div>
      </section>

      <section className="mt-12 border-t border-[var(--border)] pt-8">
        <h3 className="mb-3">Tip — naming your memories</h3>
        <p className="text-[var(--text-muted)] mb-3 text-sm">
          Keys are free-form, but a structured scheme keeps your store organised as it grows.
          We recommend:
        </p>
        <pre className="bg-[var(--surface)] border border-[var(--border)] rounded p-3 text-[13px] overflow-x-auto text-[var(--text)] mb-3">
          {"{domain}:{entity-type}/{entity-id}:{attribute}\n\nproject:task/42:summary\nuser:profile/alice:preferences\nsession:current:context"}
        </pre>
        <p className="text-[var(--text-muted)] text-sm">
          See the{" "}
          <a
            href="/docs/concepts/key-conventions"
            target="_blank"
            rel="noreferrer"
            className="text-[var(--accent)] underline"
          >
            key naming conventions
          </a>{" "}
          docs for the full guide.
        </p>
      </section>

      {quota && _hasAnyConfiguredLimit(quota) && (
        <section id="usage" className="mt-12 border-t border-[var(--border)] pt-8">
          <h3 className="mb-4">Usage</h3>
          <div className="flex flex-col gap-3.5">
            <QuotaBar label="Memories" used={quota.total_memories} limit={quota.memory_limit} />
            <QuotaBar label="Clients" used={quota.total_clients} limit={quota.client_limit} />
          </div>
          <QuotaCallout quota={quota} />
        </section>
      )}

      <section className="mt-12 border-t border-[var(--border)] pt-8">
        <h3 className="mb-2 flex items-center gap-2">
          <Download size={18} />
          Export my data
        </h3>
        <p className="text-[var(--text-muted)] mb-4 text-sm">
          Download a JSON file containing your profile, memories, OAuth clients, and the last
          90 days of activity. Limited to one export every 5 minutes.
        </p>
        {exportError && (
          <p className="text-[var(--danger)] text-[13px] mb-3">{exportError}</p>
        )}
        <Button variant="secondary" onClick={handleExport} disabled={exporting}>
          {exporting ? "Preparing…" : "Export my data"}
        </Button>
      </section>

      <section className="mt-12 border-t border-[var(--border)] pt-8">
        <h3 className="mb-2 flex items-center gap-2 text-[var(--danger)]">
          <AlertTriangle size={18} />
          Danger Zone
        </h3>
        <p className="text-[var(--text-muted)] mb-4 text-sm">
          Permanently delete your account and all associated data — memories, OAuth clients, and
          your user profile. This action cannot be undone.
        </p>

        {!showDeleteConfirm ? (
          <Button
            variant="secondary"
            className="border-[var(--danger)] text-[var(--danger)]"
            onClick={() => setShowDeleteConfirm(true)}
          >
            Delete my account
          </Button>
        ) : (
          <Card className="border-l-4 border-l-[var(--danger)] max-w-[480px]">
            <p className="mb-4 font-semibold">
              Are you sure? This will permanently erase all your data.
            </p>
            {deleteError && (
              <p className="text-[var(--danger)] text-[13px] mb-3">{deleteError}</p>
            )}
            <div className="flex gap-2">
              <Button
                variant="danger"
                onClick={handleDeleteAccount}
                disabled={deleting}
              >
                {deleting ? "Deleting…" : "Yes, delete everything"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => { setShowDeleteConfirm(false); setDeleteError(""); }}
              >
                Cancel
              </Button>
            </div>
          </Card>
        )}
      </section>
    </div>
  );
}

function DesktopOrChatgptInstructions({
  activeTab,
  desktopMode,
  setDesktopMode,
  mcpUrl,
  configs,
  urlCopied,
  copied,
  handleCopy,
  handleCopyUrl,
}) {
  const isChatgpt = activeTab === "chatgpt";
  const showJsonForm = activeTab === "desktop" && desktopMode === "json";

  if (showJsonForm) {
    return (
      <>
        <p className="mb-2 text-[var(--text-muted)] text-[13px]">
          Add to{" "}
          <code>~/Library/Application Support/Claude/claude_desktop_config.json</code>.
          Requires <a href="https://github.com/geelen/mcp-remote" target="_blank" rel="noreferrer">mcp-remote</a> (
          <code>npx</code> will install it automatically):
        </p>
        <pre className="bg-[var(--surface)] border border-[var(--border)] rounded p-3 text-[13px] overflow-x-auto text-[var(--text)]">
          {configs.desktop}
        </pre>
        <Button variant="secondary" className="mt-2" onClick={handleCopy}>
          {copied ? "Copied!" : "Copy"}
        </Button>
        <button
          type="button"
          className="block mt-3 text-[13px] text-[var(--accent)] underline bg-transparent"
          onClick={() => setDesktopMode("url")}
        >
          ← Back to the Custom Connector flow (recommended)
        </button>
      </>
    );
  }

  const steps = isChatgpt
    ? [
        "Open ChatGPT → Settings → Connectors (Developer mode required).",
        "Click Add → MCP server.",
        "Paste the URL below, save, and approve the OAuth pop-up that follows.",
      ]
    : [
        "Open Claude Desktop → Settings → Connectors.",
        "Click Add custom connector.",
        "Paste the URL below, save, and complete the browser OAuth flow.",
      ];

  return (
    <>
      <p className="mb-2 text-[var(--text-muted)] text-[13px]">
        {isChatgpt
          ? "Add Hive as a remote MCP App. ChatGPT handles OAuth in the browser — no config file needed."
          : "Add Hive as a Custom Connector. Claude Desktop handles OAuth in the browser — no config file or mcp-remote helper needed."}
      </p>
      <ol className="list-decimal pl-5 mb-3 text-[13px] text-[var(--text)] space-y-1">
        {steps.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
      <pre className="bg-[var(--surface)] border border-[var(--border)] rounded p-3 text-[13px] overflow-x-auto text-[var(--text)]">
        {mcpUrl}
      </pre>
      <Button variant="secondary" className="mt-2" onClick={handleCopyUrl}>
        {urlCopied ? "Copied!" : "Copy URL"}
      </Button>
      {!isChatgpt && (
        <button
          type="button"
          className="block mt-3 text-[13px] text-[var(--text-muted)] underline bg-transparent"
          onClick={() => setDesktopMode("json")}
        >
          Prefer JSON? (legacy mcp-remote setup)
        </button>
      )}
    </>
  );
}

// True iff at least one bucket has a configured (positive) limit.
// Used to hide the Usage section header when both limits are
// missing or non-positive — without this guard the section would
// render an empty block (no bars, no callout) and look broken.
function _hasAnyConfiguredLimit(quota) {
  const memOk = quota.memory_limit != null && quota.memory_limit > 0;
  const cliOk = quota.client_limit != null && quota.client_limit > 0;
  return memOk || cliOk;
}

// Per-bucket fill ratio. Limits ≤ 0 are treated as "unconfigured"
// (returns null) so a misconfigured env var never registers as
// "infinitely full" and a 0-limit `QuotaBar` doesn't divide by zero.
function _quotaRatio(used, limit) {
  if (limit == null || limit <= 0) return null;
  return used / limit;
}

// Worst-case bucket drives the callout severity — one resource at
// 100% is enough to block writes, so the callout reflects the
// per-bucket worst case rather than a flat average.
function _quotaSeverity(quota) {
  const ratios = [
    _quotaRatio(quota.total_memories, quota.memory_limit),
    _quotaRatio(quota.total_clients, quota.client_limit),
  ].filter((r) => r != null);
  if (ratios.length === 0) return "ok";
  const worst = Math.max(...ratios);
  if (worst >= 1) return "at";
  if (worst >= 0.8) return "near";
  return "ok";
}

// Which buckets are tripping the callout. Used to tailor the body
// copy: "New memories cannot be saved" only applies when the memory
// quota is the offender, not when it's the client quota that's full.
function _affectedBuckets(quota, threshold) {
  const memRatio = _quotaRatio(quota.total_memories, quota.memory_limit);
  const cliRatio = _quotaRatio(quota.total_clients, quota.client_limit);
  return {
    memory: memRatio != null && memRatio >= threshold,
    clients: cliRatio != null && cliRatio >= threshold,
  };
}

function _detailCopy(severity, affected) {
  const isAt = severity === "at";
  const verbAt = "cannot be saved until you free up space or request more capacity";
  const verbNear = "are running low — free up space soon, or get in touch to request more capacity";
  const verb = isAt ? verbAt : verbNear;
  if (affected.memory && affected.clients) {
    return `New memories and OAuth clients ${verb}.`;
  }
  if (affected.clients) {
    const clientVerb = isAt
      ? "cannot be created until you delete an existing one or request more capacity"
      : "are running low — delete an unused one, or get in touch to request more capacity";
    return `New OAuth clients ${clientVerb}.`;
  }
  return `New memories ${verb}.`;
}

export function QuotaCallout({ quota }) {
  const severity = _quotaSeverity(quota);
  if (severity === "ok") return null;

  const isAt = severity === "at";
  const tone = isAt ? "var(--danger)" : "var(--amber)";
  const headline = isAt
    ? "You've reached your free tier limit."
    : "You're approaching your free tier limit.";
  const affected = _affectedBuckets(quota, isAt ? 1 : 0.8);
  const detail = _detailCopy(severity, affected);

  return (
    <div
      role="status"
      data-testid="quota-callout"
      data-severity={severity}
      className="mt-4 rounded border p-3 text-[13px]"
      style={{ borderColor: tone, color: tone }}
    >
      <strong>{headline}</strong>{" "}
      <span className="text-[var(--text-muted)]">{detail}</span>{" "}
      <a
        href="mailto:hello@warlordofmars.net?subject=Hive%20capacity%20request"
        className="underline"
        style={{ color: tone }}
      >
        Contact us
      </a>{" "}
      <span className="text-[var(--text-muted)]">
        to request an increase.
      </span>
    </div>
  );
}

function QuotaBar({ label, used, limit }) {
  // Match `_quotaSeverity` semantics: a missing or non-positive
  // limit is "unconfigured", not "infinitely full" — skip the bar
  // entirely rather than dividing by zero into a 100% red sliver.
  if (limit == null || limit <= 0) return null;
  const pct = Math.min((used / limit) * 100, 100);
  const nearLimit = pct >= 80;
  const atLimit = pct >= 100;
  const color = atLimit ? "var(--danger)" : nearLimit ? "var(--amber)" : "var(--success)";
  return (
    <div>
      <div className="flex justify-between text-[13px] mb-1">
        <span>{label}</span>
        <span className={atLimit ? "text-[var(--danger)]" : "text-[var(--text-muted)]"}>
          {used} / {limit}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}
