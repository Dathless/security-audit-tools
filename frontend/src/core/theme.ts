import { useSyncExternalStore } from "react";

export const THEMES = [
  { id: "technical", name: "Technical Console", description: "Tối kỹ thuật · amber · bố cục bàn điều khiển" },
  { id: "graphite", name: "Graphite Studio", description: "Graphite · teal · nhịp chuyển động nhẹ" },
  { id: "light", name: "Light Precision", description: "Nền sáng · xanh đậm · đường nét tinh gọn" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
const STORAGE_KEY = "sec_audit_theme";
const listeners = new Set<() => void>();
let current: ThemeId = "technical";

function isTheme(value: unknown): value is ThemeId {
  return THEMES.some((theme) => theme.id === value);
}

export function setTheme(value: unknown): void {
  if (!isTheme(value)) return;
  const changed = current !== value;
  current = value;
  if (typeof window !== "undefined") {
    document.documentElement.dataset.theme = value;
    try { localStorage.setItem(STORAGE_KEY, value); } catch { /* Appearance still works when storage is unavailable. */ }
  }
  if (changed) listeners.forEach((listener) => listener());
}

export function initializeTheme(): void {
  if (typeof window === "undefined") return;
  let stored: unknown;
  try { stored = localStorage.getItem(STORAGE_KEY); } catch { /* Use the default. */ }
  setTheme(isTheme(stored) ? stored : "technical");
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function useTheme(): ThemeId {
  return useSyncExternalStore(subscribe, () => current, () => "technical");
}
