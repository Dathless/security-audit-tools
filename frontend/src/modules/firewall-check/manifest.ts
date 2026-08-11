import type { ModuleManifest } from "../../core/types/moduleManifest";

export const manifest: ModuleManifest = {
  id: "firewall-check",
  name: "Firewall Check",
  icon: "⛨",
  route: "/modules/firewall-check",
  navGroup: "modules",
  navOrder: 2,
  status: "coming-soon",
  description: "Kiểm tra trạng thái tường lửa Windows và các rule đang hoạt động.",
};