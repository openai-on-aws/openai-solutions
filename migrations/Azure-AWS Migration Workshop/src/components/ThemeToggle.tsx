"use client";

import { useEffect, useState } from "react";
import { THEME_STORAGE_KEY, applyTheme, getActiveTheme, type ThemeMode } from "@/app/lib/theme";

function SunIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2.75v2.5M12 18.75v2.5M2.75 12h2.5M18.75 12h2.5M5.46 5.46l1.76 1.76M16.78 16.78l1.76 1.76M5.46 18.54l1.76-1.76M16.78 7.22l1.76-1.76" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
      <path d="M18.5 14.5A7.5 7.5 0 0 1 9.5 5.5a7.75 7.75 0 1 0 9 9Z" />
      <path d="M15.75 4.75h.01M18.75 7.75h.01" />
    </svg>
  );
}

export default function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>("light");

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setTheme(getActiveTheme());
      setMounted(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  if (!mounted) return <span className="theme-toggle" aria-hidden="true" />;

  const nextTheme: ThemeMode = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${nextTheme} mode`}
      title={`Switch to ${nextTheme} mode`}
      onClick={() => {
        applyTheme(nextTheme);
        window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
        setTheme(nextTheme);
      }}
    >
      {theme === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}
