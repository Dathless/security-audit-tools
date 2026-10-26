import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactElement } from "react";
import { activeModules, findModuleByRoute, firstActiveModule } from "../core/moduleRegistry";
import { GENERAL_NAV, navigate, useRoute } from "../core/router";
import { useScanHandler } from "../core/scanRegistry";
import { appStore, updateHealth, useAppState, setBadge } from "../core/appStore";
import { fetchHealth, fetchModules, openGlobalSocket } from "../modules/api";
import { Button } from "../design-system/components/Button";
import { ThemeSelector } from "../design-system/components/ThemeSelector";
import { trapDialogFocus } from "../design-system/components/dialogFocus";
import { NavItem } from "../design-system/components/NavItem";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { ScanHistoryPage } from "./pages/ScanHistoryPage";
import { SettingsPage } from "./pages/SettingsPage";
import "./AppShell.css";

const HEALTH_POLL_MS = 5000;

function Sidebar({ route, onNavigate }: { route: string; onNavigate?: () => void }): ReactElement {
  const { badges, healthStatus } = useAppState();
  const [query, setQuery] = useState("");
  const modules = activeModules().filter((module) => `${module.name} ${module.description ?? ""}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));

  const statusLabel = useMemo(() => {
    switch (healthStatus) {
      case "scanning":
        return "Đang quét";
      case "idle":
        return "Sẵn sàng";
      case "offline":
        return "Backend ngoài";
      default:
        return "Đang kết nối…";
    }
  }, [healthStatus]);

  return (
    <aside className="sidebar" data-testid="sidebar">
      <a className="brand" href="#/" onClick={onNavigate}>
        <span className="brand-mark">▣</span>
        <span className="brand-name">Security Audit<small>LOCAL WORKSPACE</small></span>
      </a>
      <label className="module-search-label"><span className="sr-only">Tìm module</span><input type="search" placeholder="Tìm module…" value={query} onChange={(event) => setQuery(event.target.value)} data-testid="module-search" /></label>
      <nav className="nav" aria-label="Điều hướng chính">
        <div className="nav-modules">
        <p className="nav-group-label">Modules</p>
        {modules.map((m) => (
          <NavItem
            key={m.id}
            icon={m.icon}
            label={m.name}
            href={`#${m.route}`}
            active={route === m.route}
            disabled={m.status !== "active"}
            soon={m.status !== "active"}
            badge={badges[m.id] ?? 0}
            dataTestId={`nav-item-${m.id}`}
            dataModule={m.id}
            dataStatus={m.status}
            dataRoute={m.route}
            dataGroup="modules"
            onNavigate={onNavigate}
          />
        ))}
        {modules.length === 0 && <p className="nav-empty" role="status">Không tìm thấy module</p>}
        </div>
        <div className="nav-general">
        <p className="nav-group-label nav-group-spacer">General</p>
        {GENERAL_NAV.map((g) => (
          <NavItem
            key={g.route}
            icon={g.icon}
            label={g.label}
            href={`#${g.route}`}
            active={route === g.route}
            dataTestId={`nav-item-${g.route.replace(/^\//, "")}`}
            dataRoute={g.route}
            dataGroup="general"
            onNavigate={onNavigate}
          />
        ))}
        </div>
      </nav>

      <footer className="sidebar-footer">
        <span className={`sidebar-status-dot status-${healthStatus}`} aria-hidden="true" />
        <span className="sidebar-status-text">{statusLabel}</span>
      </footer>
    </aside>
  );
}

function Topbar({ route, onMenu }: { route: string; onMenu?: () => void }): ReactElement {
  const module = route.startsWith("/modules/") ? findModuleByRoute(route) : undefined;
  const handler = useScanHandler(module?.id);
  const { scanningNow } = useAppState();

  const currentName =
    module?.name ?? GENERAL_NAV.find((g) => g.route === route)?.label ?? "";

  return (
    <header className="topbar" data-testid="topbar">
      <div className="breadcrumb" data-testid="breadcrumb">
        {onMenu && <Button variant="ghost" data-testid="menu-toggle" aria-label="Mở điều hướng" aria-haspopup="dialog" onClick={onMenu}>☰</Button>}
        <span className="crumb">Security Audit</span>
        <span className="crumb-sep" aria-hidden="true">
          /
        </span>
        <span className="crumb-current">{currentName}</span>
      </div>

      <div className="topbar-actions">
        <ThemeSelector compact />
        {module && <Button
          variant="primary"
          data-testid="scan-button"
          onClick={() => handler?.()}
          disabled={!module || !handler}
          title={module?.status !== "active" ? "Module chưa khả dụng" : "Quét ngay"}
        >
          <span aria-hidden="true">⟳</span>
          {module && scanningNow ? "Đang quét…" : "Quét ngay"}
        </Button>}
      </div>
    </header>
  );
}

export function AppShell(): ReactElement {
  const route = useRoute();
  const [mobile, setMobile] = useState(() => window.matchMedia("(max-width: 960px)").matches);
  const menu = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 960px)");
    const change = () => setMobile(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);

  useEffect(() => {
    if (!route || route === "/") {
      const first = firstActiveModule();
      if (first) navigate(first.route);
    }
  }, [route]);

  useEffect(() => {
    let mounted = true;

    const refreshHealth = async () => {
      try {
        const h = await fetchHealth();
        if (mounted) updateHealth(h, true);
      } catch {
        if (mounted) updateHealth(null, false);
      }
    };

    void refreshHealth();
    const healthTimer = window.setInterval(refreshHealth, HEALTH_POLL_MS);

    void fetchModules()
      .then((mods) => {
        if (!mounted) return;
        // seed badge từ last scan nếu backend báo has_scan
        mods.forEach((m) => {
          const sm = m.last_scan?.summary;
          const count = sm?.needs_review_count ?? (sm?.danger || 0) + (sm?.warning || 0);
          if (appStore.get().badges[m.id] === undefined) setBadge(m.id, count);
        });
      })
      .catch(() => {
        if (mounted) updateHealth(null, false);
      });

    const closeGlobal = openGlobalSocket((msg) => {
      if (msg.type === "done" || msg.type === "error") {
        void refreshHealth();
      }
    });

    return () => {
      mounted = false;
      window.clearInterval(healthTimer);
      closeGlobal();
    };
  }, []);

  let content: ReactElement;
  if (route === "/scan-history") {
    content = <ScanHistoryPage />;
  } else if (route === "/settings") {
    content = <SettingsPage />;
  } else {
    const m = findModuleByRoute(route);
    if (m?.Page) {
      content = <m.Page />;
    } else if (m) {
      content = <ComingSoonPage module={m} />;
    } else {
      const first = firstActiveModule();
      content = (
        <div className="unknown-route">
          <p>Trang không tồn tại.</p>
          {first ? <Button onClick={() => navigate(first.route)}>Về trang chính</Button> : null}
        </div>
      );
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); document.getElementById("main-content")?.focus(); }}>Đến nội dung chính</a>
      {mobile ? <dialog ref={menu} className="mobile-navigation" aria-label="Điều hướng chính" onKeyDown={trapDialogFocus}>
        <Button variant="ghost" className="menu-close" onClick={() => menu.current?.close()}>Đóng điều hướng ×</Button>
        <Sidebar route={route} onNavigate={() => menu.current?.close()} />
      </dialog> : <Sidebar route={route} />}
      <div className="app-main">
        <Topbar route={route} onMenu={mobile ? () => menu.current?.showModal() : undefined} />
        <main className="app-content" id="main-content" tabIndex={-1}>{content}</main>
      </div>
    </div>
  );
}
