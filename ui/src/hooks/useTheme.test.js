// Copyright (c) 2026 John Carter. All rights reserved.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTheme } from "./useTheme.js";

describe("useTheme", () => {
  let _storage;

  beforeEach(() => {
    _storage = {};
    vi.stubGlobal("localStorage", {
      getItem: (k) => _storage[k] ?? null,
      setItem: (k, v) => { _storage[k] = v; },
      removeItem: (k) => { delete _storage[k]; },
      clear: () => { _storage = {}; },
    });
    document.documentElement.removeAttribute("data-theme");
    vi.stubGlobal("matchMedia", (q) => ({
      matches: q === "(prefers-color-scheme: dark)" ? false : false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("defaults to light when no stored preference and OS is light", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("defaults to dark when OS prefers dark and nothing stored", () => {
    vi.stubGlobal("matchMedia", (q) => ({
      matches: q === "(prefers-color-scheme: dark)",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });

  it("uses stored preference over OS preference", () => {
    localStorage.setItem("starter_theme", "dark");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });

  it("toggle switches theme", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
    act(() => result.current.toggle());
    expect(result.current.theme).toBe("dark");
    act(() => result.current.toggle());
    expect(result.current.theme).toBe("light");
  });

  it("persists theme to localStorage on change", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.toggle());
    expect(localStorage.getItem("starter_theme")).toBe("dark");
  });

  it("sets data-theme on documentElement", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.toggle());
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("ignores invalid stored values and falls back to OS", () => {
    localStorage.setItem("starter_theme", "invalid");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
  });
});
