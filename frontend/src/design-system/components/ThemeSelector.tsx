import { useId } from "react";
import { THEMES, setTheme, useTheme } from "../../core/theme";
import "./ThemeSelector.css";

export function ThemeSelector({ compact = false }: { compact?: boolean }) {
  const id = useId();
  const theme = useTheme();
  return <label className={`theme-control${compact ? " theme-control-compact" : ""}`} htmlFor={id}>
    <span className={compact ? "sr-only" : "theme-control-label"}>Giao diện</span>
    <select id={id} value={theme} onChange={(event) => setTheme(event.target.value)} data-testid="theme-selector">
      {THEMES.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
    </select>
    {!compact && <span className="theme-control-hint">{THEMES.find((option) => option.id === theme)?.description}</span>}
  </label>;
}
