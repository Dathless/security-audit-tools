import type { ModuleManifest } from "./types/moduleManifest";

/**
 * Registry tự động quét mọi manifest dưới thư mục modules bằng import.meta.glob.
 * Thêm module mới = thêm thư mục, không cần liệt kê thủ công.
 */
const manifests = import.meta.glob<{ manifest: ModuleManifest }>(
  "../modules/*/manifest.ts",
  { eager: true },
);

export const registry: ModuleManifest[] = Object.values(manifests)
  .map((m) => m.manifest)
  .sort((a, b) => a.navOrder - b.navOrder);

export function activeModules(): ModuleManifest[] {
  return registry.filter((m) => m.navGroup === "modules");
}

export function findModuleByRoute(route: string): ModuleManifest | undefined {
  return registry.find((m) => m.route === route);
}

export function findModuleById(id: string): ModuleManifest | undefined {
  return registry.find((m) => m.id === id);
}

export function firstActiveModule(): ModuleManifest | undefined {
  return registry.find((m) => m.navGroup === "modules" && m.status === "active");
}