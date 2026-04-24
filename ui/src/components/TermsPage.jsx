// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import PageLayout from "@/components/PageLayout";

function Section({ title, children }) {
  return (
    <section className="mb-10">
      <h2 className="text-xl font-bold mb-3">{title}</h2>
      <div className="text-sm text-[var(--text-muted)] leading-relaxed space-y-3">{children}</div>
    </section>
  );
}

export default function TermsPage() {
  return (
    <PageLayout>
      {/* Header */}
      <section className="py-20 px-4 md:px-8 text-center bg-[var(--surface)]">
        <div className="max-w-[1100px] mx-auto">
          <h1 className="text-[2.5rem] font-extrabold mb-4">Terms of Service</h1>
          <p className="text-[var(--text-muted)] text-lg max-w-[520px] mx-auto leading-relaxed">
            Last updated: April 2026. Please read these terms before using Hive.
          </p>
        </div>
      </section>

      {/* Body */}
      <section className="py-16 px-4 md:px-8">
        <div className="max-w-[720px] mx-auto">

          <Section title="1. Acceptance of Terms">
            <p>
              By accessing or using Hive ("the Service"), you agree to be bound by these Terms of
              Service. If you do not agree, you may not use the Service.
            </p>
          </Section>

          <Section title="2. Acceptable Use">
            <p>You may use Hive to store, retrieve, and manage memories for AI agents and
            personal productivity. You agree not to:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>Store content that is unlawful, abusive, or infringes third-party rights.</li>
              <li>Attempt to circumvent authentication, rate limits, or access controls.</li>
              <li>Use the Service to send spam, run denial-of-service attacks, or scrape data at
                  scale in ways that degrade service quality for other users.</li>
              <li>Reverse-engineer or resell access to the Service without prior written consent.</li>
            </ul>
            <p>
              We reserve the right to suspend or terminate accounts that violate these rules.
            </p>
          </Section>

          <Section title="3. What Hive Stores">
            <p>When you use Hive, the following data is created and stored on your behalf:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Memories</strong> — key/value pairs with optional tags that you or your
                  AI agents write via the MCP tools (<code>remember</code>, <code>recall</code>,
                  <code>list_memories</code>, <code>search_memories</code>).</li>
              <li><strong>OAuth tokens</strong> — short-lived access tokens and refresh tokens
                  issued to registered MCP clients. Tokens are stored in DynamoDB with a TTL and
                  are automatically purged on expiry.</li>
              <li><strong>Activity logs</strong> — timestamped records of MCP tool calls and
                  management API requests, retained for 90 days for debugging and abuse detection.</li>
              <li><strong>Account data</strong> — your email address collected via Google OAuth
                  at sign-in, used to scope your memories and authenticate management UI access.</li>
            </ul>
          </Section>

          <Section title="4. Data Retention and Deletion">
            <p>
              You may delete individual memories at any time from the Memory Browser in the
              management UI.
            </p>
            <p>
              To delete your account and all associated data (memories, tokens, activity logs,
              and account record), use the <code>DELETE /api/account</code> endpoint (available
              since the v0.19 release, implemented in issue #330). A successful call permanently
              removes all data within seconds. We do not retain backups of deleted accounts beyond
              standard AWS DynamoDB point-in-time recovery windows (35 days).
            </p>
            <p>
              You may also contact us at the email listed in the Privacy Policy to request
              deletion; we will complete it within 30 days.
            </p>
          </Section>

          <Section title="5. Service Availability">
            <p>
              Hive is provided on a best-effort basis. We target high availability using AWS
              Lambda and DynamoDB, but we make no uptime guarantee. Scheduled maintenance or
              unexpected outages may occur. Memories are not lost during downtime.
            </p>
          </Section>

          <Section title="6. Limitation of Liability">
            <p>
              To the fullest extent permitted by applicable law, Hive and its operators are not
              liable for any indirect, incidental, special, consequential, or punitive damages,
              including loss of data or profits, arising from your use of or inability to use the
              Service.
            </p>
            <p>
              Our total liability to you for any claim arising from these terms or the Service
              shall not exceed the amount you paid us in the twelve months preceding the claim.
              Because Hive is currently free, that amount is zero.
            </p>
          </Section>

          <Section title="7. Intellectual Property">
            <p>
              Hive is open-source software. The content of your memories belongs to you. By
              storing content in Hive you grant us a limited licence to host, transmit, and
              process that content solely to provide the Service.
            </p>
          </Section>

          <Section title="8. Changes to These Terms">
            <p>
              We may update these Terms from time to time. We will notify users of material
              changes via the in-app changelog or email. Continued use of the Service after
              notice constitutes acceptance of the updated Terms.
            </p>
          </Section>

          <Section title="9. Governing Law">
            <p>
              These Terms are governed by and construed in accordance with the laws of the State
              of California, United States, without regard to its conflict-of-law provisions. Any
              disputes shall be resolved in the courts located in San Francisco County, California.
            </p>
          </Section>

          <Section title="10. Contact">
            <p>
              Questions about these Terms? Email us at{" "}
              <a href="mailto:hello@warlordofmars.net" className="text-brand no-underline hover:underline">
                hello@warlordofmars.net
              </a>
              .
            </p>
          </Section>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="py-12 px-4 md:px-8 text-center border-t border-[var(--border)]">
        <p className="text-[var(--text-muted)] text-sm">
          See also our{" "}
          <a href="/privacy" className="text-brand no-underline hover:underline">
            Privacy Policy →
          </a>
        </p>
      </section>
    </PageLayout>
  );
}
