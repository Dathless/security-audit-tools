import type { FormEvent, ReactElement } from "react";
import { useEffect, useState } from "react";
import { ModulePageLayout } from "../../design-system/layouts/ModulePageLayout";
import { Panel } from "../../design-system/components/Panel";
import { PanelGrid } from "../../design-system/components/PanelGrid";
import { Button } from "../../design-system/components/Button";
import { StatusBadge } from "../../design-system/components/StatusBadge";
import { ErrorBanner } from "../../design-system/components/ErrorBanner";
import { fetchModules, fetchWhitelist, fetchPortReviews, revokePortReview, removeFromWhitelist, getLocalToken, setLocalToken } from "../../modules/api";
import { setBadge, useAppState } from "../../core/appStore";
import type { BackendModule, PortReview, WhitelistEntry } from "../../core/types/api";
import "./SettingsPage.css";

export function SettingsPage(): ReactElement {
  const { backendOnline } = useAppState();
  const [token, setToken] = useState(getLocalToken());
  const [saved, setSaved] = useState(false);
  const [modules, setModules] = useState<BackendModule[]>([]);
  const [whitelist, setWhitelist] = useState<WhitelistEntry[]>([]);
  const [reviews, setReviews] = useState<PortReview[]>([]);
  const [reviewPage, setReviewPage] = useState(1);
  const [reviewTotal, setReviewTotal] = useState(0);
  const [revision, setRevision] = useState(0);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    fetchPortReviews(reviewPage).then((response) => {
      if (current) { setReviews(response.items); setReviewTotal(response.total); setReviewError(null); }
    }).catch((error: Error) => { if (current) setReviewError(error.message); });
    return () => { current = false; };
  }, [reviewPage, revision]);

  async function revoke(id: number): Promise<void> {
    try { await revokePortReview(id); setRevision((value) => value + 1); }
    catch (error) { setReviewError((error as Error).message); }
  }

  useEffect(() => {
    let current = true;
    fetchModules()
      .then((items) => {
        if (!current) return;
        setModules(items);
        items.forEach((module) => {
          const summary = module.last_scan?.summary;
          setBadge(module.id, summary?.needs_review_count ?? (summary?.danger || 0) + (summary?.warning || 0));
        });
      })
      .catch(() => { if (current) setModules([]); });
    return () => { current = false; };
  }, [revision]);

  useEffect(() => {
    fetchWhitelist()
      .then(setWhitelist)
      .catch(() => setWhitelist([]));
  }, []);

  function onSave(e: FormEvent): void {
    e.preventDefault();
    setLocalToken(token);
    setSaved(true);
    setRevision((value) => value + 1);
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

        <Panel title="Xác nhận endpoint" subtitle="Bản ghi đã xem xét; không xác nhận an toàn hoặc thay đổi mức rủi ro.">
          {reviewError && <ErrorBanner title="Không tải được review" message={reviewError} />}
          <ul className="whitelist-list" data-testid="port-reviews-list">
            {reviews.length === 0 ? <li>Chưa có xác nhận.</li> : reviews.map((record) => <li className="whitelist-item" key={record.id}>
              <span>{record.label} · {record.scope === "scan" ? "Chỉ lượt đã xem" : "Theo bằng chứng"} · {record.expired_at ? "Hết hiệu lực" : "Còn lưu"}</span>
              <Button variant="subtle" size="sm" onClick={() => void revoke(record.id)}>Hủy xác nhận</Button>
            </li>)}
          </ul>
          <div className="settings-actions"><Button variant="subtle" disabled={reviewPage <= 1} onClick={() => setReviewPage((page) => page - 1)}>Trước</Button><span>Trang {reviewPage} · {reviewTotal} bản ghi</span><Button variant="subtle" disabled={reviewPage * 20 >= reviewTotal} onClick={() => setReviewPage((page) => page + 1)}>Sau</Button></div>
        </Panel>
        <Panel title="Whitelist cũ" subtitle="Chỉ đọc/xóa; không tự áp dụng vào đánh giá mới. Quét lại rồi xác nhận endpoint.">
          <ul className="whitelist-list" data-testid="whitelist-list">
            {whitelist.length === 0 ? (
              <li className="whitelist-item" data-testid="whitelist-item">
                <span className="whitelist-empty">Chưa có mục nào trong whitelist.</span>
              </li>
            ) : (
              whitelist.map((w) => (
                <li key={w.id} className="whitelist-item" data-testid="whitelist-item">
                  <span className="whitelist-label">{w.label || w.whitelist_key}</span>
                  <Button variant="subtle" size="sm" onClick={() => void removeFromWhitelist(w.id).then(() => fetchWhitelist()).then(setWhitelist).catch((error: Error) => setReviewError(error.message))}>Xóa mục cũ</Button>
                </li>
              ))
            )}
          </ul>
        </Panel>
      </PanelGrid>
    </ModulePageLayout>
  );
}
