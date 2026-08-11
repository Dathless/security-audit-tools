import { useSyncExternalStore } from "react";

/**
 * Router hash tối giản. Hash = chính route trong manifest
 * (vd "#/modules/port-scanner", "#/history", "#/settings").
 * Không cần react-router — phạm vi tool cá nhân, ít route.
 */

export interface GeneralNavItem {
  route: string;
  label: string;
  icon: string;
}

/** Các trang General cố định (không phải module). */
export const GENERAL_NAV: GeneralNavItem[] = [
  { route: "/scan-history", label: "Scan History", icon: "◷" },
  { route: "/settings", label: "Settings", icon: "⚙" },
];

export function currentHashRoute(): string {
  const raw = window.location.hash.replace(/^#/, "");
  return raw || "/";
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

/** Hook trả về route đang active dạng "/modules/port-scanner". */
export function useRoute(): string {
  const route = useSyncExternalStore(subscribe, currentHashRoute, currentHashRoute);
  if (route === "/") return "/";
  return route.startsWith("/") ? route : `/${route}`;
}

/** Điều hướng (set hash). Nhận dạng "/modules/port-scanner" hoặc không có slash đầu. */
export function navigate(route: string): void {
  const normalized = route.startsWith("/") ? route : `/${route}`;
  if (currentHashRoute() === normalized) {
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    return;
  }
  window.location.hash = normalized;
}