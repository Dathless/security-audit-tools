import type { ReactElement } from "react";
import { ModulePageLayout } from "../../design-system/layouts/ModulePageLayout";
import { Panel } from "../../design-system/components/Panel";
import { DataTable, type DataColumn } from "../../design-system/components/DataTable";
import { StatusBadge } from "../../design-system/components/StatusBadge";
import { ProgressBar } from "../../design-system/components/ProgressBar";
import { ErrorBanner } from "../../design-system/components/ErrorBanner";
import { EmptyState } from "../../design-system/components/EmptyState";
import { Button } from "../../design-system/components/Button";
import type { ScanItem } from "../../core/types/api";
import { useFirewallCheck } from "./useFirewallCheck";
import "./FirewallCheckPage.css";

interface RuleRow extends ScanItem {
  scope: string;
  direction: string;
  action: string;
  ports: string;
  addresses: string;
  application: string;
}

const REASONS: Record<string, string> = {
  FIREWALL_DISABLED: "Firewall đang tắt",
  DEFAULT_INBOUND_ALLOW: "Mặc định cho phép kết nối vào",
  POLICY_UNDETERMINED: "Chưa xác định được chính sách hiệu lực",
  BROAD_INBOUND_ALLOW: "Rule cho phép kết nối vào với phạm vi rộng trên Public",
};

function Findings({ item }: { item: ScanItem }): ReactElement {
  return <>
    <StatusBadge tone={item.severity} label={item.severity === "safe" ? "Không phát hiện theo tiêu chí v1" : undefined} />
    {item.detail.reasons?.map((reason) => <p key={reason}>{REASONS[reason] ?? reason}</p>)}
    {item.detail.guidance?.length ? <details><summary>Hướng dẫn kiểm tra</summary>
      {item.detail.guidance.map((text) => <p key={text}>{text}</p>)}
    </details> : null}
  </>;
}

const columns: DataColumn<RuleRow>[] = [
  { key: "title", label: "Rule", sortable: true, render: (row) => <><strong>{row.title}</strong><p className="mono">{row.detail.name}</p>{row.is_new ? <StatusBadge tone="info" label="NEW" /> : null}</> },
  { key: "scope", label: "Profile", sortable: true },
  { key: "direction", label: "Chiều", sortable: true },
  { key: "action", label: "Hành động", sortable: true },
  { key: "ports", label: "Giao thức / cổng", mono: true, render: (row) => <>{row.ports}<p>Cổng từ xa: {row.detail.remote_ports?.join(", ")}</p></> },
  { key: "addresses", label: "Địa chỉ", mono: true, render: (row) => <>Từ xa: {row.addresses}<p>Cục bộ: {row.detail.local_addresses?.join(", ")}</p></> },
  { key: "application", label: "Chương trình / dịch vụ", render: (row) => <>{row.application}<p>Nguồn policy: {row.detail.policy_source || "—"}</p></> },
  { key: "severity", label: "Đánh giá", sortable: true, render: (row) => <Findings item={row} /> },
];

export function FirewallCheckPage(): ReactElement {
  const { data, loading, scanning, progress, error, startScan } = useFirewallCheck();
  const complete = data?.status === "done";
  const profiles = complete ? data.items.filter((item) => item.detail.kind === "profile") : [];
  const rules: RuleRow[] = complete ? data.items.filter((item) => item.detail.kind === "rule").map((item) => ({
    ...item,
    scope: item.detail.profiles?.join(", ") ?? "—",
    direction: item.detail.direction ?? "—",
    action: item.detail.action ?? "—",
    ports: `${item.detail.protocol ?? "—"} / ${item.detail.local_ports?.join(", ") ?? "—"}`,
    addresses: item.detail.remote_addresses?.join(", ") ?? "—",
    application: `${item.detail.program ?? "—"} / ${item.detail.service ?? "—"}`,
  })) : [];
  const summary = complete ? data.summary : null;
  return <ModulePageLayout
    title="Firewall Check"
    description="Kiểm tra cấu hình Windows Firewall và giải thích các thiết lập cần xem xét."
    actions={<Button disabled={loading || scanning} onClick={() => void startScan()}>Kiểm tra firewall</Button>}
    banner={error ? <ErrorBanner title="Không kiểm tra được firewall" message={error} action={<Button disabled={scanning} onClick={() => void startScan()}>Thử lại</Button>} /> : undefined}
    kpis={[
      { label: "Profiles", value: summary?.total_profiles ?? "—", loading },
      { label: "Rule đang bật", value: summary?.total_rules ?? "—", loading },
      { label: "Nguy hiểm", value: summary?.danger ?? "—", tone: "danger", loading },
      { label: "Cảnh báo", value: summary?.warning ?? "—", tone: "warning", loading },
    ]}
  >
    <p className="firewall-limits" data-testid="firewall-limits">Chỉ đọc cấu hình tại máy. Kết quả chưa kiểm chứng khả năng truy cập từ Internet hoặc tính hiệu lực tổng hợp của mọi rule.</p>
    {scanning ? <ProgressBar {...progress} /> : null}
    {loading ? <p role="status">Đang tải kết quả…</p> : null}
    {!loading && !scanning && !complete && !error ? <EmptyState title="Chưa có kết quả Firewall Check" description="Bấm Kiểm tra firewall hoặc Quét ngay để đọc cấu hình hiện tại." /> : null}
    {complete && !scanning ? <div className="firewall-results" data-testid="firewall-results">
      <div className="firewall-profiles">{profiles.map((item) => <div key={item.id} data-testid="firewall-profile" data-profile={item.detail.name}>
        <Panel title={item.title} subtitle={item.detail.active ? "Đang sử dụng" : "Chưa sử dụng"}>
          <p>Firewall: <strong>{item.detail.enabled ? "Bật" : "Tắt"}</strong></p>
          <p>Inbound mặc định: {item.detail.default_inbound_action}</p>
          <p>Outbound mặc định: {item.detail.default_outbound_action}</p>
          <Findings item={item} />
        </Panel>
      </div>)}</div>
      <Panel title="Rule đang bật" subtitle={`${rules.length} rule trong snapshot · ${data.finished_at ? new Date(data.finished_at).toLocaleString("vi-VN") : ""}`}>
        <DataTable columns={columns} rows={rules} rowKey="id" searchPlaceholder="Tìm rule / profile / địa chỉ / chương trình…" emptyText="Không có rule phù hợp." />
      </Panel>
    </div> : null}
  </ModulePageLayout>;
}
