import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "./Button";
import { ThemeSelector } from "./ThemeSelector";
import { trapDialogFocus } from "./dialogFocus";
import "./EvidenceDrawer.css";

export function EvidenceDrawer({ open, title, onClose, children, actions }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; actions?: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (open && !element?.open) element?.showModal();
    if (!open && element?.open) element.close();
  }, [open]);
  return <dialog ref={dialog} className="evidence-drawer" aria-labelledby={titleId} onClose={onClose} onKeyDown={trapDialogFocus}>
    <header className="evidence-header"><div><p className="eyebrow">BẰNG CHỨNG KIỂM KÊ</p><h2 id={titleId}>{title}</h2></div><Button variant="ghost" onClick={() => dialog.current?.close()} aria-label="Đóng bằng chứng">Đóng ×</Button></header>
    <div className="evidence-tools"><ThemeSelector compact />{actions}</div>
    <div className="evidence-content">{children}</div>
  </dialog>;
}
