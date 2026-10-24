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
import { RadarMap } from "./components/RadarMap";
import { usePortScanner } from "./usePortScanner";
import type { PortOwner, ScanItem, Severity } from "../../core/types/api";
import "./PortScannerPage.css";

const LABELS: Record<Severity, string> = { danger: "Ưu tiên cao", warning: "Cảnh báo", safe: "Không có phát hiện" };
const WEIGHT: Record<Severity, number> = { danger: 2, warning: 1, safe: 0 };
const CHANGES = { initial: "Ban đầu", added: "Đã thêm", changed: "Đã thay đổi", unchanged: "Không đổi" };
const METADATA_STATUS: Record<string, string> = { access_denied: "Thiếu quyền", gone: "Đã thoát", unknown: "Chưa xác định" };
function ownersText(owners: PortOwner[]): string {
  return owners.map((owner) => {
    const field = (key: "name" | "exe" | "username") => owner[key] || METADATA_STATUS[owner.status?.[key]] || "Chưa xác định";
    return `${field("name")} (${owner.pid ?? "—"}) · ${field("exe")} · ${field("username")}`;
  }).join("; ");
}
interface Row extends ScanItem { port: number; processText: string; protocolText: string; listenerText: string; reasonsText: string }

export function PortScannerPage(): ReactElement {
  const { phase, data, items, summary, progress, error, isScanning, reviewing, review, startScan, retryLoad } = usePortScanner();
  const [filter, setFilter] = useState("all");
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
    { key: "port", label: "Cổng", mono: true, sortable: true },
    { key: "processText", label: "Tiến trình / executable / owner", mono: true },
    { key: "protocolText", label: "Giao thức", mono: true, sortable: true },
    { key: "listenerText", label: "Listener / bind", mono: true },
    { key: "review_status", label: "Review", render: (row) => <StatusBadge tone="info" label={row.review_status === "reviewed" ? `Đã xem xét${row.review_scope === "scan" ? " (lượt này)" : ""}` : row.review_status === "legacy" ? "Dữ liệu cũ" : row.review_status === "needs_review" ? "Cần xem xét" : "Chưa xác nhận"} /> },
    { key: "is_new", label: "Thay đổi", render: (row) => <span className="badge-new">{row.detail.change_type ? CHANGES[row.detail.change_type] : row.is_new ? "NEW" : "Dữ liệu cũ"}</span> },
    { key: "reasonsText", label: "Lý do / hướng dẫn", render: (row) => <div>{row.reasonsText}<br />{row.detail.guidance?.join(" ")}{row.detail.previous_evidence && <p>Trước: {ownersText(row.detail.previous_evidence.owners)} · {LABELS[row.detail.previous_evidence.severity]}<br />Sau: {row.processText} · {LABELS[row.severity]}</p>}</div> },
  ];
  const banner = error ? <ErrorBanner title="Cần kiểm tra lại" message={error.message} /> : data?.partial_result ? <ErrorBanner tone="warning" title="Inventory chưa đầy đủ" message="Không dùng lượt này để kết luận endpoint đã biến mất." /> : undefined;
  return <ModulePageLayout title="Port Scanner" description="Kiểm kê TCP LISTEN và UDP bind trên máy; đánh giá theo bằng chứng và xác nhận đã xem xét độc lập với mức rủi ro." kpis={kpis} banner={banner}>
    <PanelGrid>
      <Panel title="Radar cổng" subtitle="Một chấm gộp các endpoint cùng cổng; bảng giữ riêng giao thức và địa chỉ bind.">
        <RadarMap dots={dots} scanning={isScanning} />
        <p data-testid="port-limits">Bind không chứng minh khả năng truy cập LAN/Internet. UDP bind không đồng nghĩa dịch vụ đang lắng nghe. Path/owner không xác minh nội dung binary.</p>
        {data?.assessment_status === "legacy" && <p>Kết quả legacy: giữ nguyên đánh giá cũ; risk trước khi whitelist chưa được lưu. Quét mới để dùng review.</p>}
      </Panel>
      <Panel title="Chi tiết endpoint" subtitle={summary ? `${summary.total_endpoints ?? items.length} endpoint · ${summary.unique_ports ?? dots.length} cổng · ${summary.unique_processes ?? "—"} tiến trình` : undefined}>
        <p data-testid="port-review-summary">Đã xem xét: {summary?.reviewed_count ?? 0} · Cần xem xét: {summary?.needs_review_count ?? 0} · Thiếu metadata: {summary?.metadata_incomplete_count ?? 0}. Xác nhận không hạ mức rủi ro.</p>
        <label htmlFor="port-review-filter">Lọc review </label>
        <select id="port-review-filter" value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="all">Tất cả</option><option value="needs_review">Cần xem xét</option><option value="reviewed">Đã xem xét</option>
        </select>
        {isScanning && <ProgressBar current={progress.current} total={progress.total} message={progress.message} />}
        {phase === "loading" ? <EmptyState title="Đang tải dữ liệu gần nhất…" description="" /> : phase === "error" ? <EmptyState title="Không hoàn tất được lượt quét" description={error?.message || "Lượt quét lỗi"} action={<><Button variant="ghost" data-testid="retry-btn" onClick={() => void retryLoad()}>Tải lại</Button><Button onClick={() => void startScan()}>Quét ngay</Button></>} /> : phase === "empty" || (!isScanning && items.length === 0) ? <EmptyState title={data?.status === "done" ? "Không có endpoint trong lượt quét" : "Chưa có dữ liệu quét"} description="Bấm Quét ngay để kiểm kê trên máy này." action={<Button data-testid="scan-button" onClick={() => void startScan()}>Quét ngay</Button>} /> : <DataTable columns={columns} rows={rows} rowKey="whitelist_key" searchPlaceholder="Lọc cổng / executable / owner / địa chỉ" maxHeight="520px" renderColumn={(row) => <div className="row-actions">{!isScanning && data?.assessment_status === "current" ? <Button variant="ghost" size="sm" disabled={reviewing} data-testid="review-endpoint-btn" onClick={() => void review(row)}>{row.review_status === "reviewed" ? "Hủy xác nhận" : "Xác nhận đã xem"}</Button> : <span className="text-muted">{isScanning ? "Dữ liệu tạm" : "Quét mới để review"}</span>}</div>} />}
        {!!summary?.removed_endpoints?.length && <p>Đã biến mất so với mốc: {summary.removed_endpoints.map((endpoint) => `${endpoint.protocol.toUpperCase()} ${endpoint.listener}:${endpoint.port}`).join("; ")}</p>}
      </Panel>
    </PanelGrid>
  </ModulePageLayout>;
}
