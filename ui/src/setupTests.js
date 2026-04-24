// Copyright (c) 2026 John Carter. All rights reserved.
import "@testing-library/jest-dom";

// URL.createObjectURL and URL.revokeObjectURL are not implemented in jsdom.
// Stub them as vi.fn() so components that call them don't throw.
// Individual tests can call .mockReturnValue(...) to control the return.
globalThis.URL.createObjectURL = vi.fn(() => "blob:test-url");
globalThis.URL.revokeObjectURL = vi.fn();

// jsdom does not implement scrollIntoView; stub it so components that call it
// do not throw and coverage branches are reachable.
globalThis.HTMLElement.prototype.scrollIntoView = function () {};

// useTheme reads `matchMedia("(prefers-color-scheme: dark)")` on first render.
// jsdom doesn't ship matchMedia, so stub a default-light response. Individual
// tests that need a different value (e.g. the useTheme suite) can override
// with `vi.stubGlobal("matchMedia", ...)`.
if (typeof globalThis.matchMedia === "undefined") {
  globalThis.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
