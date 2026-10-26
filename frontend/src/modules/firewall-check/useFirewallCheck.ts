import { useCallback, useEffect, useRef, useState } from "react";
import { setBadge, setScanningNow, updateHealth } from "../../core/appStore";
import { registerScanHandler } from "../../core/scanRegistry";
import type { ScanDetail, ScanListItem } from "../../core/types/api";
import { ApiError, fetchFirewallScan, fetchFirewallScans, fetchHealth, fetchLatestFirewallScan, openScanSocket, startFirewallScan } from "../api";

const INITIAL_PROGRESS = { current: 0, total: 0, message: "Đang đọc cấu hình Windows Firewall…" };
interface LogEntry { message: string; seconds: number }

export function useFirewallCheck() {
  const [data, setData] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(INITIAL_PROGRESS);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const [sampleSeconds, setSampleSeconds] = useState<number | null>(null);
  const [connectionNotice, setConnectionNotice] = useState<string | null>(null);
  const active = useRef(false);
  const activeScan = useRef<string | null>(null);
  const mounted = useRef(false);
  const requestVersion = useRef(0);
  const startedAt = useRef(0);
  const sampleFinishedAt = useRef(0);
  const closeSocket = useRef<(() => void) | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frame = useRef<number | null>(null);
  const pending = useRef<LogEntry[]>([]);
  const pendingProgress = useRef(INITIAL_PROGRESS);

  const seconds = useCallback(() => Math.max(0, Math.floor((Date.now() - startedAt.current) / 1000)), []);
  const appendLog = useCallback((message: string) => {
    const entry = { message, seconds: seconds() };
    setLog((entries) => [...entries.slice(-99), entry]);
  }, [seconds]);

  const rememberDuration = useCallback((scan: ScanListItem | null) => {
    if (scan?.status !== "done" || scan.partial_result) return;
    const start = Date.parse(scan.started_at ?? "");
    const finish = Date.parse(scan.finished_at ?? "");
    if (Number.isFinite(start) && Number.isFinite(finish) && finish > start && finish > sampleFinishedAt.current) {
      sampleFinishedAt.current = finish;
      setSampleSeconds((finish - start) / 1000);
    }
  }, []);

  const flushProgress = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
    if (!pending.current.length) return;
    const entries = pending.current;
    pending.current = [];
    setLog((previous) => [...previous, ...entries].slice(-100));
    setProgress(pendingProgress.current);
  }, []);

  const stopMonitoring = useCallback(() => {
    closeSocket.current?.();
    closeSocket.current = null;
    if (pollTimer.current !== null) clearTimeout(pollTimer.current);
    pollTimer.current = null;
  }, []);

  const finish = useCallback((version: number, scan: ScanDetail | null, message?: string) => {
    if (!mounted.current || version !== requestVersion.current) return;
    flushProgress();
    stopMonitoring();
    active.current = false;
    activeScan.current = null;
    setScanning(false);
    setLoading(false);
    setElapsed(seconds());
    setConnectionNotice(null);
    setData(scan?.status === "done" ? scan : null);
    const failure = message ?? (scan?.status === "error" ? scan.error_message || "Không đọc được Windows Firewall." : null);
    setError(failure);
    appendLog(failure ? `Thất bại: ${failure}` : "Hoàn tất — kết quả đã được lưu.");
    if (scan?.status === "done") {
      rememberDuration(scan);
      setBadge("firewall-check", (scan.summary?.danger ?? 0) + (scan.summary?.warning ?? 0));
    }
    void fetchHealth().then((health) => {
      if (mounted.current && version === requestVersion.current) updateHealth(health);
    }).catch(() => { /* The shell's health poll will retry. */ });
  }, [appendLog, flushProgress, rememberDuration, seconds, stopMonitoring]);

  const connect = useCallback((id: string, version: number, recovered?: ScanDetail) => {
    stopMonitoring();
    active.current = true;
    activeScan.current = id;
    setData(null);
    setLoading(false);
    setScanning(true);
    setScanningNow(true);
    if (recovered) {
      const timestamp = Date.parse(recovered.started_at ?? "");
      startedAt.current = Number.isFinite(timestamp) ? Math.min(Date.now(), timestamp) : Date.now();
      setElapsed(seconds());
      appendLog("Tiếp tục theo dõi lượt quét. Nhật ký chỉ gồm các mốc quan sát trong phiên này; các mốc trước có thể thiếu.");
    }
    const valid = () => mounted.current && version === requestVersion.current && activeScan.current === id;
    let checking = false;
    const reconcile = async () => {
      if (!valid() || checking) return;
      checking = true;
      try {
        const scan = await fetchFirewallScan(id);
        if (!valid()) return;
        if (scan.status !== "running") {
          finish(version, scan);
          return;
        }
      } catch {
        if (!valid()) return;
        setConnectionNotice("Chưa liên lạc được backend. Vẫn giữ lượt quét đang hoạt động và thử kiểm tra lại.");
      } finally {
        checking = false;
      }
      if (valid()) pollTimer.current = setTimeout(() => void reconcile(), 2000);
    };
    closeSocket.current = openScanSocket(id, {
      onProgress: (current, total, message) => {
        if (!valid()) return;
        pendingProgress.current = { current, total, message };
        pending.current = [...pending.current.slice(-99), { message, seconds: seconds() }];
        if (frame.current === null) frame.current = requestAnimationFrame(flushProgress);
      },
      onDone: () => {
        if (!valid()) return;
        stopMonitoring();
        setConnectionNotice("Đang tải kết quả đã lưu…");
        void reconcile();
      },
      onError: (_code, message) => {
        if (valid()) finish(version, null, message);
      },
      onDisconnect: () => {
        if (!valid()) return;
        stopMonitoring();
        const message = "Mất kết nối tiến trình. Đang kiểm tra lượt quét qua HTTP mỗi 2 giây; nhật ký có thể thiếu mốc.";
        setConnectionNotice(message);
        appendLog(message);
        void reconcile();
      },
    });
  }, [appendLog, finish, flushProgress, seconds, stopMonitoring]);

  const startScan = useCallback(async () => {
    if (active.current) return;
    active.current = true;
    const version = ++requestVersion.current;
    activeScan.current = null;
    stopMonitoring();
    pending.current = [];
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
    startedAt.current = Date.now();
    setElapsed(0);
    setData(null);
    setLoading(false);
    setLog([{ message: INITIAL_PROGRESS.message, seconds: 0 }]);
    setScanning(true);
    setScanningNow(true);
    setError(null);
    setConnectionNotice(null);
    setProgress(INITIAL_PROGRESS);
    try {
      const { scan_id } = await startFirewallScan();
      if (mounted.current && version === requestVersion.current) connect(scan_id, version);
    } catch (e) {
      if (!mounted.current || version !== requestVersion.current) return;
      const err = e as ApiError;
      if (err.code === "SCAN_ALREADY_RUNNING") {
        try {
          const scan = await fetchLatestFirewallScan();
          if (!mounted.current || version !== requestVersion.current) return;
          if (scan?.status === "running") {
            connect(scan.id, version, scan);
            return;
          }
          if (scan) {
            finish(version, scan);
            return;
          }
        } catch { /* Keep the original conflict message if recovery fails. */ }
      }
      finish(version, null, err.message);
    }
  }, [connect, finish, stopMonitoring]);

  useEffect(() => registerScanHandler("firewall-check", () => void startScan()), [startScan]);
  useEffect(() => {
    if (!scanning) return;
    const timer = setInterval(() => setElapsed(seconds()), 1000);
    return () => clearInterval(timer);
  }, [scanning, seconds]);

  useEffect(() => {
    mounted.current = true;
    const version = ++requestVersion.current;
    void fetchFirewallScans().then((history) => {
      if (mounted.current && version === requestVersion.current) rememberDuration(history.items.find((scan) => scan.status === "done" && !scan.partial_result) ?? null);
    }).catch(() => { /* A missing duration sample never blocks scanning. */ });
    void fetchLatestFirewallScan().then((scan) => {
      if (!mounted.current || version !== requestVersion.current) return;
      setLoading(false);
      if (scan?.status === "running") {
        connect(scan.id, version, scan);
      } else {
        setData(scan?.status === "done" ? scan : null);
        setError(scan?.status === "error" ? scan.error_message || "Không đọc được Windows Firewall." : null);
        rememberDuration(scan);
        if (scan?.status === "done") setBadge("firewall-check", (scan.summary?.danger ?? 0) + (scan.summary?.warning ?? 0));
      }
    }).catch((e: ApiError) => {
      if (mounted.current && version === requestVersion.current) {
        setLoading(false);
        setError(e.message);
      }
    });
    return () => {
      mounted.current = false;
      activeScan.current = null;
      active.current = false;
      stopMonitoring();
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
      pending.current = [];
    };
  }, [connect, rememberDuration, stopMonitoring]);

  return { data, loading, scanning, progress, error, startScan, log, elapsed, sampleSeconds, connectionNotice };
}
