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

export default function PrivacyPage() {
  return (
    <PageLayout>
      {/* Header */}
      <section className="py-20 px-4 md:px-8 text-center bg-[var(--surface)]">
        <div className="max-w-[1100px] mx-auto">
          <h1 className="text-[2.5rem] font-extrabold mb-4">Privacy Policy</h1>
          <p className="text-[var(--text-muted)] text-lg max-w-[520px] mx-auto leading-relaxed">
            Last updated: April 2026. We keep this short and specific to Hive.
          </p>
        </div>
      </section>

      {/* Body */}
      <section className="py-16 px-4 md:px-8">
        <div className="max-w-[720px] mx-auto">

          <Section title="1. Who We Are">
            <p>
              Hive is a shared persistent memory service for AI agents and teams. The Service is
              operated by warlordofmars. Questions about this policy can be sent to{" "}
              <a href="mailto:privacy@warlordofmars.net" className="text-brand no-underline hover:underline">
                privacy@warlordofmars.net
              </a>
              .
            </p>
          </Section>

          <Section title="2. Data We Collect">
            <p>We collect only what is necessary to operate the Service:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <strong>Email address</strong> — collected when you sign in via Google OAuth.
                Used to identify your account, scope your memories, and (rarely) contact you about
                service changes.
              </li>
              <li>
                <strong>Memories</strong> — the key/value pairs you or your AI agents store using
                the MCP tools. These are the core data of the Service and belong to you.
              </li>
              <li>
                <strong>Activity logs</strong> — timestamped records of MCP tool calls (e.g.
                <code> remember</code>, <code>recall</code>) and management API requests. Retained
                for 90 days. Used for debugging, abuse detection, and usage statistics shown in
                your account.
              </li>
              <li>
                <strong>Usage metrics</strong> — aggregate CloudWatch metrics (request counts,
                error rates, latency) used to monitor service health. Not linked to individual
                user identities.
              </li>
              <li>
                <strong>OAuth tokens</strong> — access and refresh tokens issued to your
                registered MCP clients. Stored encrypted in DynamoDB with a TTL; purged
                automatically on expiry.
              </li>
            </ul>
          </Section>

          <Section title="3. How We Use Your Data">
            <ul className="list-disc pl-5 space-y-1">
              <li>To authenticate you and serve your memories to your AI agents.</li>
              <li>To display your activity log and usage statistics in the management UI.</li>
              <li>To detect and prevent abuse or policy violations.</li>
              <li>To notify you of significant changes to the Service or these policies.</li>
            </ul>
            <p>
              We do not sell, rent, or share your personal data with third parties for marketing
              purposes.
            </p>
          </Section>

          <Section title="4. Where Data Is Stored">
            <p>
              All data is stored in AWS DynamoDB (us-east-1 region) behind AWS Lambda with IAM
              role-based access. Semantic search embeddings are stored in AWS S3 Vectors in the
              same region. No data is replicated to other cloud providers or regions.
            </p>
            <p>
              AWS is our primary infrastructure provider. A full list of the third parties
              that process data on our behalf (including AWS, Google OAuth, and Google
              Analytics) is maintained on the{" "}
              <a href="/subprocessors" className="text-brand no-underline hover:underline">
                Subprocessors
              </a>{" "}
              page.
            </p>
          </Section>

          <Section title="5. Cookies and Local Storage">
            <p>
              Hive does not use tracking cookies. The management UI stores a single item in your
              browser's <code>localStorage</code>:
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <code>hive_mgmt_token</code> — a signed JWT issued after you authenticate via
                Google OAuth. Used to authorise API requests from the management UI. Expires
                after 24 hours. Removed when you sign out.
              </li>
            </ul>
            <p>
              No third-party cookies are set on the management UI. The marketing site may set
              cookies via Google Analytics (see section 6).
            </p>
          </Section>

          <Section title="6. Google Analytics 4">
            <p>
              The Hive marketing site (hive.warlordofmars.net and its sub-pages, including <code>/pricing</code>,
              {" "}<code>/faq</code>, <code>/use-cases</code>, and <code>/docs</code>) uses Google
              Analytics 4 (GA4) to measure page views and navigation events.
            </p>
            <p>
              GA4 is <strong>opt-in</strong>: we show a consent banner on your first visit with
              equal-prominence Accept and Reject buttons. No GA4 script loads and no data is sent
              to Google until you click Accept. You can change your choice at any time via the
              <strong> Cookie preferences </strong>link in the footer. The management UI
              (<code>/app</code>) never sends data to GA4, regardless of your choice.
            </p>
            <p>
              You can also opt out at the browser level by enabling "Do Not Track", using a
              content blocker, or installing the{" "}
              <a
                href="https://tools.google.com/dlpage/gaoptout"
                className="text-brand no-underline hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Google Analytics opt-out browser add-on
              </a>
              .
            </p>
          </Section>

          <Section title="7. Google OAuth">
            <p>
              Sign-in is handled by Google OAuth 2.0. When you sign in, Google returns your
              email address and a profile identifier to Hive. We do not request access to your
              Google Drive, Gmail, contacts, or any other Google services. Google's own Privacy
              Policy governs what Google collects during the OAuth flow.
            </p>
          </Section>

          <Section title="8. Your Rights">
            <p>Depending on your location, you may have rights under GDPR, CCPA, or similar laws:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Access</strong> — request a copy of the data we hold about you.</li>
              <li><strong>Correction</strong> — ask us to correct inaccurate data.</li>
              <li>
                <strong>Deletion</strong> — delete your account and all associated data at any
                time using the <code>DELETE /api/account</code> API endpoint, or by contacting us.
                We complete deletion requests within 30 days.
              </li>
              <li><strong>Portability</strong> — export your memories from the management UI.</li>
              <li>
                <strong>Objection</strong> — object to processing where we rely on legitimate
                interests as a legal basis.
              </li>
            </ul>
            <p>
              To exercise any of these rights, email{" "}
              <a href="mailto:privacy@warlordofmars.net" className="text-brand no-underline hover:underline">
                privacy@warlordofmars.net
              </a>
              .
            </p>
          </Section>

          <Section title="9. Data Retention">
            <p>
              Memories are retained until you delete them or delete your account. Activity logs
              are retained for 90 days, after which they are automatically purged. OAuth tokens
              are purged on expiry via DynamoDB TTL. Account deletion via{" "}
              <code>DELETE /api/account</code> removes all data immediately; it may persist in
              AWS DynamoDB point-in-time recovery backups for up to 35 days.
            </p>
          </Section>

          <Section title="10. Changes to This Policy">
            <p>
              We may update this Privacy Policy periodically. Material changes will be announced
              in the in-app changelog or by email. The "last updated" date at the top of this
              page reflects the most recent revision.
            </p>
          </Section>

          <Section title="11. Contact">
            <p>
              For privacy questions or to exercise your data rights, contact us at{" "}
              <a href="mailto:privacy@warlordofmars.net" className="text-brand no-underline hover:underline">
                privacy@warlordofmars.net
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
          <a href="/terms" className="text-brand no-underline hover:underline">
            Terms of Service →
          </a>
        </p>
      </section>
    </PageLayout>
  );
}
