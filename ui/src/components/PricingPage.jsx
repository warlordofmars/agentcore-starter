// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import { Check } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import PageLayout from "@/components/PageLayout";
import { FREE_TIER_MEMORY_LIMIT } from "@/lib/limits";

const INCLUDED = [
  `Up to ${FREE_TIER_MEMORY_LIMIT} memories`,
  "Semantic search across all memories",
  "Works with Claude Code, Claude Desktop, ChatGPT, Cursor, Continue, and any MCP client",
  "Multiple OAuth clients per account",
  "Activity log and memory browser UI",
  "OAuth 2.1 with PKCE — no shared secrets",
  "No credit card required",
];

export default function PricingPage() {
  const navigate = useNavigate();

  return (
    <PageLayout>
      {/* Header */}
      <section className="py-20 px-4 md:px-8 text-center bg-[var(--surface)]">
        <div className="max-w-[1100px] mx-auto">
          <h1 className="text-[2.5rem] font-extrabold mb-4">Simple, honest pricing</h1>
          <p className="text-[var(--text-muted)] text-lg max-w-[480px] mx-auto leading-relaxed">
            Hive is free to use. No tiers, no credit card, no catch.
          </p>
        </div>
      </section>

      {/* Pricing card */}
      <section className="py-20 px-4 md:px-8">
        <div className="max-w-[420px] mx-auto">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-8 shadow-sm">
            <div className="mb-6">
              <span className="inline-block bg-brand/10 text-brand text-xs font-semibold px-3 py-1 rounded-full mb-4">
                Free
              </span>
              <div className="flex items-baseline gap-1">
                <span className="text-[3rem] font-extrabold leading-none">$0</span>
                <span className="text-[var(--text-muted)] text-sm">/ forever</span>
              </div>
            </div>

            <ul className="flex flex-col gap-3 mb-8">
              {INCLUDED.map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm">
                  <Check size={16} className="text-brand shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>

            <Button variant="brand" size="lg" className="w-full" onClick={() => navigate("/app")}>
              Get started free →
            </Button>
            <p className="text-center text-[13px] text-[var(--text-muted)] mt-3">
              No credit card required
            </p>
          </div>
        </div>
      </section>

      {/* FAQ nudge */}
      <section className="py-12 px-4 md:px-8 text-center border-t border-[var(--border)]">
        <p className="text-[var(--text-muted)] text-sm">
          Questions about limits or data?{" "}
          <a href="/faq" className="text-brand no-underline hover:underline">
            See the FAQ →
          </a>
        </p>
      </section>
    </PageLayout>
  );
}
