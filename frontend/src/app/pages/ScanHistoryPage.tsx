import type { ReactElement } from "react";
import { useEffect, useState } from "react";
import { ModulePageLayout } from "../../design-system/layouts/ModulePageLayout";
import { DataTable, type DataColumn } from "../../design-system/components/DataTable";
import { StatusBadge } from "../../design-system/components/StatusBadge";
import { EmptyState } from "../../design-system/components/EmptyState";
import { Button } from "../../design-system/components/Button";
import { ApiError, fetchPortScans } from "../../modules/api";
import { navigate } from "../../core/router";
import type { ScanListItem } from "../../core/types/api";

interface HistoryRow extends ScanListItem {
  displayName: string;
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("vi-VN");
}

const columns: DataColumn<HistoryRow>[] = [
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
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let mounted = true;
    fetchPortScans(1, 50)
      .then((data) => {
        if (!mounted) return;
        setRows(data.items.map((it) => ({ ...it, displayName: "Port Scanner" })));
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
  }, []);

  const kpis = [
    { label: "Tổng lượt quét", value: loading ? "…" : total, sub: "Toàn bộ module" },
    {
      label: "Lượt gần nhất",
      value: rows[0] ? formatTime(rows[0].started_at) : "—",
      sub: rows[0]?.status === "running" ? "Đang chạy" : undefined,
    },
  ];

  return (
    <ModulePageLayout
      title="Scan History"
      description="Lịch sử tổng hợp các lượt quét của mọi module."
      kpis={kpis}
    >
      {error ? (
        <EmptyState
          title="Không tải được lịch sử"
          description={error.message}
          action={<Button onClick={() => window.location.reload()}>Thử lại</Button>}
        />
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          rowKey="id"
          searchPlaceholder="Lọc theo thời gian / kết quả"
          emptyText={loading ? "Đang tải…" : "Chưa có lượt quét nào."}
          renderColumn={() => (
            <Button variant="subtle" size="sm" onClick={() => navigate("/modules/port-scanner")}>
              Mở module
            </Button>
          )}
        />
      )}
    </ModulePageLayout>
  );
}