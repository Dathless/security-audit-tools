/** Các kiểu chung khớp với backend (xem docs/BACKEND.md + mã nguồn backend). */

export type Severity = "safe" | "warning" | "danger";

export interface ScanSummary {
  total_open: number;
  danger: number;
  warning: number;
  safe: number;
}

export interface BackendModule {
  id: string;
  display_name: string;
  version: string;
  enabled: boolean;
  status: string;
  has_scan: boolean;
  last_scan?: ScanListItem | null;
}

export type HealthStatus = "idle" | "scanning";

export interface HealthInfo {
  status: HealthStatus;
  running_scans: number;
  registered_modules: number;
  uptime_seconds: number;
}

export interface ScanListItem {
  id: string;
  status: "running" | "done" | "error";
  started_at: string | null;
  finished_at: string | null;
  summary: ScanSummary | null;
  partial_result: boolean;
  error_message?: string | null;
}

export interface ScanItemDetail {
  port?: number;
  listener?: string;
  pid?: number | null;
  process_name?: string;
  protocol?: string;
  reasons?: string[];
  permission_denied?: boolean;
  [key: string]: unknown;
}

export interface ScanItem {
  id: number;
  severity: Severity;
  title: string;
  detail: ScanItemDetail;
  whitelist_key: string;
  is_new: boolean;
}

export interface ScanDetail extends ScanListItem {
  items: ScanItem[];
  module_id?: string;
}

export interface WhitelistEntry {
  id: number;
  module_id: string;
  whitelist_key: string;
  label: string | null;
  created_at: string | null;
}

export type ApiErrorBody = {
  code: string;
  message: string;
};

export type ScanWsMessage =
  | { type: "progress"; current: number; total: number; message: string }
  | {
      type: "item_found";
      item: { id?: number; severity: Severity; title: string; detail: ScanItemDetail; is_new: boolean };
    }
  | {
      type: "done";
      scan_id: string;
      summary: ScanSummary;
      partial_result: boolean;
      module_id?: string;
      replay?: boolean;
    }
  | { type: "error"; code: string; message: string };