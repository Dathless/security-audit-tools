import type { ReactElement, ReactNode } from "react";
import "./ErrorBanner.css";

type BannerTone = "danger" | "warning";

interface ErrorBannerProps {
  tone?: BannerTone;
  title: string;
  message: string;
  action?: ReactNode;
}

/** Banner lỗi/cảnh báo ngay dưới topbar: nói rõ nguyên nhân + cách khắc phục. */
export function ErrorBanner({ tone = "danger", title, message, action }: ErrorBannerProps): ReactElement {
  return (
    <div className={`errbanner errbanner-${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <div className="errbanner-text">
        <strong className="errbanner-title">{title}</strong>
        <p className="errbanner-message">{message}</p>
      </div>
      {action ? <div className="errbanner-action">{action}</div> : null}
    </div>
  );
}