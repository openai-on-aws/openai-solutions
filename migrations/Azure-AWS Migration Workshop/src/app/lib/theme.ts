export type ThemeMode = "light" | "dark";

export const THEME_STORAGE_KEY = "azure-bedrock-migration-workshop-theme";

export const themeInitScript = `
(() => {
  const key = "${THEME_STORAGE_KEY}";
  const root = document.documentElement;
  try {
    const stored = window.localStorage.getItem(key);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = stored === "light" || stored === "dark" ? stored : prefersDark ? "dark" : "light";
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;
  } catch {
    root.classList.remove("dark");
    root.style.colorScheme = "light";
  }
})();
`;

export function getActiveTheme(): ThemeMode {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function applyTheme(theme: ThemeMode) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}
