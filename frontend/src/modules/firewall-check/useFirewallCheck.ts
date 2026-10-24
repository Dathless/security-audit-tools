import { useCallback, useEffect, useRef, useState } from "react";
import { setBadge, setScanningNow } from "../../core/appStore";
import { registerScanHandler } from "../../core/scanRegistry";
import type { ScanDetail } from "../../core/types/api";
import { ApiError, fetchLatestFirewallScan, openScanSocket, startFirewallScan } from "../api";

export function useFirewallCheck() {
  const [data, setData] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ current: 0, total: 1, message: "Đang khởi tạo…" });
  const active = useRef(false);
  const mounted = useRef(false);
  const closeSocket = useRef<(() => void) | null>(null);

  const loadLatest = useCallback(async () => {
    try {
      const scan = await fetchLatestFirewallScan();
      if (!mounted.current) return;
      setData(scan);
      setError(scan?.status === "error" ? scan.error_message || "Không đọc được Windows Firewall." : null);
      if (scan?.status === "done") setBadge("firewall-check", (scan.summary?.danger ?? 0) + (scan.summary?.warning ?? 0));
      return scan;
    } catch (e) {
      if (mounted.current) setError((e as ApiError).message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  const connect = useCallback((scanId: string) => {
    closeSocket.current?.();
    closeSocket.current = openScanSocket(scanId, {
      onProgress: (current, total, message) => {
        if (mounted.current) setProgress({ current, total, message });
      },
      onDone: () => {
        active.current = false;
        setScanningNow(false);
        closeSocket.current?.();
        if (mounted.current) {
          setScanning(false);
          void loadLatest();
        }
      },
      onError: (_code, message) => {
        active.current = false;
        setScanningNow(false);
        closeSocket.current?.();
        if (mounted.current) {
          setScanning(false);
          setError(message);
        }
      },
      onDisconnect: () => {
        active.current = false;
        closeSocket.current?.();
        setScanningNow(false);
        if (mounted.current) {
          setScanning(false);
          setError("Mất kết nối tiến trình quét. Lượt quét có thể vẫn chạy; tải lại trang để xem kết quả hoặc thử lại.");
        }
      },
    });
  }, [loadLatest]);

  const startScan = useCallback(async () => {
    if (active.current) return;
    active.current = true;
    setScanning(true);
    setScanningNow(true);
    setError(null);
    setProgress({ current: 0, total: 1, message: "Đang đọc Windows Firewall…" });
    try {
      const { scan_id } = await startFirewallScan();
      if (mounted.current) connect(scan_id);
    } catch (e) {
      active.current = false;
      setScanningNow(false);
      if (mounted.current) {
        setScanning(false);
        setError((e as ApiError).message);
      }
    }
  }, [connect]);

  useEffect(() => registerScanHandler("firewall-check", () => void startScan()), [startScan]);

  useEffect(() => {
    mounted.current = true;
    void (async () => {
      const scan = await loadLatest();
      if (mounted.current && scan?.status === "running") {
        active.current = true;
        setScanning(true);
        setScanningNow(true);
        connect(scan.id);
      }
    })();
    return () => {
      mounted.current = false;
      closeSocket.current?.();
    };
  }, [loadLatest, connect]);

  return { data, loading, scanning, progress, error, startScan };
}
