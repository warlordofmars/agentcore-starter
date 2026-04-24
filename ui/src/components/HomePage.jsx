// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import { BrainCircuit, Plug, ShieldCheck, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import PageLayout from "@/components/PageLayout";
import { trackEvent } from "@/analytics.js";

const FEATURES = [
  {
    icon: BrainCircuit,
    title: "Persistent memory across sessions",
    body: "Store facts, context, and decisions once. Every session picks up exactly where the last one left off.",
  },
  {
    icon: Plug,
    title: "Works with any MCP client",
    body: "Plug in to Claude Code, Claude Desktop, ChatGPT, Cursor, Continue, or any client that speaks the Model Context Protocol.",
  },
  {
    icon: Users,
    title: "Share memory across your team",
    body: "One Hive, many agents. Team members and automated workflows read from the same memory store.",
  },
  {
    icon: ShieldCheck,
    title: "Your data, scoped to you",
    body: "Each user sees only their own memories and clients. Admins get a full view. OAuth 2.1 throughout.",
  },
];

const HOW_IT_WORKS = [
  {
    step: "1",
    title: "Sign in with Google",
    body: "Create your free account in seconds — no credit card, no deployment.",
  },
  {
    step: "2",
    title: "Connect your MCP client",
    body: "Paste Hive's config snippet into your client. On first use your browser opens once to approve access — after that it's automatic.",
  },
  {
    step: "3",
    title: "Start remembering",
    body: 'Ask your agent to "remember" something. Hive stores it. Every future session can recall it.',
  },
];

export default function HomePage() {
  const navigate = useNavigate();

  function handleCta(location) {
    trackEvent("cta_click", { cta_location: location });
    navigate("/app");
  }

  return (
    <PageLayout>
      {/* Hero */}
      <section
        className="text-white py-24 px-4 md:px-8 text-center"
        style={{
          background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%)",
        }}
      >
        <h1 className="text-[clamp(2rem,5vw,3.5rem)] font-extrabold mb-6 leading-[1.15]">
          Persistent memory
          <br />
          for AI agents
        </h1>
        <p className="text-[clamp(1rem,2vw,1.25rem)] text-white/75 max-w-[560px] mx-auto mb-10 leading-relaxed">
          Hive gives your AI agents a shared, durable memory store via the Model Context
          Protocol — works with Claude Code, Cursor, Continue, and any MCP-compatible client.
        </p>
        <Button variant="brand" size="lg" onClick={() => handleCta("hero")}>
          Get started free →
        </Button>
        <p className="mt-4 text-white/45 text-[13px]">No credit card required</p>
      </section>

      {/* Features */}
      <section className="py-20 px-4 md:px-8">
        <div className="max-w-[1100px] mx-auto">
          <h2 className="text-center text-[1.75rem] font-bold mb-14">
            Everything your agents need to remember
          </h2>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-8">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-7 shadow-sm"
              >
                <div className="mb-3">
                  <f.icon size={32} color="#e8a020" />
                </div>
                <h3 className="text-base font-bold mb-2">{f.title}</h3>
                <p className="text-[var(--text-muted)] text-sm leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="bg-[var(--surface)] py-20 px-4 md:px-8">
        <div className="max-w-[1100px] mx-auto">
          <h2 className="text-center text-[1.75rem] font-bold mb-14">
            Up and running in minutes
          </h2>
          <div className="flex flex-col gap-8">
            {HOW_IT_WORKS.map((s) => (
              <div key={s.step} className="flex gap-6 items-start">
                <div className="size-10 rounded-full bg-[var(--accent)] text-[var(--accent-fg)] flex items-center justify-center font-bold text-base shrink-0">
                  {s.step}
                </div>
                <div>
                  <h3 className="text-base font-bold mb-1.5">{s.title}</h3>
                  <p className="text-[var(--text-muted)] text-sm leading-relaxed">{s.body}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="text-center mt-14">
            <Button variant="brand" size="lg" onClick={() => handleCta("how_it_works")}>
              Get started free →
            </Button>
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
