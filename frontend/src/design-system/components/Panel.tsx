import type { ReactElement, ReactNode } from "react";
import "./Panel.css";

interface PanelProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}

/** Khối nội dung bo góc lớn: title + subtitle + slot nội dung. */
export function Panel({ title, subtitle, actions, children, className = "", id }: PanelProps): ReactElement {
  return (
    <section className={`panel ${className}`} data-testid="panel" id={id}>
      <header className="panel-head">
        <div className="panel-title-group">
          <h3 className="panel-title" data-testid="panel-title">
            {title}
          </h3>
          {subtitle ? (
            <p className="panel-subtitle" data-testid="panel-subtitle">
              {subtitle}
            </p>
          ) : null}
        </div>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}
