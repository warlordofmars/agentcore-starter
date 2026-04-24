// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import { BookOpen, Bot, Share2, Workflow } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import PageLayout from "@/components/PageLayout";

const USE_CASES = [
  {
    icon: BookOpen,
    title: "Remember project context across sessions",
    body: "Store architecture decisions, conventions, and open questions once. Every new Claude session picks up exactly where you left off — no more re-explaining the same context.",
    snippet: `You: "Remember that auth uses JWT — tokens in DynamoDB, 24h TTL."
You: "Remember all API routes require a Bearer token, except /health."`,
  },
  {
    icon: Share2,
    title: "Share team knowledge with AI agents",
    body: "One Hive, many agents. Store shared conventions, runbooks, and team decisions so every team member's AI assistant draws from the same pool of knowledge.",
    snippet: `You: "Remember: deploy via 'uv run inv deploy', never push to main."
You: "Remember the on-call rotation — Mon–Wed Alice, Thu–Fri Bob."`,
  },
  {
    icon: Bot,
    title: "Persistent preferences and instructions",
    body: "Store how you like to work — preferred code style, tone, output format — and every session with every MCP-compatible client respects those preferences automatically.",
    snippet: `You: "Remember: always use TypeScript strict mode."
You: "Remember: keep responses concise, no preamble."`,
  },
  {
    icon: Workflow,
    title: "Cross-tool memory for automated workflows",
    body: "Connect multiple AI tools to the same memory store. A workflow running in Cursor can leave context that a Claude Code session picks up — seamless handoffs across tools.",
    snippet: `You (in Cursor): "Remember migration v42 is pending — run after #108 merges."
You (in Claude Code, later): "What pending migrations do I have?"`,
  },
];

function CodeSnippet({ code }) {
  return (
    <pre className="mt-4 rounded-lg bg-navy text-white/85 text-xs leading-relaxed p-4 overflow-x-auto">
      <code>{code}</code>
    </pre>
  );
}

export default function UseCasesPage() {
  const navigate = useNavigate();

  return (
    <PageLayout>
      {/* Header */}
      <section className="py-20 px-4 md:px-8 text-center bg-[var(--surface)]">
        <div className="max-w-[1100px] mx-auto">
          <h1 className="text-[2.5rem] font-extrabold mb-4">What can you do with Hive?</h1>
          <p className="text-[var(--text-muted)] text-lg max-w-[560px] mx-auto leading-relaxed">
            Persistent memory unlocks a new class of AI workflows. Here are a few ways teams are using it today.
          </p>
        </div>
      </section>

      {/* Use cases */}
      <section className="py-20 px-4 md:px-8">
        <div className="max-w-[1100px] mx-auto flex flex-col gap-16">
          {USE_CASES.map((uc) => (
            <div key={uc.title} className="grid grid-cols-1 gap-8 md:grid-cols-2 md:gap-16 items-start">
              <div>
                <div className="mb-4">
                  <uc.icon size={32} color="#e8a020" />
                </div>
                <h2 className="text-xl font-bold mb-3">{uc.title}</h2>
                <p className="text-[var(--text-muted)] text-sm leading-relaxed">{uc.body}</p>
              </div>
              <CodeSnippet code={uc.snippet} />
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 px-4 md:px-8 text-center border-t border-[var(--border)]">
        <div className="max-w-[480px] mx-auto">
          <h2 className="text-2xl font-bold mb-4">Ready to give your agents a memory?</h2>
          <p className="text-[var(--text-muted)] text-sm mb-8 leading-relaxed">
            Free to use. No credit card. Works with any MCP-compatible client.
          </p>
          <Button variant="brand" size="lg" onClick={() => navigate("/app")}>
            Get started free →
          </Button>
        </div>
      </section>
    </PageLayout>
  );
}
