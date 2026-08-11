import { useSyncExternalStore } from "react";

/**
 * Đăng ký handler "Quét ngay" của từng module. Module Page tự đăng ký
 * hàm scan khi mount; Topbar gọi handler cho module đang mở.
 * Có subscribe để Topbar vô hiệu/hoạt động theo đúng module đang mở.
 */
export type ScanHandler = () => void;

const handlers = new Map<string, ScanHandler>();
let version = 0;
const listeners = new Set<() => void>();

function emit(): void {
  version += 1;
  listeners.forEach((l) => l());
}

export function registerScanHandler(moduleId: string, handler: ScanHandler): () => void {
  handlers.set(moduleId, handler);
  emit();
  return () => {
    if (handlers.get(moduleId) === handler) {
      handlers.delete(moduleId);
      emit();
    }
  };
}

export function getScanHandler(moduleId: string): ScanHandler | undefined {
  return handlers.get(moduleId);
}

/** Hook: trả về handler scan hiện tại của module, tự re-render khi có thay đổi. */
export function useScanHandler(moduleId: string | undefined): ScanHandler | undefined {
  useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => version,
  );
  return moduleId ? handlers.get(moduleId) : undefined;
}