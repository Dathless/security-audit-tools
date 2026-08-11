import type { ReactElement, ReactNode } from "react";
import "./EmptyState.css";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

/** Trạng thái khi module chưa có dữ liệu quét — không để trắng trang. */
export function EmptyState({ title, description, action }: EmptyStateProps): ReactElement {
  return (
    <div className="empty-state">
      <span className="empty-state-icon" aria-hidden="true">
        ⌁
      </span>
      <h4 className="empty-state-title">{title}</h4>
      <p className="empty-state-desc">{description}</p>
      {action ? <div className="empty-state-action">{action}</div> : null}
    </div>
  );
}