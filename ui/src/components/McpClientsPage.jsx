// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useState } from "react";
import { Check, Copy } from "lucide-react";
import PageLayout from "@/components/PageLayout";

const CLIENTS = [
  {
    name: "Claude Code",
    description: "Anthropic's official CLI for Claude. Add Hive to your global settings (or a project's .mcp.json).",
    config: `{
  "mcpServers": {
    "hive": {
      "type": "http",
      "url": "https://hive.warlordofmars.net/mcp"
    }
  }
}`,
    configFile: "~/.claude/settings.json (or .mcp.json)",
  },
  {
    name: "Claude Desktop",
    description: "The Claude desktop app on Mac and Windows. Add Hive via Settings → Connectors → Add custom connector and paste the URL — no config file or mcp-remote helper needed.",
    config: `https://hive.warlordofmars.net/mcp`,
    configFile: "Settings → Connectors → Add custom connector",
  },
  {
    name: "ChatGPT",
    description: "OpenAI's web client. Add Hive as a remote MCP App via Settings → Connectors (Developer mode required). OAuth happens in the browser.",
    config: `https://hive.warlordofmars.net/mcp`,
    configFile: "Settings → Connectors → Add → MCP server",
  },
  {
    name: "Cursor",
    description: "The AI-first code editor. Add Hive as an MCP server in your Cursor config.",
    config: `{
  "mcpServers": {
    "hive": {
      "type": "http",
      "url": "https://hive.warlordofmars.net/mcp"
    }
  }
}`,
    configFile: "~/.cursor/mcp.json",
  },
  {
    name: "Continue",
    description: "The open-source AI code assistant for VS Code and JetBrains. Add Hive in your Continue config.",
    config: `mcpServers:
  - name: hive
    command: npx
    args:
      - mcp-remote
      - https://hive.warlordofmars.net/mcp`,
    configFile: "~/.continue/config.yaml",
  },
];

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 text-xs text-white/60 hover:text-white/90 transition-colors bg-transparent"
      aria-label="Copy config"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

function ClientCard({ name, description, config, configFile }) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
      <h2 className="text-base font-bold mb-2">{name}</h2>
      <p className="text-[var(--text-muted)] text-sm leading-relaxed mb-4">{description}</p>
      <div className="rounded-lg bg-navy overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
          <span className="text-white/40 text-xs">{configFile}</span>
          <CopyButton text={config} />
        </div>
        <pre className="text-white/85 text-xs leading-relaxed p-4 overflow-x-auto">
          <code>{config}</code>
        </pre>
      </div>
    </div>
  );
}

export default function McpClientsPage() {
  return (
    <PageLayout>
      {/* Header */}
      <section className="py-20 px-4 md:px-8 text-center bg-[var(--surface)]">
        <div className="max-w-[1100px] mx-auto">
          <h1 className="text-[2.5rem] font-extrabold mb-4">MCP client compatibility</h1>
          <p className="text-[var(--text-muted)] text-lg max-w-[560px] mx-auto leading-relaxed">
            Hive works with any client that speaks the Model Context Protocol.
            Copy the config snippet for your tool below.
          </p>
        </div>
      </section>

      {/* Client cards */}
      <section className="py-20 px-4 md:px-8">
        <div className="max-w-[1100px] mx-auto grid grid-cols-1 md:grid-cols-[repeat(auto-fit,minmax(460px,1fr))] gap-6">
          {CLIENTS.map((c) => (
            <ClientCard key={c.name} {...c} />
          ))}
        </div>
      </section>

      {/* Footer note */}
      <section className="py-12 px-4 md:px-8 text-center border-t border-[var(--border)]">
        <p className="text-[var(--text-muted)] text-sm max-w-[560px] mx-auto leading-relaxed">
          Any MCP-compatible client works with Hive — these are the most commonly used ones.
          See the{" "}
          <a href="/docs/" className="text-brand no-underline hover:underline">
            docs
          </a>{" "}
          for full setup instructions including authentication.
        </p>
      </section>
    </PageLayout>
  );
}
