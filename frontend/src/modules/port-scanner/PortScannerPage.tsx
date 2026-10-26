import { useMemo, useState, type ReactElement } from "react";
import { ModulePageLayout, type LayoutKpi } from "../../design-system/layouts/ModulePageLayout";
import { Panel } from "../../design-system/components/Panel";
import { PanelGrid } from "../../design-system/components/PanelGrid";
import { DataTable, type DataColumn } from "../../design-system/components/DataTable";
import { StatusBadge } from "../../design-system/components/StatusBadge";
import { ProgressBar } from "../../design-system/components/ProgressBar";
import { ErrorBanner } from "../../design-system/components/ErrorBanner";
import { EmptyState } from "../../design-system/components/EmptyState";
import { Button } from "../../design-system/components/Button";
import { EvidenceDrawer } from "../../design-system/components/EvidenceDrawer";
import { RadarMap } from "./components/RadarMap";
import { usePortScanner } from "./usePortScanner";
import type { PortOwner, ScanItem, Severity } from "../../core/types/api";
import "./PortScannerPage.css";

const LABELS: Record<Severity, string> = { danger: "Ưu tiên cao", warning: "Cảnh báo", safe: "Không có phát hiện" };
const WEIGHT: Record<Severity, number> = { danger: 2, warning: 1, safe: 0 };
const CHANGES = { initial: "Ban đầu", added: "Đã thêm", changed: "Đã thay đổi", unchanged: "Không đổi" };
const METADATA_STATUS: Record<string, string> = { access_denied: "Thiếu quyền", gone: "Đã thoát", unknown: "Chưa xác định" };
const REASONS: Record<string, string> = {
  PORT_IN_RISKY_LIST: "Cổng nằm trong danh sách cần chú ý; không phải bằng chứng malware.",
  LISTENING_ON_ALL_INTERFACES: "Bind trên mọi giao diện; chưa xác minh khả năng truy cập từ mạng.",
  NON_LOOPBACK_BIND: "Bind ngoài loopback; cần xem xét phạm vi sử dụng.",
  PROCESS_IDENTITY_UNKNOWN: "Chưa xác định đầy đủ executable/chủ sở hữu tiến trình.",
};
function reviewLabel(item: ScanItem): string {
  return item.review_status === "reviewed" ? `Đã xem xét${item.review_scope === "scan" ? " (lượt này)" : ""}` : item.review_status === "legacy" ? "Dữ liệu cũ" : item.review_status === "needs_review" ? "Cần xem xét" : "Chưa xác nhận";
}
function OwnerEvidence({ owners }: { owners: PortOwner[] }): ReactElement {
  return <>{owners.map((owner, index) => <div className="owner-evidence" key={`${owner.pid}-${index}`}>
    <strong>{owner.name || "Chưa xác định"} · PID {owner.pid ?? "—"}</strong>
    <dl className="evidence-fields">{([['name', 'Tên tiến trình'], ['exe', 'Executable'], ['username', 'Chủ sở hữu'], ['create_time', 'Khởi tạo']] as const).map(([key, label]) => <div className="evidence-field-pair" key={key}><dt>{label}</dt><dd>{key === "create_time" ? owner.create_time != null ? new Date(owner.create_time * 1000).toLocaleString("vi-VN") : "Chưa xác định" : owner[key] || "Chưa xác định"}<span className="field-status"> · {owner.status?.[key] === "ok" ? "Đọc được" : METADATA_STATUS[owner.status?.[key]] || "Chưa xác định"}</span></dd></div>)}</dl>
  </div>)}</>;
}
function ownersText(owners: PortOwner[]): string {
  return owners.map((owner) => {
    const field = (key: "name" | "exe" | "username") => owner[key] || METADATA_STATUS[owner.status?.[key]] || "Chưa xác định";
    return `${field("name")} (${owner.pid ?? "—"}) · ${field("exe")} · ${field("username")}`;
  }).join("; ");
}
interface Row extends ScanItem { port: number; processText: string; protocolText: string; listenerText: string; reasonsText: string }

export function PortScannerPage(): ReactElement {
  const { phase, data, items, summary, progress, error, isScanning, reviewing, review, retryLoad } = usePortScanner();
  const [filter, setFilter] = useState("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  // Failed live evidence must not resolve against the previous completed snapshot.
  const selected = phase === "error" ? undefined : items.find((item) => item.whitelist_key === selectedKey);
  const rows = useMemo<Row[]>(() => items.filter((item) => filter === "all" || item.review_status === filter).map((item) => ({
    ...item, port: item.detail.port ?? 0,
    processText: item.detail.owners?.length ? ownersText(item.detail.owners) : `${item.detail.process_name || "Chưa xác định"} (${item.detail.pid ?? "—"})`,
    protocolText: `${item.detail.protocol?.toUpperCase() || "—"} ${item.detail.family || ""}`,
    listenerText: item.detail.listener || item.detail.ip || "—",
    reasonsText: (item.detail.reasons?.length ? item.detail.reasons.join(", ") : item.detail.note) || "Không có phát hiện",
  })), [items, filter]);
  const dots = useMemo(() => {
    const grouped = new Map<number, Severity>();
    for (const item of items) {
      const port = item.detail.port;
      if (port === undefined) continue;
      const previous = grouped.get(port);
      if (!previous || WEIGHT[item.severity] > WEIGHT[previous]) grouped.set(port, item.severity);
    }
    return [...grouped].sort((a, b) => a[0] - b[0]).map(([port, severity]) => ({ port, severity }));
  }, [items]);
  const loading = phase === "loading" || isScanning;
  const kpis: LayoutKpi[] = [
    { label: "Endpoint", value: summary?.total_endpoints ?? summary?.total_open ?? "—", loading },
    { label: "Ưu tiên cao", value: summary?.danger ?? "—", tone: "danger", loading },
    { label: "Cảnh báo", value: summary?.warning ?? "—", tone: "warning", loading },
    { label: "Không có phát hiện", value: summary?.safe ?? "—", tone: "safe", loading },
  ];
  const columns: DataColumn<Row>[] = [
    { key: "severity", label: "Mức rủi ro", render: (row) => <StatusBadge tone={row.severity} label={LABELS[row.severity]} /> },
    { key: "port", label: "Endpoint", mono: true, sortable: true, render: (row) => <><strong className="endpoint-port">{row.port}</strong><span className="cell-secondary">{row.listenerText}</span></> },
    { key: "protocolText", label: "Giao thức", mono: true, sortable: true },
    { key: "processText", label: "Tiến trình", render: (row) => <><strong>{row.detail.owners?.[0]?.name || row.detail.process_name || "Chưa xác định"}</strong><span className="cell-secondary">{row.detail.owners?.length || 1} owner · PID {row.detail.owners?.[0]?.pid ?? row.detail.pid ?? "—"}</span>{row.detail.owners?.some((owner) => Object.values(owner.status ?? {}).some((status) => status !== "ok")) && <span className="cell-secondary">Metadata chưa đầy đủ</span>}</> },
    { key: "review_status", label: "Review / thay đổi", render: (row) => <><StatusBadge tone="info" label={reviewLabel(row)} /><span className="cell-secondary">{row.detail.change_type ? CHANGES[row.detail.change_type] : row.is_new ? "NEW" : "Dữ liệu cũ"}</span></> },
  ];
  const banner = error ? <ErrorBanner title="Cần kiểm tra lại" message={error.message} /> : data?.partial_result ? <ErrorBanner tone="warning" title="Inventory chưa đầy đủ" message="Không dùng lượt này để kết luận endpoint đã biến mất." /> : undefined;
  return <ModulePageLayout title="Port Scanner" description="Kiểm kê TCP LISTEN và UDP bind trên máy; đánh giá theo bằng chứng và xác nhận đã xem xét độc lập với mức rủi ro." kpis={kpis} banner={banner}>
    <div className="scan-context" role="status"><span className="eyebrow">LOCAL / READ ONLY</span><span>{isScanning ? "Đang kiểm kê…" : data?.finished_at ? `Hoàn tất · ${new Date(data.finished_at).toLocaleString("vi-VN")}` : data?.status === "done" ? "Đã có kết quả · Chưa rõ thời điểm hoàn tất" : "Chưa có lượt quét hoàn tất"}</span></div>
    <PanelGrid className="port-grid">
      <Panel id="port-summary" title="Radar cổng" subtitle="Một chấm gộp các endpoint cùng cổng; bảng giữ riêng giao thức và địa chỉ bind.">
        <RadarMap dots={dots} scanning={isScanning} />
        <p data-testid="port-limits">Bind không chứng minh khả năng truy cập LAN/Internet. UDP bind không đồng nghĩa dịch vụ đang lắng nghe. Path/owner không xác minh nội dung binary.</p>
        {data?.assessment_status === "legacy" && <p>Kết quả legacy: giữ nguyên đánh giá cũ; risk trước khi whitelist chưa được lưu. Quét mới để dùng review.</p>}
      </Panel>
      <Panel id="port-inventory" title="Chi tiết endpoint" subtitle={summary ? `${summary.total_endpoints ?? items.length} endpoint · ${summary.unique_ports ?? dots.length} cổng · ${summary.unique_processes ?? "—"} tiến trình` : undefined}>
        <p data-testid="port-review-summary">Đã xem xét: {summary?.reviewed_count ?? 0} · Cần xem xét: {summary?.needs_review_count ?? 0} · Thiếu metadata: {summary?.metadata_incomplete_count ?? 0}. Xác nhận không hạ mức rủi ro.</p>
        {isScanning && <ProgressBar current={progress.current} total={progress.total} message={progress.message} />}
        {phase === "loading" ? <EmptyState title="Đang tải dữ liệu gần nhất…" description="" /> : phase === "error" ? <EmptyState title="Không hoàn tất được lượt quét" description={error?.message || "Lượt quét lỗi"} action={<Button variant="ghost" data-testid="retry-btn" onClick={() => void retryLoad()}>Tải lại</Button>} /> : phase === "empty" || (!isScanning && items.length === 0) ? <EmptyState title={data?.status === "done" ? "Không có endpoint trong lượt quét" : "Chưa có dữ liệu quét"} description="Bấm Quét ngay trên thanh công cụ để kiểm kê trên máy này." /> : <DataTable toolbar={<label className="inventory-filter"><span className="sr-only">Lọc review</span><select id="port-review-filter" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">Tất cả review</option><option value="needs_review">Cần xem xét</option><option value="reviewed">Đã xem xét</option></select></label>} columns={columns} rows={rows} rowKey="whitelist_key" searchText={(row) => `${row.protocolText} ${row.listenerText} ${row.reasonsText}`} searchPlaceholder="Lọc cổng / executable / owner / địa chỉ" maxHeight="520px" renderColumn={(row) => <div className="row-actions"><Button variant="subtle" size="sm" data-testid="endpoint-evidence-btn" onClick={() => setSelectedKey(row.whitelist_key)}>Bằng chứng ↗</Button>{!isScanning && data?.assessment_status === "current" ? <Button variant="ghost" size="sm" disabled={reviewing} data-testid="review-endpoint-btn" onClick={() => void review(row)}>{row.review_status === "reviewed" ? "Hủy xác nhận" : "Xác nhận đã xem"}</Button> : <span className="text-muted">{isScanning ? "Dữ liệu tạm" : "Quét mới để review"}</span>}</div>} />}
        {!!summary?.removed_endpoints?.length && <p>Đã biến mất so với mốc: {summary.removed_endpoints.map((endpoint) => `${endpoint.protocol.toUpperCase()} ${endpoint.listener}:${endpoint.port}`).join("; ")}</p>}
      </Panel>
    </PanelGrid>
    <EvidenceDrawer open={!!selected} title={selected ? `${selected.detail.protocol?.toUpperCase() || "Endpoint"} ${selected.detail.listener || selected.detail.ip || "—"}:${selected.detail.port ?? "—"}` : "Endpoint"} onClose={() => setSelectedKey(null)}>
      {selected && <><StatusBadge tone={selected.severity} label={LABELS[selected.severity]} /> <StatusBadge tone="info" label={reviewLabel(selected)} />
        {isScanning && <p role="status">Dữ liệu tạm của lượt đang quét; chưa phải snapshot hoàn tất.</p>}
        <dl className="evidence-fields"><dt>Giao thức / họ IP</dt><dd>{selected.detail.protocol?.toUpperCase()} / {selected.detail.family || "—"}</dd><dt>Thay đổi</dt><dd>{selected.detail.change_type ? CHANGES[selected.detail.change_type] : "Dữ liệu cũ"}</dd></dl>
        <h3>Tiến trình sở hữu</h3>{selected.detail.owners?.length ? <OwnerEvidence owners={selected.detail.owners} /> : <p>{selected.detail.process_name || "Chưa xác định"} · PID {selected.detail.pid ?? "—"}</p>}
        <h3>Lý do đánh giá</h3><ul>{selected.detail.reasons?.map((reason) => <li key={reason}>{REASONS[reason] || reason}{REASONS[reason] && <><br /><code>{reason}</code></>}</li>)}</ul>{selected.detail.note && <p>{selected.detail.note}</p>}
        <h3>Hướng dẫn kiểm tra</h3>{selected.detail.guidance?.map((text) => <p key={text}>{text}</p>)}
        {selected.detail.previous_evidence && <><h3>Bằng chứng trước / sau</h3><p>Trước: {LABELS[selected.detail.previous_evidence.severity]} · {selected.detail.previous_evidence.reasons.join(", ")}</p><OwnerEvidence owners={selected.detail.previous_evidence.owners} /><p>Sau: {LABELS[selected.severity]} · {ownersText(selected.detail.owners || [])}</p></>}
        <p>Xác nhận đã xem xét không thay đổi mức rủi ro. Bind không chứng minh khả năng truy cập LAN/Internet; path/owner không xác minh nội dung binary.</p>
      </>}
    </EvidenceDrawer>
  </ModulePageLayout>;
}
