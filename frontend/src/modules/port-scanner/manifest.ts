import type { ModuleManifest } from "../../core/types/moduleManifest";
import { PortScannerPage } from "./PortScannerPage";

export const manifest: ModuleManifest = {
  id: "port-scanner",
  name: "Port Scanner",
  icon: "◎",
  route: "/modules/port-scanner",
  navGroup: "modules",
  navOrder: 1,
  status: "active",
  Page: PortScannerPage,
  description:
    "Quét toàn bộ cổng đang LISTEN, đối chiếu whitelist và so sánh với lượt quét trước để phát hiện điều mới xuất hiện.",
};