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
    "Kiểm kê endpoint TCP/UDP, đánh giá theo bằng chứng và xác nhận đã xem xét độc lập với rủi ro.",
};
