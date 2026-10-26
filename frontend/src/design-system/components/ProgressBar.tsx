import type { ReactElement } from "react";
import "./ProgressBar.css";

interface ProgressBarProps {
  current: number;
  total: number;
  message?: string;
}

/** Tiến trình quét kiểu kỹ thuật: con số cụ thể "đã quét X/Y" thay vì spinner. */
export function ProgressBar({ current, total, message }: ProgressBarProps): ReactElement {
  const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  return (
    <div className="progress" role="progressbar" aria-label="Tiến độ kiểm kê" data-testid="progress-bar" aria-valuemin={0} aria-valuemax={Math.max(1, total)} aria-valuenow={Math.max(0, Math.min(current, total))}>
      <div className="progress-head">
        <span className="progress-label">Đang quét</span>
        <span className="progress-count" data-testid="progress-text">
          {current}/{total}
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
