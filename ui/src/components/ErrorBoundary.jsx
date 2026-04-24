// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";

// React's error-boundary contract still requires a class component
// — there is no hook equivalent for `componentDidCatch` /
// `getDerivedStateFromError`. Wrap the entire route tree so a thrown
// exception in any rendered component falls into a friendly
// "Something went wrong" page with a reload button instead of
// blanking the whole tab.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
    this.handleReload = this.handleReload.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message ?? "" };
  }

  componentDidCatch(error, info) {
    // Best-effort: log to the browser console so a developer
    // inspecting the page can find the trace. A real backend
    // ingest endpoint can be wired here later.
    if (globalThis.console) {
      // eslint-disable-next-line no-console
      globalThis.console.error("ErrorBoundary caught:", error, info);
    }
  }

  handleReload() {
    if (globalThis.location) globalThis.location.reload();
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div
        role="alert"
        data-testid="error-boundary"
        className="min-h-screen flex flex-col items-center justify-center text-center px-4"
      >
        <p
          className="font-bold tracking-[2px] text-[var(--text-muted)] uppercase text-sm mb-3"
          aria-hidden="true"
        >
          Error
        </p>
        <h1 className="text-3xl md:text-4xl font-bold mb-4">Something went wrong</h1>
        <p className="text-[var(--text-muted)] mb-8 max-w-[480px]">
          The page failed to load. Try reloading; if the problem
          persists, please get in touch.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 sm:gap-6 items-center">
          <button
            type="button"
            onClick={this.handleReload}
            className="px-4 py-2 rounded bg-[var(--accent)] text-white border-0 cursor-pointer text-sm"
          >
            Reload page
          </button>
          <a
            href="mailto:hello@warlordofmars.net"
            className="text-[var(--accent)] no-underline hover:underline text-sm"
          >
            Contact support
          </a>
        </div>
      </div>
    );
  }
}
