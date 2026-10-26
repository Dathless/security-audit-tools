/** Các kiểu chung khớp với backend (xem docs/architecture/backend.md + mã nguồn backend). */

export type Severity = "safe" | "warning" | "danger";

export interface ScanSummary {
  assessment_version?: number;
  total_open?: number;
  total_endpoints?: number;
  unique_ports?: number;
  unique_processes?: number;
  metadata_incomplete_count?: number;
  reviewed_count?: number;
  needs_review_count?: number;
  removed_endpoints?: { protocol: string; family: string; listener: string; port: number }[];
  total_profiles?: number;
  total_rules?: number;
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

export interface PortOwner {
  pid: number | null;
  name: string | null;
  exe: string | null;
  username: string | null;
  create_time?: number | null;
  status: Record<string, string>;
}

export interface ScanItemDetail {
  identity_version?: number;
  assessment_version?: number;
  family?: string;
  exposure?: string;
  owners?: PortOwner[];
  change_type?: "initial" | "added" | "changed" | "unchanged";
  previous_evidence?: { owners: PortOwner[]; severity: Severity; reasons: string[] };
  port?: number;
  listener?: string;
  ip?: string;
  note?: string;
  pid?: number | null;
  process_name?: string;
  protocol?: string;
  reasons?: string[];
  permission_denied?: boolean;
  kind?: "profile" | "rule";
  name?: string;
  enabled?: boolean;
  active?: boolean;
  default_inbound_action?: string;
  default_outbound_action?: string;
  profiles?: string[];
  direction?: string;
  action?: string;
  local_ports?: string[];
  remote_ports?: string[];
  local_addresses?: string[];
  remote_addresses?: string[];
  program?: string;
  service?: string;
  policy_source?: string;
  guidance?: string[];
  [key: string]: unknown;
}

export interface ScanItem {
  id: number;
  severity: Severity;
  title: string;
  detail: ScanItemDetail;
  whitelist_key: string;
  is_new: boolean;
  review_status?: "reviewed" | "needs_review" | "unreviewed" | "legacy";
  review_scope?: "scan" | "persistent" | null;
  review_id?: number | null;
}

export interface ScanDetail extends ScanListItem {
  items: ScanItem[];
  module_id?: string;
  assessment_status?: "legacy" | "current";
}

export interface PortReview {
  id: number;
  endpoint_key: string;
  label: string;
  scan_id: string;
  scope: "scan" | "persistent";
  note: string | null;
  reviewed_at: string;
  expired_at: string | null;
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
      item: { id?: number; whitelist_key?: string; severity: Severity; title: string; detail: ScanItemDetail; is_new: boolean };
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
