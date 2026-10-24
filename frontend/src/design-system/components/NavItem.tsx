import type { ReactElement } from "react";
import "./NavItem.css";

interface NavItemProps {
  icon: string;
  label: string;
  active?: boolean;
  disabled?: boolean;
  soon?: boolean;
  badge?: number;
  href?: string;
  onNavigate?: () => void;
  dataTestId?: string;
  dataModule?: string;
  dataStatus?: string;
  dataRoute?: string;
  dataGroup?: string;
}

/** Mục trong sidebar: icon + label + active/disabled + badge số. */
export function NavItem({
  icon,
  label,
  active = false,
  disabled = false,
  soon = false,
  badge = 0,
  href,
  onNavigate,
  dataTestId,
  dataModule,
  dataStatus,
  dataRoute,
  dataGroup,
}: NavItemProps): ReactElement {
  const cls = [
    "nav-item",
    active ? "nav-item-active" : "",
    disabled ? "nav-item-disabled" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <a
      className={cls}
      href={href ?? "#"}
      data-testid={dataTestId}
      data-module={dataModule}
      data-status={dataStatus}
      data-route={dataRoute}
      data-group={dataGroup}
      aria-current={active ? "page" : undefined}
      aria-disabled={disabled || undefined}
      onClick={
        disabled
          ? (e) => e.preventDefault()
          : () => {
              onNavigate?.();
            }
      }
    >
      <span className="nav-item-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="nav-item-label">{label}</span>
      {soon ? <span className="nav-item-soon">soon</span> : null}
      {!disabled && badge > 0 ? <span className="nav-item-badge">{badge}</span> : null}
    </a>
  );
}