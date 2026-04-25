// Copyright (c) 2026 John Carter. All rights reserved.
import { useEffect, useState } from "react";

export function useTheme() {
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem("starter_theme");
    if (stored === "dark" || stored === "light") return stored;
    return globalThis.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("starter_theme", theme);
  }, [theme]);

  function toggle() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  return { theme, toggle };
}
