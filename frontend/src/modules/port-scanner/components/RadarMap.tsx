import type { ReactElement } from "react";
import type { Severity } from "../../../core/types/api";
import "./RadarMap.css";

export interface RadarDot {
  port: number;
  severity: Severity;
}

interface RadarMapProps {
  dots: RadarDot[];
  /** khi đang quét, hiện chế độ "quét" thay vì dừng */
  scanning?: boolean;
}

const CX = 170;
const CY = 170;
const RINGS = [
  { range: "well-known", max: 1024, r: 52, label: "0–1023" },
  { range: "registered", max: 49152, r: 96, label: "1024–49151" },
  { range: "dynamic", max: 65536, r: 138, label: "49152–65535" },
] as const;

type RadarRing = (typeof RINGS)[number];

function polar(port: number): { x: number; y: number } {
  let ring: RadarRing = RINGS[2];
  let prevMax = 49152;
  if (port < 1024) {
    ring = RINGS[0];
    prevMax = 0;
  } else if (port < 49152) {
    ring = RINGS[1];
    prevMax = 1024;
  }
  const frac = Math.min(1, Math.max(0, (port - prevMax) / (ring.max - prevMax)));
  // bắt đầu từ đỉnh (12 giờ), quay thuận kim đồng hồ
  const angle = -Math.PI / 2 + frac * Math.PI * 2;
  return { x: CX + ring.r * Math.cos(angle), y: CY + ring.r * Math.sin(angle) };
}

const SEV_COLOR: Record<Severity, string> = {
  danger: "var(--status-danger)",
  warning: "var(--status-warning)",
  safe: "var(--status-safe)",
};

const SEV_LABEL: Record<Severity, string> = {
  danger: "Ưu tiên cao",
  warning: "Cảnh báo",
  safe: "Không có phát hiện",
};

/**
 * Radar cổng — signature element: vòng tròn đồng tâm chia dải cổng,
 * mỗi cổng quan sát là 1 chấm theo góc tương ứng số hiệu cổng, màu theo severity.
 */
export function RadarMap({ dots, scanning = false }: RadarMapProps): ReactElement {
  const counts = {
    danger: dots.filter((d) => d.severity === "danger").length,
    warning: dots.filter((d) => d.severity === "warning").length,
    safe: dots.filter((d) => d.severity === "safe").length,
  };

  return (
    <div className={`radar${scanning ? " radar-scanning" : ""}`} data-testid="radar-map">
      <svg
        className="radar-svg"
        viewBox="0 0 340 340"
        role="img"
        aria-label={`Radar cổng: ${dots.length} cổng quan sát. Ưu tiên cao ${counts.danger}, cảnh báo ${counts.warning}, không có phát hiện ${counts.safe}.`}
      >
        {/* nền radar */}
        <defs>
          <linearGradient id="radar-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="rgba(61, 169, 252, 0.0)" />
          </linearGradient>
        </defs>
        <circle className="radar-bg" cx={CX} cy={CY} r={150} />
        <circle className="radar-grid radar-grid-1" cx={CX} cy={CY} r={52} />
        <circle className="radar-grid radar-grid-2" cx={CX} cy={CY} r={96} />
        <circle className="radar-grid radar-grid-3" cx={CX} cy={CY} r={138} />
        <line className="radar-cross" x1={CX - 150} y1={CY} x2={CX + 150} y2={CY} />
        <line className="radar-cross" x1={CX} y1={CY - 150} x2={CX} y2={CY + 150} />

        {/* nhãn dải cổng */}
        <text className="radar-label" x={CX} y={CY - 56}>
          Well-known
        </text>
        <text className="radar-label" x={CX} y={CY - 100}>
          Registered
        </text>
        <text className="radar-label" x={CX} y={CY - 142}>
          Dynamic
        </text>

        {/* tia quét */}
        <g className={`radar-sweep${scanning ? " radar-sweep-fast" : ""}`}>
          <path className="radar-sweep-shape" d={`M ${CX} ${CY} L ${CX} ${CY - 150} A 150 150 0 0 1 300 95 Z`} />
        </g>
        <line className="radar-beam" x1={CX} y1={CY} x2={CX} y2={CY - 150} />

        {/* chấm cổng */}
        {dots.map((d) => {
          const p = polar(d.port);
          const pulse = d.severity === "danger" || d.severity === "warning" ? " radar-dot-pulse" : "";
          return (
            <circle
              key={`${d.port}-${d.severity}`}
              className={`radar-dot radar-dot-${d.severity}${pulse}`}
              data-testid="radar-dot"
              cx={p.x}
              cy={p.y}
              r={d.severity === "safe" ? 3 : 4}
            >
              <title>{`Cổng ${d.port} — ${SEV_LABEL[d.severity]}`}</title>
            </circle>
          );
        })}

        <text className="radar-center-num" x={CX} y={CY - 4}>
          {dots.length}
        </text>
        <text className="radar-center-cap" x={CX} y={CY + 14}>
          cổng quan sát
        </text>
      </svg>

      <ul className="radar-legend">
        {(Object.keys(counts) as Severity[]).map((sev) => (
          <li key={sev} className="radar-legend-item">
            <span className="radar-legend-dot" style={{ background: SEV_COLOR[sev] }} aria-hidden="true" />
            <span>{SEV_LABEL[sev]}</span>
            <span className="radar-legend-count">{counts[sev]}</span>
          </li>
        ))}
        <li key="total" className="radar-legend-item radar-legend-total">
          <span>→ Dải cổng: well-known ở tâm, dynamic ở rìa</span>
        </li>
      </ul>
    </div>
  );
}
