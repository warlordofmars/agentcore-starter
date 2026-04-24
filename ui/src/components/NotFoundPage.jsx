// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import { Link } from "react-router-dom";
import PageLayout from "@/components/PageLayout";

export default function NotFoundPage() {
  return (
    <PageLayout>
      <section className="max-w-[640px] mx-auto px-4 md:px-8 py-20 md:py-28 text-center">
        <p
          className="font-bold tracking-[2px] text-[var(--text-muted)] uppercase text-sm mb-3"
          aria-hidden="true"
        >
          404
        </p>
        <h1 className="text-3xl md:text-4xl font-bold mb-4">Page not found</h1>
        <p className="text-[var(--text-muted)] mb-10">
          The page you&apos;re looking for doesn&apos;t exist or has moved. Try
          one of these instead:
        </p>
        <ul className="flex flex-col sm:flex-row sm:justify-center gap-4 sm:gap-8 list-none p-0 m-0">
          <li>
            <Link
              to="/"
              className="text-[var(--accent)] no-underline hover:underline"
            >
              Home
            </Link>
          </li>
          <li>
            <a
              href="/docs/"
              className="text-[var(--accent)] no-underline hover:underline"
            >
              Docs
            </a>
          </li>
          <li>
            <a
              href="mailto:hello@warlordofmars.net"
              className="text-[var(--accent)] no-underline hover:underline"
            >
              Contact support
            </a>
          </li>
        </ul>
      </section>
    </PageLayout>
  );
}
