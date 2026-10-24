import { useCallback, useEffect, useRef, useState } from "react";
import type { ScanDetail, ScanItem } from "../../core/types/api";
import { setBadge, setScanningNow } from "../../core/appStore";
import { registerScanHandler } from "../../core/scanRegistry";
import { ApiError, acknowledgePort, fetchLatestPortScan, fetchPortScan, openScanSocket, revokePortReview, startPortScan } from "../api";

export type ScanPhase = "loading" | "ready" | "scanning" | "empty" | "error";
export interface ScanProgress { current: number; total: number; message: string }
export interface ScannerError { code: string; message: string }

export function usePortScanner() {
  const [phase, setPhase] = useState<ScanPhase>("loading");
  const [data, setData] = useState<ScanDetail | null>(null);
  const [liveItems, setLiveItems] = useState<ScanItem[]>([]);
  const [progress, setProgress] = useState<ScanProgress>({ current: 0, total: 1, message: "" });
  const [error, setError] = useState<ScannerError | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const mounted = useRef(false);
  const active = useRef(false);
  const activeScan = useRef<string | null>(null);
  const closeSocket = useRef<(() => void) | null>(null);
  const requestVersion = useRef(0);
  const pending = useRef<ScanItem[]>([]);
  const frame = useRef<number | null>(null);
  const liveId = useRef(0);

  const clearPending = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
    pending.current = [];
  }, []);

  const load = useCallback(async (scanId?: string) => {
    const version = ++requestVersion.current;
    try {
      const scan = scanId ? await fetchPortScan(scanId) : await fetchLatestPortScan();
      if (!mounted.current || version !== requestVersion.current) return;
      setData(scan);
      setError(scan?.status === "error" ? { code: "SCAN_FAILED", message: scan.error_message || "Lượt quét đã thất bại." } : null);
      setPhase(!scan ? "empty" : scan.status === "running" ? "scanning" : scan.status === "error" ? "error" : "ready");
      setBadge("port-scanner", scan?.summary?.needs_review_count ?? (scan?.summary?.danger ?? 0) + (scan?.summary?.warning ?? 0));
      return scan;
    } catch (e) {
      if (mounted.current && version === requestVersion.current) {
        const err = e as ApiError;
        setError({ code: err.code, message: err.message });
        setPhase("error");
      }
    }
  }, []);

  const connect = useCallback((id: string) => {
    closeSocket.current?.();
    clearPending();
    active.current = true;
    activeScan.current = id;
    setPhase("scanning");
    setScanningNow(true);
    closeSocket.current = openScanSocket(id, {
      onProgress: (current, total, message) => {
        if (mounted.current && activeScan.current === id) setProgress({ current, total, message });
      },
      onItem: (item) => {
        if (!mounted.current || activeScan.current !== id) return;
        pending.current.push({ ...item, id: --liveId.current, whitelist_key: item.whitelist_key ?? "" });
        if (frame.current === null) frame.current = requestAnimationFrame(() => {
          frame.current = null;
          const batch = pending.current;
          pending.current = [];
          if (mounted.current && activeScan.current === id) setLiveItems((rows) => [...rows, ...batch]);
        });
      },
      onDone: () => {
        if (!mounted.current || activeScan.current !== id) return;
        active.current = false;
        activeScan.current = null;
        closeSocket.current?.();
        clearPending();
        setScanningNow(false);
        void load(id);
      },
      onError: (code, message) => {
        if (!mounted.current || activeScan.current !== id) return;
        active.current = false;
        activeScan.current = null;
        closeSocket.current?.();
        clearPending();
        setScanningNow(false);
        setError({ code, message });
        setPhase("error");
      },
      onDisconnect: () => {
        if (!mounted.current || activeScan.current !== id) return;
        active.current = false;
        activeScan.current = null;
        closeSocket.current?.();
        clearPending();
        setScanningNow(false);
        setError({ code: "WS_DISCONNECTED", message: "Mất kết nối tiến trình quét. Lượt quét có thể vẫn chạy; tải lại để tiếp tục hoặc xem kết quả." });
        setPhase("error");
      },
    });
  }, [clearPending, load]);

  const retryLoad = useCallback(async () => {
    const scan = await load();
    if (mounted.current && scan?.status === "running") connect(scan.id);
  }, [load, connect]);

  const startScan = useCallback(async () => {
    if (active.current) return;
    active.current = true;
    ++requestVersion.current;
    setError(null);
    setLiveItems([]);
    clearPending();
    setProgress({ current: 0, total: 1, message: "Đang khởi tạo lượt quét…" });
    setPhase("scanning");
    setScanningNow(true);
    try {
      const { scan_id } = await startPortScan();
      if (mounted.current) connect(scan_id);
    } catch (e) {
      active.current = false;
      setScanningNow(false);
      if (mounted.current) {
        const err = e as ApiError;
        setError({ code: err.code, message: err.message });
        setPhase("error");
      }
    }
  }, [connect, clearPending]);

  const review = useCallback(async (item: ScanItem) => {
    if (!data || reviewing || active.current) return;
    const version = requestVersion.current;
    setReviewing(true);
    try {
      if (item.review_id) await revokePortReview(item.review_id);
      else await acknowledgePort(data.id, item.id);
      if (mounted.current && !active.current && version === requestVersion.current) await load(data.id);
    } catch (e) {
      if (mounted.current && version === requestVersion.current) {
        const err = e as ApiError;
        setError({ code: err.code, message: err.message });
      }
    } finally {
      if (mounted.current) setReviewing(false);
    }
  }, [data, reviewing, load]);

  useEffect(() => registerScanHandler("port-scanner", () => void startScan()), [startScan]);
  useEffect(() => {
    mounted.current = true;
    void (async () => {
      const scan = await load();
      if (mounted.current && scan?.status === "running") connect(scan.id);
    })();
    return () => {
      mounted.current = false;
      activeScan.current = null;
      closeSocket.current?.();
      clearPending();
    };
  }, [load, connect, clearPending]);

  return { phase, data, error, progress, reviewing, review, startScan, retryLoad,
    isScanning: phase === "scanning", items: phase === "scanning" ? liveItems : data?.items ?? [],
    summary: phase === "scanning" ? null : data?.summary ?? null };
}
