import { useMemo, type ReactElement } from "react";
import { ModulePageLayout, type LayoutKpi } from "../../design-system/layouts/ModulePageLayout";
import { Panel } from "../../design-system/components/Panel";
import { PanelGrid } from "../../design-system/components/PanelGrid";
import { DataTable, type DataColumn } from "../../design-system/components/DataTable";
import { StatusBadge } from "../../design-system/components/StatusBadge";
import { ProgressBar } from "../../design-system/components/ProgressBar";
import { ErrorBanner } from "../../design-system/components/ErrorBanner";
import { EmptyState } from "../../design-system/components/EmptyState";
import { Button } from "../../design-system/components/Button";
import { RadarMap, type RadarDot } from "./components/RadarMap";
import { usePortScanner } from "./usePortScanner";
import type { ScanItem, Severity, WhitelistEntry } from "../../core/types/api";
import "./PortScannerPage.css";

interface Row extends ScanItem {
  _port: number;
  _pidText: string;
  _processText: string;
  _proto: string;
  _listener: string;
  _reasons: string[];
}

/** Một dòng hiển thị = MỘT CỔNG (group các item theo port), list tiến trình kèm theo. */
interface PortRow {
  key: string;
  port: number;
  severity: Severity;
  processText: string;
  protoText: string;
  listenerText: string;
  reasonsText: string;
  isNew: boolean;
  items: Row[];
  allSafe: boolean;
}

function toRow(item: ScanItem): Row {
  const d = item.detail;
  return {
    ...item,
    _port: typeof d.port === "number" ? d.port : 0,
    _pidText: d.pid != null ? String(d.pid) : "—",
    _processText: d.process_name || (d.permission_denied ? "(cần admin)" : "—"),
    _proto: d.protocol || "—",
    _listener: d.listener || d.ip || "—",
    _reasons: Array.isArray(d.reasons) ? d.reasons : d.note ? [d.note] : [],
  };
}

const SEV_WEIGHT: Record<Severity, number> = { safe: 0, warning: 1, danger: 2 };

function worstSeverity(a: Severity, b: Severity): Severity {
  return SEV_WEIGHT[a] >= SEV_WEIGHT[b] ? a : b;
}

function uniq(list: unknown[]): string[] {
  return [...new Set(list.filter((v) => v != null && String(v).trim() !== "—").map(String))];
}

/** Group các item theo cổng — 1 cổng = 1 dòng, các tiến trình/PID nối lại. */
function groupByPort(rows: Row[], severityOf: (item: ScanItem) => Severity): PortRow[] {
  const byPort = new Map<number, Row[]>();
  for (const r of rows) {
    const list = byPort.get(r._port) ?? [];
    list.push(r);
    byPort.set(r._port, list);
  }
  const result: PortRow[] = [];
  for (const [port, items] of byPort) {
    const sev = items.map((r) => severityOf(r)).reduce(worstSeverity, "safe");
    // "process (PID)" gộp theo từng item riêng — vd "chrome.exe (1111), svchost.exe (2222)"
    const processList = uniq(
      items.map((r) => {
        const name = r._processText;
        const pid = r._pidText;
        if (name === "—" || name === "(cần admin)") return pid !== "—" ? pid : name;
        return pid !== "—" ? `${name} (${pid})` : name;
      }),
    );
    result.push({
      key: `port-${port}`,
      port,
      severity: sev,
      processText: processList.join(", ") || "—",
      protoText: uniq(items.map((r) => r._proto)).join(", ") || "—",
      listenerText: uniq(items.map((r) => r._listener)).join(", ") || "—",
      reasonsText: uniq(items.flatMap((r) => r._reasons)).join(", ") || "",
      isNew: items.some((r) => r.is_new),
      items,
      allSafe: items.every((r) => severityOf(r) === "safe"),
    });
  }
  result.sort((a, b) => a.port - b.port);
  return result;
}

export function PortScannerPage(): ReactElement {
  const {
    phase,
    data,
    items,
    summary,
    progress,
    whitelist,
    error,
    isScanning,
    startScan,
    markSafe,
    unmarkSafe,
    severityOf,
    retryLoad,
  } = usePortScanner();

  const loading = phase === "loading" || phase === "scanning";

  const kpis: LayoutKpi[] = [
    { label: "Cổng đang mở", value: summary?.total_open ?? "—", sub: summary ? "trong lượt quét này" : undefined, loading },
    { label: "Nguy hiểm", value: summary?.danger ?? "—", tone: "danger", loading },
    { label: "Cảnh báo", value: summary?.warning ?? "—", tone: "warning", loading },
    { label: "An toàn", value: summary?.safe ?? "—", tone: "safe", loading },
  ];

  const banner = error?.code && error.code !== "NETWORK_ERROR" ? (
    <ErrorBanner title="Không hoàn tất được lượt quét" message={error.message} />
  ) : data?.partial_result ? (
    <ErrorBanner
      tone="warning"
      title="Kết quả có thể chưa đầy đủ"
      message="Một số tiến trình không đọc được tên — cần chạy tool với quyền Administrator để thu thập toàn bộ dữ liệu."
    />
  ) : undefined;

  // radar: 1 chấm = 1 cổng (lấy severity cao nhất nhóm) — tránh key trùng
  const radarByPort = new Map<number, Severity>();
  for (const it of items) {
    if (typeof it.detail.port !== "number") continue;
    const port = it.detail.port;
    const sev = severityOf(it);
    const prev = radarByPort.get(port);
    radarByPort.set(port, prev ? worstSeverity(prev, sev) : sev);
  }
  const radarDots: RadarDot[] = [...radarByPort.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([port, severity]) => ({ port, severity }));

  const columns: DataColumn<PortRow>[] = [
    {
      key: "severity",
      label: "Trạng thái",
      sortable: true,
      render: (r) => {
        const tone = r.severity === "safe" ? "safe" : r.severity === "danger" ? "danger" : "warning";
        const label = r.severity === "safe" ? "An toàn" : r.severity === "danger" ? "Nguy hiểm" : "Cảnh báo";
        return <StatusBadge tone={tone} label={label} />;
      },
    },
    { key: "port", label: "Cổng", mono: true, align: "right", sortable: true },
    { key: "processText", label: "Tiến trình (PID)", mono: true, sortable: true },
    { key: "protoText", label: "Giao thức", mono: true, sortable: true },
    { key: "listenerText", label: "Listener", mono: true, sortable: true },
    {
      key: "isNew",
      label: "Mới",
      render: (r) => (r.isNew ? <span className="badge-new">NEW</span> : <span className="text-muted">—</span>),
    },
    { key: "reasonsText", label: "Lý do" },
  ];

  const whitelistById = new Map(whitelist.map((w) => [w.whitelist_key, w]));

  const renderRow = (r: PortRow): ReactElement => {
    const safeEntries = r.items.map((i) => whitelistById.get(i.whitelist_key)).filter((e): e is WhitelistEntry => Boolean(e));
    const totalKeys = r.items.filter((i) => i.whitelist_key).length;
    if (totalKeys === 0) {
      return (
        <span className="row-actions-pending" title="Đang quét…">
          …
        </span>
      );
    }
    const allMarkedSafe = totalKeys === safeEntries.length;
    return (
      <div className="row-actions">
        {allMarkedSafe ? (
          <Button variant="subtle" size="sm" data-testid="mark-safe-btn" onClick={() => safeEntries.forEach((e) => void unmarkSafe(e.id))}>
            Bỏ an toàn
          </Button>
        ) : (
          <Button variant="ghost" size="sm" data-testid="mark-safe-btn" onClick={() => r.items.forEach((i) => void markSafe(i))}>
            Đánh dấu an toàn
          </Button>
        )}
      </div>
    );
  };

  const portRows = useMemo(
    () => groupByPort(items.map(toRow), severityOf),
    [items, severityOf],
  );

  return (
    <ModulePageLayout
      title="Port Scanner"
      description="Quét toàn bộ cổng đang LISTEN, đối chiếu whitelist và so sánh với lượt quét trước để phát hiện điều mới xuất hiện."
      kpis={kpis}
      banner={banner}
    >
      <PanelGrid>
        <Panel title="Radar cổng" subtitle="Vòng trong = well-known, rìa = dynamic">
          <RadarMap dots={radarDots} scanning={isScanning} />
        </Panel>

        <Panel
          title="Chi tiết cổng"
          subtitle={
            isScanning
              ? `đã quét ${progress.current}/${progress.total} cổng`
              : summary
                ? `${portRows.length} cổng đang mở (${items.length} tiến trình)`
                : undefined
          }
        >
          {isScanning ? (
            <ProgressBar current={progress.current} total={progress.total} message={progress.message} />
          ) : phase === "loading" ? (
            <EmptyState title="Đang tải dữ liệu gần nhất…" description="" />
          ) : phase === "error" ? (
            <EmptyState
              title="Không có kết quả quét"
              description={error?.message ?? "Không tải được lượt quét gần nhất từ backend."}
              action={
                <>
                  <Button variant="ghost" data-testid="retry-btn" onClick={() => retryLoad()}>
                    Tải lại
                  </Button>{" "}
                  <Button data-testid="scan-button" onClick={() => void startScan()}>
                    Quét ngay
                  </Button>
                </>
              }
            />
          ) : phase === "empty" || items.length === 0 ? (
            <EmptyState
              title="Chưa có dữ liệu quét"
              description="Chưa có lượt quét nào. Bấm 'Quét ngay' để kiểm tra các cổng đang lắng nghe trên máy này."
              action={
                <Button data-testid="scan-button" onClick={() => void startScan()}>
                  Quét ngay
                </Button>
              }
            />
          ) : (
            <DataTable
              columns={columns}
              rows={portRows}
              rowKey="key"
              searchPlaceholder="Lọc theo port / tiến trình"
              renderColumn={renderRow}
              maxHeight="420px"
            />
          )}
        </Panel>
      </PanelGrid>
    </ModulePageLayout>
  );
}
