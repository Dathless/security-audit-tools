import type { ComponentType } from "react";

export type NavGroup = "modules" | "general";
export type ModuleStatus = "active" | "coming-soon";

/**
 * Hợp đồng khai báo 1 module. Thêm module = thêm 1 thư mục + 1 file
 * manifest.ts như thế này — không sửa AppShell/router/registry.
 */
export interface ModuleManifest {
  id: string;
  name: string;
  displayName?: string;
  /** icon token — ký tự/ký hiệu đơn giản, không phải ảnh cứng */
  icon: string;
  /** đường dẫn dạng "/modules/port-scanner" */
  route: string;
  navGroup: NavGroup;
  navOrder: number;
  status: ModuleStatus;
  /** component Page khi status === "active" */
  Page?: ComponentType;
  /** optional: số hiển thị trên sidebar (badge "cần xem") */
  badge?: () => number;
  /** optional: mô tả ngắn hiển thị trên trang module / trang soon */
  description?: string;
}