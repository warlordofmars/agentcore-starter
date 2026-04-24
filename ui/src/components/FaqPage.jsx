// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import PageLayout from "@/components/PageLayout";
import { FREE_TIER_MEMORY_LIMIT } from "@/lib/limits";

const FAQS = [
  {
    q: "Is my data private? Who can see my memories?",
    a: "Your memories are scoped to your account. Only you can read, write, or delete them. Admins of the Hive service can access data for operational purposes (e.g. debugging, compliance), but no data is shared with third parties or used for training.",
  },
  {
    q: "What are the usage limits?",
    a: `Free accounts can store up to ${FREE_TIER_MEMORY_LIMIT} memories. Once you reach the limit, new memories are rejected until you delete existing ones. Additional rate limits may apply to prevent abuse. We'll communicate any changes to these limits with plenty of notice.`,
  },
  {
    q: "Which MCP clients are supported?",
    a: "Any client that implements the Model Context Protocol works with Hive. Tested clients include Claude Code, Claude Desktop, ChatGPT, Cursor, and Continue. If your client supports MCP, it will work.",
  },
  {
    q: "How do I delete my account or data?",
    a: "You can delete individual memories at any time from the Memory Browser in the management UI. To delete your account and all associated data, sign in and use the account settings, or contact us and we will remove everything within 30 days.",
  },
  {
    q: "What happens if the service goes down?",
    a: "Hive is hosted on AWS with Lambda and DynamoDB, both of which have high availability SLAs. If the service is unavailable, your MCP client will receive an error and can degrade gracefully. Memories are not lost during downtime.",
  },
  {
    q: "Is this free forever?",
    a: "The current free tier will remain free. If paid plans are introduced in the future, existing free-tier accounts will keep their current access. We will communicate any changes well in advance.",
  },
  {
    q: "How do I connect my MCP client?",
    a: "Sign in and open the Setup tab. Copy the config snippet (a short JSON block) into your MCP client's config file. The first time your client uses a Hive tool it opens a browser window to complete OAuth — after that the connection is maintained automatically. Full step-by-step instructions are in the docs.",
  },
  {
    q: "Does Hive work offline or self-hosted?",
    a: "The hosted service requires an internet connection. Self-hosting is not officially supported at this time, though the project is open source and you are welcome to deploy your own instance.",
  },
];

function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-[var(--border)]">
      <button
        className="w-full flex items-center justify-between py-5 text-left gap-4 bg-transparent hover:opacity-80 transition-opacity"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="font-medium text-base">{q}</span>
        <ChevronDown
          size={18}
          className="shrink-0 text-[var(--text-muted)] transition-transform duration-200"
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
        />
      </button>
      {open && (
        <p className="pb-5 text-sm text-[var(--text-muted)] leading-relaxed">{a}</p>
      )}
    </div>
  );
}

export default function FaqPage() {
  return (
    <PageLayout>
      {/* Header */}
      <section className="py-20 px-4 md:px-8 text-center bg-[var(--surface)]">
        <div className="max-w-[1100px] mx-auto">
          <h1 className="text-[2.5rem] font-extrabold mb-4">Frequently asked questions</h1>
          <p className="text-[var(--text-muted)] text-lg max-w-[480px] mx-auto leading-relaxed">
            Everything you need to know before getting started.
          </p>
        </div>
      </section>

      {/* Accordion */}
      <section className="py-16 px-4 md:px-8">
        <div className="max-w-[720px] mx-auto">
          {FAQS.map((item) => (
            <FaqItem key={item.q} q={item.q} a={item.a} />
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-12 px-4 md:px-8 text-center border-t border-[var(--border)]">
        <p className="text-[var(--text-muted)] text-sm">
          Still have questions?{" "}
          <a href="/docs/" className="text-brand no-underline hover:underline">
            Read the docs →
          </a>
        </p>
      </section>
    </PageLayout>
  );
}
