import type { ReactElement, ReactNode } from "react";
import "./PanelGrid.css";

interface PanelGridProps {
  children: ReactNode;
}

/**
 * Lưới 2 cột (380px / 1fr): panel phụ (trực quan hoá) + panel chính (chi tiết).
 * Tự chuyển 1 cột ở màn hẹp (<960px).
 */
export function PanelGrid({ children }: PanelGridProps): ReactElement {
  return <div className="panel-grid">{children}</div>;
}