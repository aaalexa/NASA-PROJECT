"use client";

import { useId, useMemo } from "react";
import { Area, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from "recharts";
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

export interface TrendPoint {
  x: string | number;
  value: number | null;
  fit?: number | null;
}

/** Series as a soft gradient area with the backend's trend line dashed on top (recharts through shadcn charts). */
export function TrendChart({
  data,
  valueLabel,
  fitLabel,
  significant,
  className = "h-36 w-full",
}: {
  data: TrendPoint[];
  valueLabel: string;
  fitLabel: string;
  significant: boolean;
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const config = useMemo<ChartConfig>(
    () => ({
      value: { label: valueLabel, color: "var(--blue)" },
      fit: { label: fitLabel, color: significant ? "var(--red)" : "var(--olive)" },
    }),
    [valueLabel, fitLabel, significant]
  );

  const [lo, hi] = useMemo(() => {
    const vals = data.flatMap((d) => [d.value, d.fit ?? null]).filter((v): v is number => v !== null && Number.isFinite(v));
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const pad = (max - min || 1) * 0.12;
    return [min - pad, max + pad];
  }, [data]);

  return (
    <ChartContainer config={config} className={className}>
      <ComposedChart data={data} margin={{ top: 8, right: 6, left: 6, bottom: 0 }}>
        <defs>
          <linearGradient id={`area-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-value)" stopOpacity={0.55} />
            <stop offset="100%" stopColor="var(--color-value)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="3 4" stroke="var(--border)" />
        <XAxis dataKey="x" tickLine={false} axisLine={false} tickMargin={6} minTickGap={28} interval="preserveStartEnd" />
        <YAxis hide domain={[lo, hi]} />
        <ChartTooltip cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }} content={<ChartTooltipContent indicator="line" />} />
        <Area dataKey="value" type="monotone" stroke="var(--color-value)" strokeWidth={2.2} fill={`url(#area-${uid})`} dot={false} activeDot={{ r: 4 }} isAnimationActive animationDuration={900} />
        <Line dataKey="fit" type="linear" stroke="var(--color-fit)" strokeWidth={2.2} strokeDasharray="6 4" dot={false} activeDot={false} isAnimationActive animationDuration={1100} />
      </ComposedChart>
    </ChartContainer>
  );
}
