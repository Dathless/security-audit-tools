import type { ReactElement } from "react";
import "./ProgressBar.css";

interface ProgressBarProps {
  current: number;
  total: number;
  message?: string;
}

/** Chỉ hiển thị số lượng khi collector đã biết tổng công việc. */
export function ProgressBar({ current, total, message }: ProgressBarProps): ReactElement {
  const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  return (
    <div className={`progress${total <= 0 ? " progress-indeterminate" : ""}`} role="progressbar" aria-label="Tiến độ kiểm kê" aria-valuetext={message} data-testid="progress-bar" aria-valuemin={0} aria-valuemax={total > 0 ? total : undefined} aria-valuenow={total > 0 ? Math.max(0, Math.min(current, total)) : undefined}>
      <div className="progress-head">
        <span className="progress-label">Đang quét</span>
        <span className="progress-count" data-testid="progress-text">
          {total > 0 ? `${current}/${total}` : "Chưa xác định tổng"}
        </span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ transform: `scaleX(${percent / 100})` }} />
      </div>
      {message ? (
        <p className="progress-message" data-testid="progress-message">
          {message}
        </p>
      ) : null}
    </div>
  );
}
