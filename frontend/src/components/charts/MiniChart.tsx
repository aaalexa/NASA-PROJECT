"use client";

import { useId } from "react";

export interface ChartSeries {
  label: string;
  /** CSS color or var(). */
  color: string;
  values: (number | null)[];
  dashed?: boolean;
}

/**
 * Small dependency-free line chart (SVG). `x` labels are only used for the first/last captions.
 * Draws a zero line when the data crosses zero (anomalies).
 */
export function MiniChart({
  series,
  xLabels,
  height = 64,
  className,
  ariaLabel,
}: {
  series: ChartSeries[];
  xLabels?: [string, string];
  height?: number;
  className?: string;
  ariaLabel: string;
}) {
  const id = useId();
  const width = 320;
  const pad = 4;
  const all = series.flatMap((s) => s.values).filter((v): v is number => v !== null && Number.isFinite(v));
  if (all.length < 2) return null;
  let min = Math.min(...all);
  let max = Math.max(...all);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const n = Math.max(...series.map((s) => s.values.length));
  const x = (i: number) => pad + (i / Math.max(1, n - 1)) * (width - pad * 2);
  const y = (v: number) => pad + (1 - (v - min) / (max - min)) * (height - pad * 2);

  const path = (values: (number | null)[]) => {
    let d = "";
    let pen = false;
    values.forEach((v, i) => {
      if (v === null || !Number.isFinite(v)) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };

  return (
    <figure className={className}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel} className="h-auto w-full overflow-visible" aria-describedby={id}>
        {min < 0 && max > 0 && (
          <line x1={pad} x2={width - pad} y1={y(0)} y2={y(0)} stroke="var(--border)" strokeWidth={1} strokeDasharray="3 3" />
        )}
        {series.map((s) => (
          <path
            key={s.label}
            d={path(s.values)}
            fill="none"
            stroke={s.color}
            strokeWidth={s.dashed ? 1.5 : 1.75}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={s.dashed ? "4 3" : undefined}
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      {xLabels && (
        <figcaption id={id} className="mt-1 flex justify-between text-[11px] tabular-nums text-muted-foreground">
          <span>{xLabels[0]}</span>
          <span>{xLabels[1]}</span>
        </figcaption>
      )}
    </figure>
  );
}
