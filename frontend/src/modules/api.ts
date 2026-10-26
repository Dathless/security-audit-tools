import type {
  ApiErrorBody,
  BackendModule,
  HealthInfo,
  ScanDetail,
  ScanListItem,
  ScanWsMessage,
  WhitelistEntry,
  PortReview,
} from "../core/types/api";

/**
 * Client API khớp với backend (docs/architecture/backend.md + mã nguồn backend).
 * Envelope: { success: true, data, error: null } | { success: false, data: null, error: {code,message} }
 */

const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  "http://127.0.0.1:8000/api/v1";

const WS_BASE: string = API_BASE.replace(/^http/, "ws").replace(/\/api\/v1$/, "");

/** Token nội bộ — ưu tiên env, fallback localStorage (cài trong Settings). */
export function getLocalToken(): string {
  const fromEnv = (import.meta.env.VITE_LOCAL_TOKEN as string | undefined) ?? "";
  if (fromEnv) return fromEnv;
  try { return localStorage.getItem("sec_audit_local_token") || ""; }
  catch { return ""; }
}

export function setLocalToken(token: string): void {
  if (token.trim()) localStorage.setItem("sec_audit_local_token", token.trim());
  else localStorage.removeItem("sec_audit_local_token");
}

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

export interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: ApiErrorBody | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getLocalToken();
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("X-Local-Token", token);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "NETWORK_ERROR",
      "Không kết nối được tới backend. Đảm bảo backend đang chạy (uvicorn main:app) tại 127.0.0.1:8000.",
    );
  }

  let body: Envelope<T> | null;
  try {
    body = (await res.json()) as Envelope<T>;
  } catch {
    body = null;
  }

  if (!res.ok || !body?.success) {
    const err = body?.error ?? {
      code: "HTTP_ERROR",
      message: `Yêu cầu thất bại (HTTP ${res.status}).`,
    };
    throw new ApiError(err.code, err.message);
  }
  return body.data as T;
}

/* ---------- hệ thống ---------- */

export async function fetchModules(): Promise<BackendModule[]> {
  const data = await request<{ modules: BackendModule[] }>("/modules");
  return data.modules;
}

export async function fetchHealth(): Promise<HealthInfo> {
  return request<HealthInfo>("/health");
}

/* ---------- port-scanner ---------- */

export async function startPortScan(): Promise<{ scan_id: string }> {
  return request("/modules/port-scanner/scan", { method: "POST", body: "{}" });
}

export async function fetchLatestPortScan(): Promise<ScanDetail | null> {
  return request<ScanDetail | null>("/modules/port-scanner/scans/latest");
}

export async function fetchPortScan(scanId: string): Promise<ScanDetail> {
  return request<ScanDetail>(`/modules/port-scanner/scans/${scanId}`);
}

export async function fetchPortScans(page = 1, pageSize = 20): Promise<{
  items: ScanListItem[];
  page: number;
  page_size: number;
  total: number;
}> {
  return request(`/modules/port-scanner/scans?page=${page}&page_size=${pageSize}`);
}

/* ---------- firewall-check ---------- */

export async function startFirewallScan(): Promise<{ scan_id: string }> {
  return request("/modules/firewall-check/scan", { method: "POST", body: "{}" });
}

export async function fetchLatestFirewallScan(): Promise<ScanDetail | null> {
  return request("/modules/firewall-check/scans/latest");
}

export async function fetchFirewallScan(scanId: string): Promise<ScanDetail> {
  return request(`/modules/firewall-check/scans/${scanId}`);
}

export async function fetchFirewallScans(page = 1, pageSize = 20): ReturnType<typeof fetchPortScans> {
  return request(`/modules/firewall-check/scans?page=${page}&page_size=${pageSize}`);
}

export async function fetchWhitelist(): Promise<WhitelistEntry[]> {
  return request<WhitelistEntry[]>("/modules/port-scanner/whitelist");
}

export async function acknowledgePort(scanId: string, itemId: number): Promise<PortReview> {
  return request("/modules/port-scanner/reviews", {
    method: "POST",
    body: JSON.stringify({ scan_id: scanId, item_id: itemId }),
  });
}

export async function fetchPortReviews(page = 1): Promise<{ items: PortReview[]; page: number; page_size: number; total: number }> {
  return request(`/modules/port-scanner/reviews?page=${page}&page_size=20`);
}

export async function revokePortReview(id: number): Promise<{ id: number; deleted: boolean }> {
  return request(`/modules/port-scanner/reviews/${id}`, { method: "DELETE" });
}

export async function removeFromWhitelist(entryId: number): Promise<{ id: number; deleted: boolean }> {
  return request(`/modules/port-scanner/whitelist/${entryId}`, { method: "DELETE" });
}

/* ---------- WebSocket ---------- */

function parseWsMessage(raw: string): ScanWsMessage | null {
  try {
    const msg = JSON.parse(raw) as ScanWsMessage;
    if (!msg || typeof msg !== "object" || !("type" in msg)) return null;
    return msg;
  } catch {
    return null;
  }
}

function createSocket(path: string): WebSocket {
  const token = getLocalToken();
  return new WebSocket(`${WS_BASE}${path}`, token ? ["sec-audit", `token.${encodeURIComponent(token)}`] : []);
}

/**
 * Subscribe vào kênh 1 scan cụ thể. Trả về hàm huỷ kết nối.
 * Gọi ngay sau khi POST /scan nhận được scan_id.
 */
export function openScanSocket(
  scanId: string,
  handlers: {
    onProgress?: (current: number, total: number, message: string) => void;
    onItem?: (item: Extract<ScanWsMessage, { type: "item_found" }>["item"]) => void;
    onDone?: (summary: Extract<ScanWsMessage, { type: "done" }>) => void;
    onError?: (code: string, message: string) => void;
    onDisconnect?: () => void;
  },
): () => void {
  const ws = createSocket(`/ws/scan/${scanId}`);
  ws.onclose = () => handlers.onDisconnect?.();
  ws.onerror = () => handlers.onDisconnect?.();
  ws.onmessage = (ev) => {
    const msg = parseWsMessage(ev.data as string);
    if (!msg) return;
    switch (msg.type) {
      case "progress":
        handlers.onProgress?.(msg.current, msg.total, msg.message);
        break;
      case "item_found":
        handlers.onItem?.(msg.item);
        break;
      case "done":
        handlers.onDone?.(msg);
        break;
      case "error":
        handlers.onError?.(msg.code, msg.message);
        break;
    }
  };
  return () => {
    try {
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
      ws.close();
    } catch {
      /* noop */
    }
  };
}

/** Kênh global — nhận sự kiện scan của scheduler (có ai đó tự quét). */
export function openGlobalSocket(onMessage: (msg: ScanWsMessage) => void): () => void {
  const ws = createSocket("/ws/events");
  ws.onmessage = (ev) => {
    const msg = parseWsMessage(ev.data as string);
    if (msg) onMessage(msg);
  };
  return () => {
    try {
      ws.onmessage = null;
      ws.close();
    } catch {
      /* noop */
    }
  };
}
