// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import PageLayout from "@/components/PageLayout";

const LAST_UPDATED = "April 2026";

const SUBPROCESSORS = [
  {
    name: "Amazon Web Services",
    services: "DynamoDB, Lambda, S3 Vectors, CloudFront, CloudWatch",
    purpose: "Hosting, storage, compute, CDN, observability",
    data: "User account, memories, OAuth clients, activity logs, request logs",
    location: "us-east-1 (United States)",
  },
  {
    name: "Google LLC",
    services: "Google OAuth 2.0",
    purpose: "Sign-in / identity verification for the management UI",
    data: "Email address, Google profile identifier",
    location: "Global",
  },
  {
    name: "Google LLC",
    services: "Google Analytics 4",
    purpose: "Marketing-site usage analytics (opt-in only)",
    data: "Pseudonymous usage data (page views, referrers, aggregated device info)",
    location: "Global",
  },
];

function Section({ title, children }) {
  return (
    <section className="mb-10">
      <h2 className="text-xl font-bold mb-3">{title}</h2>
      <div className="text-sm text-[var(--text-muted)] leading-relaxed space-y-3">
        {children}
      </div>
    </section>
  );
}

export default function SubprocessorsPage() {
  return (
    <PageLayout>
      <section className="py-20 px-4 md:px-8 text-center bg-[var(--surface)]">
        <div className="max-w-[1100px] mx-auto">
          <h1 className="text-[2.5rem] font-extrabold mb-4">Subprocessors</h1>
          <p className="text-[var(--text-muted)] text-lg max-w-[520px] mx-auto leading-relaxed">
            Last updated: {LAST_UPDATED}. The third-party services Hive uses to
            operate.
          </p>
        </div>
      </section>

      <section className="py-16 px-4 md:px-8">
        <div className="max-w-[960px] mx-auto">
          <Section title="Current subprocessors">
            <p>
              Hive engages the following third parties (subprocessors) to
              process personal data on our behalf. Each entry lists the
              categories of data they see and where they process it.
            </p>
            <div className="overflow-x-auto -mx-2">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left border-b border-[var(--border)]">
                    <th className="py-3 px-2 font-semibold text-[var(--text)]">
                      Subprocessor
                    </th>
                    <th className="py-3 px-2 font-semibold text-[var(--text)]">
                      Purpose
                    </th>
                    <th className="py-3 px-2 font-semibold text-[var(--text)]">
                      Data processed
                    </th>
                    <th className="py-3 px-2 font-semibold text-[var(--text)]">
                      Location
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {SUBPROCESSORS.map((s) => (
                    <tr
                      key={`${s.name}-${s.services}`}
                      className="border-b border-[var(--border)] align-top"
                    >
                      <td className="py-3 px-2">
                        <div className="text-[var(--text)] font-medium">
                          {s.name}
                        </div>
                        <div className="text-[13px]">{s.services}</div>
                      </td>
                      <td className="py-3 px-2">{s.purpose}</td>
                      <td className="py-3 px-2">{s.data}</td>
                      <td className="py-3 px-2 whitespace-nowrap">
                        {s.location}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <Section title="Notification of changes">
            <p>
              When we add or change subprocessors, we announce the update in the
              in-app changelog. Paid enterprise customers (once available) will
              receive at least 30 days' advance notice by email before any new
              subprocessor is engaged, giving them time to object.
            </p>
          </Section>

          <Section title="Where this fits">
            <p>
              This page is a living complement to our{" "}
              <a
                href="/privacy"
                className="text-brand no-underline hover:underline"
              >
                Privacy Policy
              </a>
              . Section 4 of the Privacy Policy describes where data is stored
              at a high level; this page enumerates the specific services
              involved.
            </p>
          </Section>
        </div>
      </section>
    </PageLayout>
  );
}
