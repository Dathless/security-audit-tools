import { useSyncExternalStore } from "react";
import type { BackendModule, HealthInfo, HealthStatus } from "./types/api";

/** Store cực nhỏ, đủ cho tool cá nhân: get/set + subscribe qua useSyncExternalStore. */
class Store<T> {
  private value: T;
  private listeners = new Set<() => void>();

  constructor(initial: T) {
    this.value = initial;
  }

  get = (): T => this.value;

  set(updater: (prev: T) => T): void {
    const next = updater(this.value);
    if (next !== this.value) {
      this.value = next;
      this.listeners.forEach((l) => l());
    }
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
}

export interface AppState {
  /** danh sách module backend đang enabled — nguồn cho sidebar footer/badge */
  modules: BackendModule[];
  /** badge đỏ "cần xem" theo module_id (đếm mục danger/warning) */
  badges: Record<string, number>;
  health: HealthInfo | null;
  /** backend có đang chạy hay không (từ API call) */
  backendOnline: boolean;
  /** đang có scan chạy (bất kỳ module nào) — hiện trạng sidebar footer */
  scanningNow: boolean;
  /** health status hiển thị: idle | scanning | offline */
  healthStatus: "idle" | "scanning" | "offline" | "unknown";
}

const defaultState: AppState = {
  modules: [],
  badges: {},
  health: null,
  backendOnline: false,
  scanningNow: false,
  healthStatus: "unknown",
};

export const appStore = new Store<AppState>(defaultState);

export function useAppState(): AppState {
  return useSyncExternalStore(appStore.subscribe, appStore.get);
}

/** Cập nhật health từ backend và suy ra trạng thái hiển thị. */
export function updateHealth(health: HealthInfo | null, online = true): void {
  appStore.set((prev) => {
    const healthStatus: HealthStatus | "offline" | "unknown" = !online
      ? "offline"
      : health
        ? health.status
        : "unknown";
    return { ...prev, health, backendOnline: online, healthStatus };
  });
}

export function setBadge(moduleId: string, count: number): void {
  appStore.set((prev) => ({ ...prev, badges: { ...prev.badges, [moduleId]: count } }));
}

export function setScanningNow(scanning: boolean): void {
  appStore.set((prev) => ({ ...prev, scanningNow: scanning }));
}