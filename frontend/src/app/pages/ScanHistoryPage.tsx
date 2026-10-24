import type { ReactElement } from "react";
import { useEffect, useState } from "react";
import { ModulePageLayout } from "../../design-system/layouts/ModulePageLayout";
import { DataTable, type DataColumn } from "../../design-system/components/DataTable";
import { StatusBadge } from "../../design-system/components/StatusBadge";
import { EmptyState } from "../../design-system/components/EmptyState";
import { Button } from "../../design-system/components/Button";
import { ApiError, fetchPortScans, fetchFirewallScans } from "../../modules/api";
import { navigate } from "../../core/router";
import type { ScanListItem } from "../../core/types/api";

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("vi-VN");
}

const columns: DataColumn<ScanListItem>[] = [
  { key: "started_at", label: "Thời gian", sortable: true, render: (r) => formatTime(r.started_at) },
  {
    key: "status",
    label: "Trạng thái",
    sortable: true,
    render: (r) =>
      r.status === "done" ? (
        <StatusBadge tone="safe" label="Hoàn tất" />
      ) : r.status === "running" ? (
        <StatusBadge tone="info" label="Đang chạy" />
      ) : (
        <StatusBadge tone="danger" label="Lỗi" />
      ),
  },
  { label: "Cổng mở", mono: true, align: "right", render: (r) => r.summary?.total_open ?? "—" },
  { label: "Nguy hiểm", mono: true, align: "right", render: (r) => r.summary?.danger ?? "—" },
  { label: "Cảnh báo", mono: true, align: "right", render: (r) => r.summary?.warning ?? "—" },
  { label: "An toàn", mono: true, align: "right", render: (r) => r.summary?.safe ?? "—" },
];

export function ScanHistoryPage(): ReactElement {
  const [moduleId, setModuleId] = useState("port-scanner");
  const [rows, setRows] = useState<ScanListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchScans = moduleId === "firewall-check" ? fetchFirewallScans : fetchPortScans;
    fetchScans(1, 50)
      .then((data) => {
        if (!mounted) return;
        setRows(data.items);
        setTotal(data.total);
        setError(null);
      })
      .catch((e) => {
        if (mounted) setError(e as ApiError);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [moduleId]);

  const portLabels: Record<number, string> = { 2: "Endpoint", 3: "Ưu tiên cao", 5: "Không có phát hiện" };
  const historyColumns = columns.map((column, index) => {
    if (moduleId === "port-scanner") return { ...column, label: portLabels[index] ?? column.label };
    return index === 2
      ? { ...column, label: "Profiles / rules", render: (row: ScanListItem) => row.summary?.total_profiles != null ? `${row.summary.total_profiles} / ${row.summary.total_rules ?? 0}` : "—" }
      : column;
  });

  const kpis = [
    { label: "Tổng lượt quét", value: loading ? "…" : total, sub: moduleId === "firewall-check" ? "Firewall Check" : "Port Scanner" },
    {
      label: "Lượt gần nhất",
      value: rows[0] ? formatTime(rows[0].started_at) : "—",
      sub: rows[0]?.status === "running" ? "Đang chạy" : undefined,
    },
  ];

  return (
    <ModulePageLayout
      title="Scan History"
      description="Xem lịch sử quét theo module."
      kpis={kpis}
    >
      <label htmlFor="history-module">Module: </label>
      <select id="history-module" value={moduleId} onChange={(event) => {
        setRows([]);
        setTotal(0);
        setError(null);
        setLoading(true);
        setModuleId(event.target.value);
      }}>
        <option value="port-scanner">Port Scanner</option>
        <option value="firewall-check">Firewall Check</option>
      </select>
      {error ? (
        <EmptyState
          title="Không tải được lịch sử"
          description={error.message}
          action={<Button onClick={() => window.location.reload()}>Thử lại</Button>}
        />
      ) : (
        <DataTable
          columns={historyColumns}
          rows={rows}
          rowKey="id"
          searchPlaceholder="Lọc theo thời gian / kết quả"
          emptyText={loading ? "Đang tải…" : "Chưa có lượt quét nào."}
          renderColumn={() => (
            <Button variant="subtle" size="sm" onClick={() => navigate(`/modules/${moduleId}`)}>
              Mở module
            </Button>
          )}
        />
      )}
    </ModulePageLayout>
  );
}
