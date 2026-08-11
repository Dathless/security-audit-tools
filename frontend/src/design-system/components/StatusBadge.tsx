import type { ReactElement } from "react";
import "./StatusBadge.css";

export type BadgeTone = "danger" | "warning" | "safe" | "info";

const TONE_LABEL: Record<BadgeTone, string> = {
  danger: "Nguy hiểm",
  warning: "Cảnh báo",
  safe: "An toàn",
  info: "Thông tin",
};

interface StatusBadgeProps {
  tone: BadgeTone;
  label?: string;
}

/** Nhãn trạng thái: chấm màu + text (luôn có text để không loại trừ người mù màu). */
export function StatusBadge({ tone, label }: StatusBadgeProps): ReactElement {
  return (
    <span className={`badge badge-${tone}`} role="status">
      <span className="badge-dot" aria-hidden="true" />
      <span className="badge-label">{label ?? TONE_LABEL[tone]}</span>
    </span>
  );
}