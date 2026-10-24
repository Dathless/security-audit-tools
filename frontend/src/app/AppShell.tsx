import { useEffect, useMemo } from "react";
import type { ReactElement } from "react";
import { activeModules, findModuleByRoute, firstActiveModule } from "../core/moduleRegistry";
import { GENERAL_NAV, navigate, useRoute } from "../core/router";
import { useScanHandler } from "../core/scanRegistry";
import { appStore, updateHealth, useAppState, setBadge } from "../core/appStore";
import { fetchHealth, fetchModules, openGlobalSocket } from "../modules/api";
import { Button } from "../design-system/components/Button";
import { NavItem } from "../design-system/components/NavItem";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { ScanHistoryPage } from "./pages/ScanHistoryPage";
import { SettingsPage } from "./pages/SettingsPage";
import "./AppShell.css";

const HEALTH_POLL_MS = 5000;

function Sidebar({ route }: { route: string }): ReactElement {
  const { badges, healthStatus } = useAppState();
  const modules = activeModules();

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
      <a className="brand" href="#/">
        <span className="brand-mark">▣</span>
        <span className="brand-name">Security Audit</span>
      </a>

      <nav className="nav">
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
          />
        ))}

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
          />
        ))}
      </nav>

      <footer className="sidebar-footer">
        <span className={`sidebar-status-dot status-${healthStatus}`} aria-hidden="true" />
        <span className="sidebar-status-text">{statusLabel}</span>
      </footer>
    </aside>
  );
}

function Topbar({ route }: { route: string }): ReactElement {
  const module = route.startsWith("/modules/") ? findModuleByRoute(route) : undefined;
  const handler = useScanHandler(module?.id);
  const { scanningNow } = useAppState();

  const currentName =
    module?.name ?? GENERAL_NAV.find((g) => g.route === route)?.label ?? "";

  return (
    <header className="topbar" data-testid="topbar">
      <div className="breadcrumb" data-testid="breadcrumb">
        <span className="crumb">Security Audit</span>
        <span className="crumb-sep" aria-hidden="true">
          /
        </span>
        <span className="crumb-current">{currentName}</span>
      </div>

      <div className="topbar-actions">
        <Button
          variant="primary"
          data-testid="scan-button"
          onClick={() => handler?.()}
          disabled={!module || !handler}
          title={module?.status !== "active" ? "Module chưa khả dụng" : "Quét ngay"}
        >
          <span aria-hidden="true">⟳</span>
          {module && scanningNow ? "Đang quét…" : "Quét ngay"}
        </Button>
      </div>
    </header>
  );
}

export function AppShell(): ReactElement {
  const route = useRoute();

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
      <Sidebar route={route} />
      <div className="app-main">
        <Topbar route={route} />
        <main className="app-content">{content}</main>
      </div>
    </div>
  );
}
