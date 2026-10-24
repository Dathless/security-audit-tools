import type { FormEvent, ReactElement } from "react";
import { useEffect, useState } from "react";
import { ModulePageLayout } from "../../design-system/layouts/ModulePageLayout";
import { Panel } from "../../design-system/components/Panel";
import { PanelGrid } from "../../design-system/components/PanelGrid";
import { Button } from "../../design-system/components/Button";
import { StatusBadge } from "../../design-system/components/StatusBadge";
import { ErrorBanner } from "../../design-system/components/ErrorBanner";
import { fetchModules, fetchWhitelist, getLocalToken, setLocalToken } from "../../modules/api";
import { useAppState } from "../../core/appStore";
import type { BackendModule, WhitelistEntry } from "../../core/types/api";
import "./SettingsPage.css";

export function SettingsPage(): ReactElement {
  const { backendOnline } = useAppState();
  const [token, setToken] = useState(getLocalToken());
  const [saved, setSaved] = useState(false);
  const [modules, setModules] = useState<BackendModule[]>([]);
  const [whitelist, setWhitelist] = useState<WhitelistEntry[]>([]);

  useEffect(() => {
    fetchModules()
      .then(setModules)
      .catch(() => setModules([]));
  }, []);

  useEffect(() => {
    fetchWhitelist()
      .then(setWhitelist)
      .catch(() => setWhitelist([]));
  }, []);

  function onSave(e: FormEvent): void {
    e.preventDefault();
    setLocalToken(token);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1600);
  }

  return (
    <ModulePageLayout title="Settings" description="Cấu hình kết nối và thông tin hệ thống của Security Audit.">
      {!backendOnline ? (
        <ErrorBanner
          tone="warning"
          title="Backend chưa kết nối"
          message="Không thể liên hệ backend tại 127.0.0.1:8000. Hãy chạy uvicorn để thao tác. Token dưới đây vẫn lưu được."
        />
      ) : null}

      <PanelGrid>
        <Panel title="Kết nối nội bộ" subtitle="Backend chỉ bind 127.0.0.1 — token bảo vệ khỏi CSRF localhost.">
          <form className="settings-form" onSubmit={onSave}>
            <label className="settings-field">
              <span className="settings-field-label">Local API token</span>
              <input
                className="settings-input"
                type="text"
                value={token}
                placeholder="X-Local-Token"
                autoComplete="off"
                spellCheck={false}
                onChange={(e) => setToken(e.target.value)}
              />
              <span className="settings-hint">
                Tìm trong <code>backend/config.yaml → app.local_token</code> (được sinh tự động lần chạy đầu).
              </span>
            </label>
            <div className="settings-actions">
              <Button type="submit" disabled={!token.trim()}>
                {saved ? "Đã lưu ✓" : "Lưu token"}
              </Button>
            </div>
          </form>
        </Panel>

        <Panel title="Module" subtitle="Danh sách module backend đã đăng ký.">
          <ul className="settings-modules">
            {modules.length === 0 ? (
              <li className="settings-module-empty">Không tải được danh sách module (backend ngoại tuyến?).</li>
            ) : (
              modules.map((m) => (
                <li key={m.id} className="settings-module">
                  <span className="settings-module-name">{m.display_name}</span>
                  <StatusBadge tone={m.enabled ? "safe" : "info"} label={m.enabled ? "Đang bật" : "Đã tắt"} />
                </li>
              ))
            )}
          </ul>
        </Panel>

        <Panel title="Whitelist" subtitle="Các mục đã đánh dấu an toàn, được giữ qua các lượt quét.">
          <ul className="whitelist-list" data-testid="whitelist-list">
            {whitelist.length === 0 ? (
              <li className="whitelist-item" data-testid="whitelist-item">
                <span className="whitelist-empty">Chưa có mục nào trong whitelist.</span>
              </li>
            ) : (
              whitelist.map((w) => (
                <li key={w.id} className="whitelist-item" data-testid="whitelist-item">
                  <span className="whitelist-label">{w.label || w.whitelist_key}</span>
                  <StatusBadge tone="safe" label="An toàn" />
                </li>
              ))
            )}
          </ul>
        </Panel>
      </PanelGrid>
    </ModulePageLayout>
  );
}