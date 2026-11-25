export type Theme = "dark" | "light";

const STORAGE_KEY = "claimcheck-theme";
const PAGE_COLOUR: Record<Theme, string> = { dark: "#05060f", light: "#f7f5ef" };

/** The theme the page is showing. index.html sets it before the first paint. */
export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

/** Show a theme and remember the choice for the next visit. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", PAGE_COLOUR[theme]);
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage can be blocked; the choice then lasts for this visit only.
  }
}
