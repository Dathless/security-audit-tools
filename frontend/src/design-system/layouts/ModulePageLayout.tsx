import type { ReactElement, ReactNode } from "react";
import { KpiCard, type KpiTone } from "../components/KpiCard";
import "./ModulePageLayout.css";

export interface LayoutKpi {
  label: string;
  value: ReactNode;
  sub?: string;
  tone?: KpiTone;
  loading?: boolean;
}

interface ModulePageLayoutProps {
  title: string;
  description: string;
  /** nút hành động trang (vd "Quét ngay") — hiển thị bên phải header */
  actions?: ReactNode;
  kpis?: LayoutKpi[];
  /** banner lỗi/cảnh báo nằm ngay dưới topbar */
  banner?: ReactNode;
  children?: ReactNode;
}

/**
 * Hợp đồng layout DUY NHẤT cho mọi module:
 * page header → KPI row → nội dung (PanelGrid).
 * Module không tự dựng khung trang — chỉ lấp slot này.
 */
export function ModulePageLayout({
  title,
  description,
  actions,
  kpis,
  banner,
  children,
}: ModulePageLayoutProps): ReactElement {
  return (
    <div className="mp-layout">
      {banner ? <div className="mp-banner">{banner}</div> : null}

      <header className="mp-header">
        <div>
          <h2 className="mp-title">{title}</h2>
          <p className="mp-desc">{description}</p>
        </div>
        {actions ? <div className="mp-actions">{actions}</div> : null}
      </header>

      {kpis && kpis.length > 0 ? (
        <div className="kpi-row">
          {kpis.map((kpi) => (
            <KpiCard key={kpi.label} {...kpi} />
          ))}
        </div>
      ) : null}

      <div className="mp-content">{children}</div>
    </div>
  );
}