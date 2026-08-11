import type { ReactElement, ReactNode } from "react";
import "./KpiCard.css";

export type KpiTone = "danger" | "warning" | "safe" | "info" | "default";

interface KpiCardProps {
  label: string;
  value: ReactNode;
  sub?: string;
  tone?: KpiTone;
  loading?: boolean;
}

/** Thẻ chỉ số KPI: label uppercase + số lớn mono + ghi chú. */
export function KpiCard({ label, value, sub, tone = "default", loading }: KpiCardProps): ReactElement {
  return (
    <div className={`kpi-card kpi-${tone}`}>
      <span className="kpi-label">{label}</span>
      {loading ? (
        <span className="kpi-value kpi-skeleton" aria-hidden="true" />
      ) : (
        <span className="kpi-value">{value}</span>
      )}
      {sub ? <span className="kpi-sub">{sub}</span> : null}
    </div>
  );
}