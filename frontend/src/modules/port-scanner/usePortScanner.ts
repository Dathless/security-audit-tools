import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  ScanDetail,
  ScanItem,
  ScanSummary,
  Severity,
  WhitelistEntry,
} from "../../core/types/api";
import { setBadge, setScanningNow } from "../../core/appStore";
import { registerScanHandler } from "../../core/scanRegistry";
import {
  ApiError,
  addToWhitelist,
  fetchLatestPortScan,
  fetchWhitelist,
  openScanSocket,
  removeFromWhitelist,
  startPortScan,
} from "../api";

export type ScanPhase = "loading" | "ready" | "scanning" | "empty" | "error";

export interface ScanProgress {
  current: number;
  total: number;
  message: string;
}

export interface ScannerError {
  code: string;
  message: string;
}

function needsAttention(item: ScanItem, whitelistKeys: ReadonlySet<string>): boolean {
  return severityOf(item, whitelistKeys) === "danger" || severityOf(item, whitelistKeys) === "warning";
}

function severityOf(item: ScanItem, whitelistKeys: ReadonlySet<string>): Severity {
  return whitelistKeys.has(item.whitelist_key) ? "safe" : item.severity;
}

export function usePortScanner() {
  const [phase, setPhase] = useState<ScanPhase>("loading");
  const [data, setData] = useState<ScanDetail | null>(null);
  const [liveItems, setLiveItems] = useState<ScanItem[]>([]);
  const [progress, setProgress] = useState<ScanProgress>({ current: 0, total: 0, message: "" });
  const [whitelist, setWhitelist] = useState<WhitelistEntry[]>([]);
  const [error, setError] = useState<ScannerError | null>(null);
  const [scanId, setScanId] = useState<string | null>(null);

  const closeSocketRef = useRef<(() => void) | null>(null);
  const phaseRef = useRef(phase);

  const whitelistKeys = useMemo(() => new Set(whitelist.map((w) => w.whitelist_key)), [whitelist]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  const applyScan = useCallback((scan: ScanDetail | null) => {
    setData(scan);
    if (scan) setPhase(scan.status === "error" ? "error" : "ready");
    else setPhase("empty");
  }, []);

  const loadWhitelist = useCallback(async () => {
    try {
      setWhitelist(await fetchWhitelist());
    } catch {
      setWhitelist([]);
    }
  }, []);

  const loadLatest = useCallback(async () => {
    try {
      const scan = await fetchLatestPortScan();
      applyScan(scan);
      setError(null);
    } catch (e) {
      const err = e as ApiError;
      setError({ code: err.code, message: err.message });
      setPhase("error");
    }
  }, [applyScan]);

  const connectScanSocket = useCallback(
    (id: string) => {
      closeSocketRef.current?.();
      closeSocketRef.current = openScanSocket(id, {
        onProgress: (current, total, message) => setProgress({ current, total, message }),
        onItem: (item) => {
          const live: ScanItem = {
            id: Math.random(),
            ...item,
            whitelist_key: "",
          };
          setLiveItems((prev) => [...prev, live]);
        },
        onDone: () => {
          setScanningNow(false);
          void loadLatest();
          void loadWhitelist();
        },
        onError: (code, message) => {
          setScanningNow(false);
          setError({ code, message });
          setPhase("error");
        },
      });
    },
    [loadLatest, loadWhitelist],
  );

  const startScan = useCallback(async () => {
    if (phaseRef.current === "scanning") return;
    setError(null);
    setLiveItems([]);
    setProgress({ current: 0, total: 0, message: "Đang khởi tạo lượt quét…" });
    setPhase("scanning");
    setScanningNow(true);
    try {
      const { scan_id } = await startPortScan();
      setScanId(scan_id);
      connectScanSocket(scan_id);
    } catch (e) {
      setScanningNow(false);
      const err = e as ApiError;
      setError({ code: err.code, message: err.message });
      setPhase("error");
    }
  }, [connectScanSocket]);

  const markSafe = useCallback(
    async (item: ScanItem) => {
      if (!item.whitelist_key) return;
      try {
        await addToWhitelist(item.whitelist_key, item.title);
        await loadWhitelist();
        await loadLatest();
        setError(null);
      } catch (e) {
        const err = e as ApiError;
        setError({ code: err.code, message: err.message });
      }
    },
    [loadWhitelist, loadLatest],
  );

  const unmarkSafe = useCallback(
    async (entryId: number) => {
      try {
        await removeFromWhitelist(entryId);
        await loadWhitelist();
        await loadLatest();
        setError(null);
      } catch (e) {
        const err = e as ApiError;
        setError({ code: err.code, message: err.message });
      }
    },
    [loadWhitelist, loadLatest],
  );

  useEffect(() => registerScanHandler("port-scanner", () => void startScan()), [startScan]);

  useEffect(() => {
    let mounted = true;
    void (async () => {
      try {
        const scan = await fetchLatestPortScan();
        if (!mounted) return;
        applyScan(scan);
      } catch (e) {
        if (!mounted) return;
        const err = e as ApiError;
        setError({ code: err.code, message: err.message });
        setPhase("error");
      }
      if (mounted) void loadWhitelist();
    })();
    return () => {
      mounted = false;
      closeSocketRef.current?.();
    };
  }, [applyScan, loadWhitelist]);

  // nav badge "cần xem" trên sidebar = mục chưa safe
  useEffect(() => {
    const need = data?.items?.filter((it) => needsAttention(it, whitelistKeys)).length ?? 0;
    setBadge("port-scanner", need);
  }, [data, whitelistKeys]);

  const items = phase === "scanning" ? liveItems : data?.items ?? [];
  const summary: ScanSummary | null = phase === "scanning" ? null : data?.summary ?? null;

  return {
    phase,
    data,
    items,
    summary,
    progress,
    whitelist,
    error,
    scanId,
    isScanning: phase === "scanning",
    startScan,
    markSafe,
    unmarkSafe,
    severityOf: (item: ScanItem): Severity => severityOf(item, whitelistKeys),
    retryLoad: () => void loadLatest(),
  };
}

export type { ScanItem, WhitelistEntry };